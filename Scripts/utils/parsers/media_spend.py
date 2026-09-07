# -*- coding: utf-8 -*-
"""
매체비 총합 추출 — 집행 이후 문서에서만 가져온다.

왜 별도 파서인가
  매체비 총합은 보고서에서 가장 자주 인용되는 단 하나의 숫자다. 그런데
  기존 구현은 이 값을 **어디서도 직접 읽지 않고** 매체별 행을 더해서 만들었다.
  병합셀 때문에 매체명이 빈 행(카카오모먼트_크레딧 등)이 누락되면서 실측
  캠페인에서 395,170,000 이어야 할 값이 414,170,000 으로 나왔다.

  더 나쁜 건 출처였다. '계획 예산' 은 제안서 시점의 미디어믹스에서 왔는데,
  그건 부킹 전 숫자라 실제와 다르다. 집행이 끝난 뒤의 보고서에 그 값을 쓰면
  안 된다.

신뢰하는 출처 (둘 다 집행 이후 문서다)
  1순위  데일리리포트 안의 `Media Mix` 시트 → 예산 열의 Grand Total 행
  검증   포스트바이 `Campaign Summary` 표 → Total 행의 예산

  실측 6개 캠페인에서 두 값은 서로 일치했다. 일치하면 확신을 갖고 쓰고,
  어긋나면 임의로 하나를 고르지 않고 양쪽을 함께 남긴다 (claude.md 3.2).

명시적으로 쓰지 않는 것
  · 제안서 / 기획안의 예산
  · 별도 파일로 있는 미디어믹스(제안 시점)의 예산
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from . import sheet_utils as su

# 시트 이름 표기 흔들림 — 'Media Mix', 'Media-mix', 'MediaMix', '미디어믹스'
_SHEET_RE = re.compile(r'^(media\s*[-_]?\s*mix|미디어\s*믹스)$', re.I)

# 총계 행 라벨. 'Sub Total' 과 '<매체> Total' 은 제외해야 한다.
_GRAND_RE = re.compile(r'^\s*(grand\s*total|총\s*합계|합\s*계|total)\s*$', re.I)
_SUBTOTAL_RE = re.compile(r'sub\s*total|소계', re.I)

# 예산 열 후보 (열 제목)
_BUDGET_HEADS = ('예산', '매체비', '광고비', 'budget', 'cost', '집행금액', '금액')


def find_sheet(sheet_names) -> Optional[str]:
    """데일리리포트 워크북에서 Media Mix 시트를 찾는다."""
    for name in sheet_names or []:
        if _SHEET_RE.match(str(name).strip()):
            return name
    return None


def _budget_column(df) -> Tuple[Optional[int], Optional[int]]:
    """
    예산 열과 그 헤더 행을 찾는다.

    상단 메타 영역에도 '예산' 라벨이 있어서(`예산 | 395170000`) 헤더와
    헷갈린다. **아래에 숫자가 여러 개 이어지는 열**만 표 헤더로 인정한다.
    """
    best: Tuple[Optional[int], Optional[int], int] = (None, None, 0)
    limit = min(24, len(df))
    for r in range(limit):
        for c in range(df.shape[1]):
            head = su.norm(df.iat[r, c])
            if not head or head.lower() not in _BUDGET_HEADS:
                continue
            below = 0
            for rr in range(r + 1, len(df)):
                if su.to_number(df.iat[rr, c]) is not None:
                    below += 1
            if below > best[2]:
                best = (c, r, below)
    col, row, n = best
    return (col, row) if n >= 3 else (None, None)


def _row_labels(df, row: int) -> List[str]:
    """한 행의 문자열 셀들 (총계 라벨 탐색용)."""
    out = []
    for c in range(df.shape[1]):
        v = df.iat[row, c]
        if isinstance(v, str) and v.strip():
            out.append(v.strip())
    return out


def extract_from_dataframe(df, *, source_label: str = '') -> Dict[str, Any]:
    """
    Media Mix 시트 한 장에서 매체비 총합을 뽑는다.

    Returns:
        {'total', 'by_media', 'basis', 'header_value', 'confidence', 'note'}
        basis — 'grand_total_row' | 'header_cell' | 'media_sum' | ''
    """
    out: Dict[str, Any] = {'total': None, 'by_media': {}, 'basis': '',
                           'header_value': None, 'confidence': 'none',
                           'note': '', 'source_label': source_label}
    if df is None or getattr(df, 'empty', True):
        return out

    col, head_row = _budget_column(df)
    if col is None:
        out['note'] = '예산 열을 찾지 못함'
        return out

    # ── 상단 메타의 '예산' 값 (표 헤더 위쪽에 캠페인 총 예산이 적혀 있다)
    header_value = None
    for r in range(min(head_row if head_row is not None else 12, 12)):
        for c in range(df.shape[1] - 1):
            if su.norm(df.iat[r, c]) == '예산':
                for c2 in range(c + 1, min(c + 4, df.shape[1])):
                    v = su.to_number(df.iat[r, c2])
                    if v is not None and v > 1000:
                        header_value = v
                        break
            if header_value is not None:
                break
        if header_value is not None:
            break
    out['header_value'] = header_value

    # ── 매체별 Total 행 수집 + Grand Total 행 탐색
    grand = None
    by_media: Dict[str, float] = {}
    for r in range((head_row or 0) + 1, len(df)):
        value = su.to_number(df.iat[r, col])
        if value is None:
            continue
        labels = _row_labels(df, r)
        joined = ' '.join(labels)
        if _SUBTOTAL_RE.search(joined):
            continue                                   # 월별 소계는 건너뛴다
        if any(_GRAND_RE.match(l) for l in labels):
            grand = value                              # 마지막 것이 최종 총계
            continue
        m = re.match(r'^(.*?)\s*Total$', joined, re.I)
        if m and m.group(1).strip():
            by_media[m.group(1).strip()] = value

    # 라벨 없는 마지막 숫자도 총계일 수 있다 (무풍콤보가 그렇다)
    if grand is None:
        nums = [(r, su.to_number(df.iat[r, col])) for r in range(len(df))]
        nums = [(r, v) for r, v in nums if v is not None]
        if nums:
            last_row, last_val = nums[-1]
            if not _row_labels(df, last_row):
                grand = last_val

    out['by_media'] = by_media
    media_sum = sum(by_media.values()) if by_media else None

    if grand is not None:
        out['total'], out['basis'] = grand, 'grand_total_row'
    elif header_value is not None:
        out['total'], out['basis'] = header_value, 'header_cell'
    elif media_sum:
        out['total'], out['basis'] = media_sum, 'media_sum'
        out['note'] = '총계 행이 없어 매체별 합계를 사용'

    # ── 확신도 — 같은 시트 안에서 두 값이 맞아떨어지면 높다
    if out['total'] is not None:
        agree = (header_value is not None
                 and abs(header_value - out['total']) <= max(1.0, out['total'] * 0.001))
        out['confidence'] = 'high' if agree else 'medium'
        if header_value is not None and not agree:
            out['note'] = (f'시트 상단 예산({header_value:,.0f})과 '
                           f'총계 행({out["total"]:,.0f})이 다름')
    return out


def extract(book, sheet_names, *, file_name: str = '') -> Dict[str, Any]:
    """열린 워크북에서 Media Mix 시트를 찾아 매체비 총합을 뽑는다."""
    sheet = find_sheet(sheet_names)
    if not sheet:
        return {'total': None, 'by_media': {}, 'basis': '',
                'header_value': None, 'confidence': 'none',
                'note': 'Media Mix 시트 없음', 'source_label': ''}
    df = su.read_sheet(book, sheet, header=None)
    return extract_from_dataframe(df, source_label=f'{file_name}:{sheet}')
