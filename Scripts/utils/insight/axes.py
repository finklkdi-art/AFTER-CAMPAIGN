# -*- coding: utf-8 -*-
"""
Lesson Learned 5대 분석 축 정의

실제 결과보고서 7장표 분석(LESSON_LEARNED.md)에서 도출한 축이다.
기존 4축(media/targeting/kpi/period)은 그대로 두고 5축 체계로 매핑해
호출부를 건드리지 않는다 (rules_kpi/rules_period 는 수정 없이 계속 동작).

  A message   전략/메시지    제안서의 기획 의도 vs 실제 시장 반응
  B media     매체/상품 효율  예산 비중 vs 실제 달성 효율
  C targeting 타겟팅         타겟 설정 vs 실제 반응률
  D creative  크리에이티브    소재별·포맷별 기여도
  E funnel    전환/퍼널      노출을 넘어선 실질 유입·전환 품질
"""

from typing import Dict, List

# ─────────────────────────── 축 코드
A_MESSAGE = 'message'
B_MEDIA = 'media'
C_TARGETING = 'targeting'
D_CREATIVE = 'creative'
E_FUNNEL = 'funnel'

ORDER: List[str] = [A_MESSAGE, B_MEDIA, C_TARGETING, D_CREATIVE, E_FUNNEL]

LABELS: Dict[str, str] = {
    A_MESSAGE: '전략·메시지',
    B_MEDIA: '매체·상품 효율',
    C_TARGETING: '타겟팅',
    D_CREATIVE: '크리에이티브',
    E_FUNNEL: '전환·퍼널',
}

CODES: Dict[str, str] = {
    A_MESSAGE: 'A', B_MEDIA: 'B', C_TARGETING: 'C',
    D_CREATIVE: 'D', E_FUNNEL: 'E',
}

# 구 축 이름 → 5축 (기존 규칙 모듈이 내보내는 값을 흡수한다)
LEGACY: Dict[str, str] = {
    'media': B_MEDIA,
    'targeting': C_TARGETING,
    'kpi': E_FUNNEL,        # 목표 달성률 = 성과·전환 품질의 일부
    'period': B_MEDIA,      # 기간·Phase 추이 = 매체 운영 결과
}


def normalize(axis: str) -> str:
    """어떤 표기로 들어와도 5축 코드로 정규화"""
    a = (axis or '').strip().lower()
    if a in LABELS:
        return a
    return LEGACY.get(a, B_MEDIA)


def label(axis: str) -> str:
    return LABELS.get(normalize(axis), axis or '')


def code(axis: str) -> str:
    return CODES.get(normalize(axis), '?')


def sort_key(axis: str) -> int:
    """축 표시 순서 (A→E)"""
    try:
        return ORDER.index(normalize(axis))
    except ValueError:
        return len(ORDER)


# ─────────────────────────── 서술 패턴 (LESSON_LEARNED.md §2)
PATTERNS: Dict[str, str] = {
    'P1': '성과-한계형',
    'P2': '성과-확대형',
    'P3': '부재-보완형',
    'P4': '실험-정착형',
    'P5': '운영노하우형',
    'P6': '편중-확장형',
}


def pattern_label(pattern: str) -> str:
    return PATTERNS.get((pattern or '').upper(), '')
