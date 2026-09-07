# -*- coding: utf-8 -*-
"""
매체 시트의 라벨 구분 표(■ 섹션)를 표별로 분리해 읽는다.

실측 구조 (데일리리포트 매체 시트):
    ■ 상품 별 효율        상품 | 상품 구분 | 예산 | 청구금액 | ... | VTR | CTR | CPM | CPV
    ■ 타겟팅 별 효율      구분 | 상세 타겟팅 | 예산 | ...
    ■ 상품별 X 소재별 효율 상품구분 | 소재 | 초수 | 노출 | 조회 | ...

한 시트에 표가 2~3개 있고 각 표 끝에 TOTAL / Sub 소계 행이 붙는다.
표를 구분하지 않고 한 덩어리로 읽으면 서로 다른 축의 행과 소계가 뒤섞여
효율 비교가 틀린 값으로 산출되므로, 표 단위로 경계를 잡아 읽는다.

축(axis)은 라벨 문구가 아니라 **헤더 이름**으로 판정한다.
라벨 표기는 파일마다 다르지만("상품 별 효율" / "상품별 X 소재별 효율"),
헤더의 '상품' · '소재' · '타겟팅' 어휘는 일관되게 관측됨.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from models.campaign_data import MediaPerformance, MetricSet, Provenance
from . import sheet_utils as su


# 섹션 라벨 (■ 상품 별 효율 …)
_LABEL_RE = re.compile(r'^\s*[■◆▪]\s*(.+)$')

# 지표로 취급하는 정규 컬럼 — MetricSet 필드와 1:1
_METRIC_KEYS = ('billed', 'spend', 'impressions', 'views', 'clicks',
                'vtr', 'ctr', 'cpm', 'cpv', 'cpc')

# 분류 축 헤더 어휘 → 축 종류
# 실측 라벨: 상품 별 효율 / 타겟팅 별 효율 / 상품별 X 소재별 효율 /
#            소재 별 / 타겟 별 효율 / 상품별(타겟별) 효율 / 매체x타겟별 효율 /
#            목적별 효율 — 라벨 표기는 제각각이나 헤더 어휘는 일관됨
_DIM_RULES = (
    ('purpose',   ('목적', 'objective', 'purpose')),
    ('creative',  ('소재', 'creative')),
    ('targeting', ('타겟', '타게팅', 'targeting')),
    ('product',   ('상품', 'product')),
    ('media',     ('매체', 'media')),
    ('group',     ('구분', 'category')),
)

# 캠페인 목적(퍼널 단계) 값으로 관측된 표기.
# 목적 컬럼의 헤더가 '구분' 이거나 '소재' 로 중복 표기된 파일이 있어
# 헤더 이름만으로는 목적 축을 알아볼 수 없다. 값으로도 함께 판정한다.
_FUNNEL_WORDS = (
    'awareness', 'consideration', 'conversion', 'engagement', 'traffic',
    '인지', '고려', '전환', '유입', '트래픽', '도달',
)
# '관심' · '구매' 는 넣지 않는다 — 'MF3554∩관심사+구매의도' 같은 타겟팅 표기에 걸려
# 타겟팅 컬럼이 목적으로 오분류된다 (실측 확인)

# 값이 비어 있어도 표의 끝으로 보지 않는 최대 연속 공백 행 수
_MAX_BLANK_RUN = 2

# 분류 축이 아닌 것이 확실한 컬럼 — 지표 컬럼 앞에 놓여도 축으로 쓰지 않는다
# (예산은 MediaPerformance.budget 으로 따로 담기므로 축·비고에서 제외)
_NOT_DIM_CANON = {'budget', 'list_price', 'unit_price', 'reach', 'frequency',
                  'cpr', 'exp_imps', 'exp_clicks', 'exp_views', 'date', 'note'}


def _dim_kind(header_text: str) -> str:
    """헤더 이름으로 분류 축의 종류를 판정한다 (모르면 'other')"""
    key = su.norm_key(header_text)
    if not key:
        return 'other'
    for kind, words in _DIM_RULES:
        if any(w in key for w in words):
            return kind
    return 'other'


def find_label_rows(df: pd.DataFrame, limit: int = 120) -> List[Tuple[int, str]]:
    """■ 로 시작하는 섹션 라벨 행을 모두 찾는다"""
    out: List[Tuple[int, str]] = []
    for i in range(min(limit, len(df))):
        for v in df.iloc[i]:
            s = su.norm(v)
            if not s:
                continue
            m = _LABEL_RE.match(s)
            if m:
                out.append((i, m.group(1).strip()))
            break                      # 행의 첫 유효 셀만 라벨로 인정
    return out


def _find_header_below(df: pd.DataFrame, start: int, stop: int) -> Optional[int]:
    """라벨 아래에서 지표 컬럼이 2개 이상인 첫 행을 헤더로 본다"""
    for i in range(start, min(stop, len(df))):
        found = {su.canonical_column(v) for v in df.iloc[i]}
        found.discard(None)
        if len(found & set(_METRIC_KEYS)) >= 2:
            return i
    return None


def _dim_columns(df: pd.DataFrame, header: int,
                 first_metric: int) -> List[Tuple[int, str, str]]:
    """
    지표 컬럼 앞쪽의 분류 축 컬럼들.

    Returns:
        [(열 인덱스, 헤더 원문, 축 종류)] — 헤더가 빈 열은 제외
    """
    dims: List[Tuple[int, str, str]] = []
    for j in range(first_metric):
        name = su.norm(su.cell(df, header, j))
        if not name:
            continue
        if su.canonical_column(name) in _NOT_DIM_CANON:
            continue
        dims.append((j, name, _dim_kind(name)))
    return dims


def _is_funnel_value(text: str) -> bool:
    low = su.norm_key(text)
    return bool(low) and any(w in low for w in _FUNNEL_WORDS)


def _detect_purpose_column(df: pd.DataFrame, dims: List[Tuple[int, str, str]],
                           body: range, label: str) -> Optional[int]:
    """
    목적 값이 담긴 분류 축 컬럼을 찾는다.

    판정 순서:
      1) 헤더 이름이 '목적' 계열이면 그 컬럼
      2) 컬럼 값의 절반 이상이 퍼널 표기(Awareness/인지 ...)면 그 컬럼
      3) ■ 라벨에 '목적' 이 있으면 마지막 분류 축 컬럼
         (헤더가 '구분' 이거나 '소재' 로 중복 표기된 파일 대응)

    Returns:
        열 인덱스 (없으면 None)
    """
    for j, _, kind in dims:
        if kind == 'purpose':
            return j

    # 값 기반 판정은 헤더로 축을 못 알아본 컬럼에만 쓴다.
    # 이미 '상세 타겟팅' 처럼 축이 확정된 컬럼까지 검사하면
    # 타겟팅 값이 목적으로 뒤바뀐다 (실측: 타겟팅 4행 오분류)
    for j, _, kind in dims:
        if kind not in ('other', 'group'):
            continue
        values = [su.norm(su.cell(df, row, j)) for row in body]
        values = [v for v in values if v and not su.is_total_row(v)]
        if values and sum(_is_funnel_value(v) for v in values) >= len(values) / 2:
            return j

    if '목적' in label and dims:
        return dims[-1][0]
    return None


def _read_metrics(df: pd.DataFrame, row: int, cols: Dict[str, int]) -> MetricSet:
    return MetricSet(**{
        k: su.to_number(su.cell(df, row, cols.get(k))) for k in _METRIC_KEYS
    })


def _is_empty_metrics(m: MetricSet) -> bool:
    return all(getattr(m, k) in (None, 0)
               for k in ('impressions', 'views', 'clicks', 'spend'))


def read_section_tables(df: pd.DataFrame, *, media: str, sheet: str,
                        file_name: str, budget: Optional[float],
                        period: str,
                        stop_row: Optional[int] = None) -> List[MediaPerformance]:
    """
    시트의 ■ 섹션 표들을 읽어 MediaPerformance 목록으로 돌려준다.

    Args:
        df: header=None 으로 읽은 시트
        media: 시트 상단 Media 라벨 (없으면 시트명)
        sheet: 시트명 (출처 표기용)
        file_name: 파일명 (출처 표기용)
        budget: 시트 상단 Budget (행에 예산 컬럼이 있으면 그 값을 우선)
        period: 시트 상단 Period
        stop_row: 이 행 이후는 읽지 않음 (일자별 표의 시작 행)

    Returns:
        MediaPerformance 목록 (소계/합계 행 제외, 축 표기 포함)
    """
    labels = find_label_rows(df)
    if stop_row is not None:
        labels = [(r, t) for r, t in labels if r < stop_row]
    if not labels:
        return []

    hard_stop = stop_row if stop_row is not None else len(df)
    out: List[MediaPerformance] = []

    for idx, (label_row, label) in enumerate(labels):
        next_label = labels[idx + 1][0] if idx + 1 < len(labels) else hard_stop
        section_end = min(next_label, hard_stop)

        header = _find_header_below(df, label_row + 1, section_end)
        if header is None:
            continue

        cols = su.column_map(df, header)
        metric_positions = [cols[k] for k in _METRIC_KEYS if k in cols]
        if not metric_positions:
            continue
        first_metric = min(metric_positions)
        dims = _dim_columns(df, header, first_metric)
        if not dims:
            continue

        row_budget_col = cols.get('budget')
        purpose_col = _detect_purpose_column(
            df, dims, range(header + 1, section_end), label)
        last_good: Dict[int, str] = {}
        blank_run = 0

        for row in range(header + 1, section_end):
            raw = {j: su.norm(su.cell(df, row, j)) for j, _, _ in dims}
            metrics = _read_metrics(df, row, cols)

            if not any(raw.values()) and _is_empty_metrics(metrics):
                blank_run += 1
                if blank_run >= _MAX_BLANK_RUN:
                    break
                continue
            blank_run = 0

            # 소계/합계/누계 행은 값에 반영하지 않고 병합셀 승계에도 쓰지 않음
            if su.is_total_row(*raw.values()):
                continue

            # 병합셀 승계 (소계 행 라벨이 섞여 내려가지 않도록 위에서 걸러둔 뒤 처리)
            values: Dict[str, str] = {}
            note_bits: List[str] = []
            for j, name, kind in dims:
                if j == purpose_col:
                    kind = 'purpose'             # 헤더 표기와 무관하게 목적 축
                v = raw[j]
                if v:
                    last_good[j] = v
                v = v or last_good.get(j, '')
                if not v or (v == media and kind != 'media'):
                    continue                     # 매체명 반복은 축 값으로 쓰지 않음
                if kind == 'other':
                    # 축으로 쓰지 않는 표기(초수·목적 등)도 버리지 않고 보존
                    note_bits.append(f'{name} {v}')
                else:
                    values[kind] = v             # 같은 축이 2열이면 뒤쪽(상세)을 채택

            if _is_empty_metrics(metrics):
                continue
            if not values and not note_bits:
                continue

            axis = ('purpose' if values.get('purpose') else
                    'creative' if values.get('creative') else
                    'targeting' if values.get('targeting') else 'product')
            product = values.get('product') or values.get('group', '')

            # 상품이 이미 있으면 '구분' 값이 쓰이지 않고 버려진다 —
            # 축으로 쓰지 않더라도 비고에 남겨 보존한다 (실측: '캐러셀')
            group = values.get('group', '')
            if group and group != product:
                note_bits.append(f'구분 {group}')
            row_budget = (su.to_number(su.cell(df, row, row_budget_col))
                          if row_budget_col is not None else None)

            out.append(MediaPerformance(
                media=values.get('media') or media or sheet,
                product=product,
                targeting=values.get('targeting', ''),
                creative=values.get('creative', ''),
                purpose=values.get('purpose', ''),
                axis=axis,
                section=label,
                note=' / '.join(note_bits),
                period_raw=period,
                budget=row_budget if row_budget is not None else budget,
                metrics=metrics,
                source=Provenance(file_name=file_name, sheet_or_slide=sheet,
                                  locator=f'r{row + 1}'),
            ))

    return out
