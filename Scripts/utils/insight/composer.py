# -*- coding: utf-8 -*-
"""
3단 논법 조립 — [발견 Fact] → [평가 Context] → [제언 Action]

규칙 모듈은 '발견'과 '제언'을 만든다. 이 모듈이 그 사이에 빠져 있는
**2단 평가(기획적 해석)**를 채우고, 문체·구조를 강제한 뒤 블록 ID를 부여한다.

평가 문장은 두 곳에서 온다.
  1. playbook.py 가 매칭한 사내 지식(context)  — 있으면 최우선
  2. 이 모듈의 축별 내장 해석 템플릿          — 폴백

문체 규칙 (tone-guide / LESSON_LEARNED.md §2):
  - 개조식 명사형 종결만 사용
  - 서술형 어미 금지 (~했습니다 / ~입니다 / ~한다 / ~이다)
  - 수치 먼저, 해석 뒤
"""

import re
from typing import List, Optional

from models.campaign_data import Insight

from . import axes
from .config import InsightConfig

# ─────────────────────────── 문체 검증

# 명사형 종결로 인정하는 어미 (tone-guide 예문에서 추출)
NOUN_ENDINGS = (
    '기록', '달성', '확보', '운영', '권고', '권장', '절감', '입증', '확인',
    '필요', '제언', '검토', '강화', '확대', '개선', '유지', '전환', '도출',
    '부족', '미흡', '부재', '편중', '집중', '기여', '상향', '하향', '축소',
    '병행', '수립', '설계', '제고', '완화', '보완', '정교화', '다각화',
)

# 서술형 어미 — 검출 시 위반
_NARRATIVE = re.compile(
    r'(습니다|읍니다|입니다|합니다|했다|한다|이다|였다|됩니다|됐다|해요|예요|에요)\s*$')

# 근거 없는 과장 수식어 (데이터 없는 긍정 포장 금지 — CLAUDE.md 3.3)
_HYPE = re.compile(r'(획기적|압도적|극적으로|엄청난|놀라운|완벽한|최고의)')


def violates_tone(text: str) -> Optional[str]:
    """문체 위반 사유를 돌려준다. 문제 없으면 None."""
    t = (text or '').strip()
    if not t:
        return '빈 문장'
    if _NARRATIVE.search(t):
        return f'서술형 어미 사용: …{t[-8:]}'
    if _HYPE.search(t):
        return f'근거 없는 과장 수식어: {_HYPE.search(t).group(1)}'
    return None


def ends_with_noun(text: str) -> bool:
    """명사형 종결 여부 (알려진 어미 목록 기준)"""
    t = (text or '').strip().rstrip('.·')
    return any(t.endswith(e) for e in NOUN_ENDINGS)


# ─────────────────────────── 서술 패턴 추론

def infer_pattern(ins: Insight) -> str:
    """
    metrics 신호로 6패턴 중 하나를 고른다.

    규칙이 명시적으로 pattern 을 넣었으면 그대로 두고, 없을 때만 추론한다.
    """
    m = ins.metrics or {}
    axis = axes.normalize(ins.axis)

    if m.get('absent') or m.get('missing') or m.get('dropped'):
        return 'P3'                                    # 부재-보완형
    if m.get('is_test') or m.get('new_product'):
        return 'P4'                                    # 실험-정착형
    rate = m.get('achievement_rate')
    if rate is not None and rate < 1.0:
        return 'P1'                                    # 성과-한계형
    share = m.get('best_share')
    if share is not None and share >= 0.5:
        return 'P6'                                    # 편중-확장형
    if axis == axes.D_CREATIVE and m.get('creative_count') == 1:
        return 'P5'                                    # 운영노하우형
    if m.get('gap_ratio'):
        return 'P2'                                    # 성과-확대형
    return 'P2'


# ─────────────────────────── 신뢰도 판정

