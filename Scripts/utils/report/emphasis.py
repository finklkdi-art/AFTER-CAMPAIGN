# -*- coding: utf-8 -*-
"""
문장 안의 수치·지표명만 강조 런으로 분리 — design-spec.md §2 강조 혼합 규칙

  "한 문장 안에서 수치와 핵심 명사만 런으로 분리한다. 문장 전체를 강조하지 않는다."

자동 생성 문장은 길이가 제각각이라 강조 구간을 사람이 지정할 수 없으므로,
숫자(단위 포함)와 지표 약어를 기계적으로 찾아 강조한다.
"""

import re
from typing import List, Tuple


# 지표 약어 — 영문 대문자 관례 유지 (tone-guide 6장)
_METRIC_WORDS = (
    'CPCV', 'CPV', 'CPC', 'CPM', 'CPR', 'VTR', 'CTR', 'VCR', 'KPI',
    'Reach', 'Freq', 'GRPs', 'ROAS',
)

# 숫자 + 단위 / 지표 약어 / Phase 표기
# 앞선 대안이 먼저 매칭되므로 긴 표기('8억 2,726만회')를 먼저 둔다.
# 그렇지 않으면 '2억' + '5,322만' + '회로' 처럼 단위가 강조에서 떨어져 나간다.
_NUM = r'[0-9][0-9,]*(?:\.[0-9]+)?'
_TOKEN_RE = re.compile(
    r'('
    rf'{_NUM}\s*억(?:\s*{_NUM}\s*만)?\s*(?:회|원)?'
    rf'|{_NUM}\s*만\s*(?:회|원)?'
    rf'|{_NUM}\s*(?:%|원|회|배|일|개|건|초)?'
    r'|Phase\s*[0-9]+'
    r'|' + '|'.join(_METRIC_WORDS) +
    r')',
    re.IGNORECASE,
)

# 강조하지 않을 단독 토큰 (조사·기호만 남는 경우)
_TRIVIAL = {'', '-', '·', '/'}


def split_emphasis(text: str) -> List[Tuple[str, bool]]:
    """
    문장을 (조각, 강조여부) 목록으로 나눈다.

    Args:
        text: 원본 문장

    Returns:
        [(조각, True=강조), ...] — 조각을 순서대로 이으면 원문과 동일
    """
    if not text:
        return []
    out: List[Tuple[str, bool]] = []
    pos = 0
    for m in _TOKEN_RE.finditer(text):
        token = m.group(0).strip()
        if token in _TRIVIAL:
            continue
        if m.start() > pos:
            out.append((text[pos:m.start()], False))
        out.append((m.group(0), True))
        pos = m.end()
    if pos < len(text):
        out.append((text[pos:], False))
    return out or [(text, False)]


def to_runs(text: str, face_plain: str, face_emph: str, size: float,
            color_plain: str, color_emph: str) -> List[tuple]:
    """
    add_text() 가 받는 런 목록으로 변환한다.

    Returns:
        [(조각, 폰트, 크기, 색상), ...]
    """
    return [(piece, face_emph if emph else face_plain, size,
             color_emph if emph else color_plain)
            for piece, emph in split_emphasis(text)]
