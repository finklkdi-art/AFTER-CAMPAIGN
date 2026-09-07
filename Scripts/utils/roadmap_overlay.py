# -*- coding: utf-8 -*-
"""
로드맵 시간축 보정 — `roadmap_period` 결손에 기획자가 입력한 기간을 반영

미디어믹스에 기간 컬럼이 없는 파일이 있어(실측: OLED TV 캠페인 계획 134건 전부)
자동으로는 로드맵 시간축을 만들 수 없다. Stage 1.5 결손 화면에서 기획자가
[매체 / 상품 / 시작일 / 종료일] 표로 입력하면 그 값을 계획 라인에 얹는다.

매칭 규칙:
  - 매체명이 서로 포함 관계면 같은 매체로 본다 ('유튜브' ↔ 'OTT - 유튜브')
  - 상품을 적었으면 상품까지 포함 관계인 라인만 좁힌다
  - 이미 기간이 있는 라인은 덮어쓰지 않는다 (문서 값 우선)
  - 어느 계획 라인에도 붙지 않는 입력은 버리지 않고 별도 막대로 남긴다

입력값은 문서에서 온 값이 아니므로 출처를 '기획자 직접 입력' 으로 구분해 둔다.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from models.campaign_data import (
    CampaignDataset, DataGap, GAP_FILLED, PlanLine, Provenance,
)
from utils.parsers import sheet_utils as su


MANUAL_SOURCE = '기획자 직접 입력 (Stage 1.5 결손 화면)'

# 입력 표의 컬럼 이름 후보 (step2_dataset._GAP_TABLE_COLUMNS 와 맞춤)
_COL_MEDIA = ('매체', 'media')
_COL_PRODUCT = ('상품', 'product')
_COL_START = ('시작일', '시작', 'start', '기간')
_COL_END = ('종료일', '종료', 'end')

_ISO_RE = re.compile(r'(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})')


def _pick(row: Dict[str, Any], names: Tuple[str, ...]) -> str:
    """행에서 이름이 맞는 첫 컬럼 값을 꺼낸다 (컬럼명 표기 차이 허용)"""
    for key, value in row.items():
        k = su.norm_key(key)
        if any(n in k for n in names):
            text = su.norm(value)
            if text:
                return text
    return ''


def _to_mmdd(value: str) -> Optional[str]:
    """일자 표기를 'MM-DD' 로. 해석 불가면 None (추측하지 않음)"""
    text = su.norm(value)
    if not text:
        return None
    m = _ISO_RE.search(text)
    if m:
        return f'{int(m.group(2)):02d}-{int(m.group(3)):02d}'
    start, _ = su.split_period(text)          # '6/30', '6/30~7/14' 모두 처리
    return start


def _day_key(mmdd: str) -> int:
    m, d = mmdd.split('-')
    return int(m) * 31 + int(d)


def _parse_rows(gap: DataGap) -> Tuple[List[dict], List[str]]:
    """
    입력 표를 (매체, 상품, 시작, 종료) 목록으로 정규화한다.

    Returns:
        (정규화된 항목 목록, 해석 실패 사유 목록)
    """
    raw = gap.filled_value
    if not isinstance(raw, list):
        return [], ['입력 형식이 표가 아님']

    items: List[dict] = []
    problems: List[str] = []
    for idx, row in enumerate(raw, 1):
        if not isinstance(row, dict):
            continue
        media = _pick(row, _COL_MEDIA)
        product = _pick(row, _COL_PRODUCT)
        start_raw = _pick(row, _COL_START)
        end_raw = _pick(row, _COL_END)
        if not (media or product or start_raw or end_raw):
            continue

        start = _to_mmdd(start_raw)
        # 종료일이 비었으면 시작일 칸의 범위 표기('6/30~7/14')에서 뒷값을 쓴다
        end = _to_mmdd(end_raw)
        if end is None and start_raw:
            _, tail = su.split_period(start_raw)
            end = tail
        if start is None:
            problems.append(f'{idx}행 시작일 해석 불가 ({start_raw or "-"})')
            continue
        if end is None:
            end = start                       # 하루짜리 집행
        if _day_key(start) > _day_key(end):
            start, end = end, start
            problems.append(f'{idx}행 시작·종료가 뒤바뀌어 있어 교정함')

        items.append({'media': media, 'product': product,
                      'start': start, 'end': end})
    return items, problems


def _matches(text: str, needle: str) -> bool:
    """서로 포함 관계면 같은 대상으로 본다"""
    a, b = su.norm_key(text), su.norm_key(needle)
    if not a or not b:
        return False
    return a in b or b in a


def apply_period_overlay(dataset: CampaignDataset
                         ) -> Tuple[int, List[PlanLine], List[str]]:
    """
    `roadmap_period` 결손 입력을 계획 라인에 반영한다.

    Args:
        dataset: Stage 1.5 를 거친 데이터셋 (기간이 채워지면 라인이 갱신됨)

    Returns:
        (기간을 채운 계획 라인 수, 매칭되지 않아 별도로 만든 막대 목록,
         기록해 둘 메모 목록)
    """
    gap = dataset.gap('roadmap_period')
    if gap is None or gap.resolution != GAP_FILLED:
        return 0, [], []

    items, notes = _parse_rows(gap)
    if not items:
        return 0, [], notes

    lines = dataset.plan_lines()
    applied = 0
    extras: List[PlanLine] = []

    for item in items:
        same_media = [l for l in lines if _matches(l.media, item['media'])]
        if item['product']:
            narrowed = [l for l in same_media
                        if _matches(l.product, item['product'])]
            if narrowed:
                same_media = narrowed

        hits = [l for l in same_media if not (l.period_start and l.period_end)]
        if hits:
            for line in hits:
                line.period_start = item['start']
                line.period_end = item['end']
                line.period_raw = f"{item['start']}~{item['end']} (직접 입력)"
                applied += 1
            continue

        # 이미 이 입력으로 채워진 라인이면 다시 세지 않는다.
        # 이 함수는 리포트를 만들 때마다 호출되므로 멱등해야 한다 —
        # 그러지 않으면 두 번째 호출부터 매칭된 입력이 별도 막대로 중복 생성된다.
        already = [l for l in same_media
                   if l.period_start == item['start']
                   and l.period_end == item['end']]
        if already:
            applied += len(already)
            continue

        # 붙일 계획 라인이 없어도 입력값을 버리지 않는다
        extras.append(PlanLine(
            media=item['media'] or '(매체 미입력)',
            product=item['product'],
            period_raw=f"{item['start']}~{item['end']} (직접 입력)",
            period_start=item['start'],
            period_end=item['end'],
            source=Provenance(file_name=MANUAL_SOURCE),
        ))

    if extras:
        notes.append(f'계획 라인에 매칭되지 않은 입력 {len(extras)}건은 '
                     f'별도 막대로 표기')

    # 여전히 기간이 없는 계획 라인은 로드맵에서 빠진다 — 조용히 사라지지 않도록 알린다
    still_blank = [l for l in lines if not (l.period_start and l.period_end)]
    if still_blank:
        media_names = sorted({l.media for l in still_blank})
        notes.append(
            f'기간 미확보 계획 라인 {len(still_blank)}건은 로드맵에서 제외 '
            f'(매체: {", ".join(media_names[:4])}'
            f'{" 외" if len(media_names) > 4 else ""})')
    return applied, extras, notes