def score_confidence(ins: Insight, cfg: InsightConfig) -> str:
    """
    근거의 강도를 high / medium / low 로 매긴다.

    임계값을 완화하면 '겨우 기준을 넘은' 문장이 섞인다. 그것을 버리지는
    않되(도출량 확대가 목적), 검증 화면에서 기획자가 골라낼 수 있도록
    표시만 해 둔다.
    """
    m = ins.metrics or {}

    ratio = m.get('gap_ratio')
    if ratio:
        floor = float(cfg.th('min_gap_ratio') or 1.10)
        if ratio >= 2.0:
            return 'high'
        return 'medium' if ratio >= floor * 1.35 else 'low'

    gap = m.get('stage_gap')
    if gap is not None:
        if gap >= 0.5:
            return 'high'
        return 'medium' if gap >= 0.25 else 'low'

    lift = m.get('lift')
    if lift is None:
        lift = m.get('click_share')
        if lift is not None and m.get('spend_share') is not None:
            lift = lift - m['spend_share']
    if lift is not None:
        a = abs(float(lift))
        if a >= 0.20:
            return 'high'
        return 'medium' if a >= 0.10 else 'low'

    if m.get('kpi_count') or m.get('achievement_rate') or m.get('click_to_visit'):
        return 'high'          # 목표 대비 실적·전환율은 직접 인용 값
    return 'medium'


CONFIDENCE_LABEL = {'high': '근거 강함', 'medium': '근거 보통', 'low': '근거 약함'}


# ─────────────────────────── 2단 평가(기획적 해석) 생성

def _ctx_media(m: dict, cfg: InsightConfig) -> str:
    # 기간 축(rules_period)에서 흡수된 건 — 발견이 '피크일/구간'이므로 해석도 운영 관점
    if m.get('peak_date'):
        return ('특정 일자에 집행이 몰린 운영 구조 확인 — '
                '초반 임팩트 확보에는 유효하나 기간 전반의 노출 균질성은 저하')
    if m.get('segments'):
        return ('구간별 운영 성과의 편차 확인 — '
                '단계 설계 자체보다 구간 간 물량·메시지 연계가 성과를 좌우')

    metric = cfg.metric_label(m.get('cost_metric') or 'cpv')
    best = m.get('best') or '상위 매체'
    share = m.get('best_share')
    if share is not None and share < 0.05:
        return (f'소액 물량에서 확인된 {metric} 우위 — '
                f'물량 확대 시 효율 유지 여부의 검증 가치 존재')
    if share is not None and share >= 0.5:
        return (f'{best} 편중 구조에서 확보된 효율 — '
                f'단일 매체 의존도 완화 시 리스크 분산 여지 존재')
    return (f'{metric} 격차가 매체 선택보다 상품·지면 조합에서 갈린 것으로 판단 — '
            f'{best} 우위는 지면 적합성에 기인')


def _ctx_targeting(m: dict) -> str:
    winner = m.get('best') or m.get('winner') or '우위 라인'
    kind = m.get('winner_kind') or ''
    if any(k in str(kind) + str(winner) for k in ('키워드', '검색', '실수요')):
        return ('관심사 위주 노출보다 명확한 실수요(검색) 기반 타겟팅의 유효성 입증')
    if any(k in str(kind) + str(winner) for k in ('데모', '성별', '연령')):
        return ('관심사 조합보다 기본 데모 타겟의 반응이 우위 — '
                '타겟 정의의 복잡도가 효율로 직결되지 않음 확인')
    return ('타겟 설정 방식에 따른 반응률 격차 확인 — '
            '노출 확대보다 타겟 정의의 정교함이 효율을 좌우')


def _ctx_creative(m: dict) -> str:
    if m.get('creative_count') == 1:
        return ('단일 소재 장기 운영에 따른 노출 피로도 누적 가능성 — '
                '반복 노출 구간에서 반응률 저하 요인으로 작용')
    fmt = m.get('best_format') or ''
    if fmt:
        return (f'{fmt} 포맷의 기여도 우위 — '
                f'메시지 내용보다 포맷·지면 적합성이 반응을 좌우한 것으로 해석')
    return ('소재별 기여도 편차 확인 — '
            '동일 예산에서도 소재 구성에 따라 성과 폭이 갈림')


def _ctx_funnel(m: dict) -> str:
    # KPI 달성률 축(rules_kpi)에서 흡수된 건 — 미달 지표 유무로 해석이 갈린다
    if m.get('kpi_count'):
        under = list(m.get('under') or [])
        if under:
            return (f'{" · ".join(under[:2])} 지표의 목표 미달 — '
                    f'물량 부족보다 목표 산정 기준과 매체 조합의 재점검 필요')
        best_rate = m.get('best_rate')
        if best_rate and best_rate >= 2.0:
            return ('전 지표 목표 초과 달성 — 다만 초과 폭이 커 '
                    '목표 산정 기준 자체의 보수성이 시사됨')
        return ('전 지표 목표 달성 — 계획 대비 실집행의 안정적 운영 입증')

    rate = m.get('achievement_rate')
    if rate is not None and rate >= 1.0:
        return ('상단 지표(노출·조회) 목표 초과 달성 — '
                '다만 인지 확보가 하단 전환으로 자동 연결되지 않는 구조 확인')
    if rate is not None and rate < 1.0:
        return ('목표 대비 미달 구간 발생 — '
                '물량 부족보다 퍼널 단계별 이탈 요인의 점검 필요성 시사')
    return ('노출 대비 실질 유입·전환 구간에서 효율 격차 발생 — '
            '상단 지표 중심 운영의 한계 확인')


def _ctx_message(m: dict) -> str:
    return ('기획 의도와 실제 시장 반응 간 간극 확인 — '
            '메시지 전달 자체보다 접점별 일관성이 인지 형성을 좌우')


def build_context(ins: Insight, cfg: InsightConfig) -> str:
    """축별 내장 해석 템플릿 (playbook 매칭 실패 시 폴백)"""
    m = ins.metrics or {}
    axis = axes.normalize(ins.axis)
    if axis == axes.B_MEDIA:
        return _ctx_media(m, cfg)
    if axis == axes.C_TARGETING:
        return _ctx_targeting(m)
    if axis == axes.D_CREATIVE:
        return _ctx_creative(m)
    if axis == axes.E_FUNNEL:
        return _ctx_funnel(m)
    if axis == axes.A_MESSAGE:
        return _ctx_message(m)
    return ''


# ─────────────────────────── 마감

def finalize(insights: List[Insight], cfg: InsightConfig,
             warnings: Optional[List[str]] = None) -> List[Insight]:
    """
    축 정규화 · 패턴 추론 · 평가 문장 채움 · 블록 ID 부여 · 문체 검증.

    문체 위반은 문장을 버리지 않고 warnings 로 남긴다 — 규칙이 만든 문장은
    사람이 검증(Stage 1.5)하므로, 조용히 지우는 쪽이 더 위험하다.
    """
    warn = warnings if warnings is not None else []
    seq: dict = {}

    for ins in insights:
        ins.axis = axes.normalize(ins.axis)
        if not ins.pattern:
            ins.pattern = infer_pattern(ins)
        if not ins.context:
            ins.context = build_context(ins, cfg)
        ins.confidence = score_confidence(ins, cfg)

        code = axes.code(ins.axis).lower()
        seq[code] = seq.get(code, 0) + 1
        if not ins.block_id:
            ins.block_id = f'lesson-{code}-{seq[code]}'

        for field_name in ('finding', 'context', 'recommendation'):
            text = getattr(ins, field_name, '')
            if not text:
                continue
            reason = violates_tone(text)
            if reason:
                warn.append(
                    f'[{axes.label(ins.axis)}] {field_name} 문체 점검 — {reason}')

    return insights
