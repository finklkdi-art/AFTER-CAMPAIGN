# -*- coding: utf-8 -*-
"""
축 E — 전환 / 퍼널 (노출을 넘어선 실질 유입·전환 품질)

실제 보고서의 핵심 논리는 "상단 지표를 초과 달성했다고 하단 성과가 따라오지
않는다"이다. 이 축은 그 간극을 찾는다.

원천 3가지
  1. KpiTarget (포스트바이)                  — 퍼널 단계별 목표 대비 달성률
  2. MediaPerformance(axis='purpose')        — 캠페인 목적(퍼널 단계)별 효율
  3. 포스트바이 analytics 섹션 헤드라인       — Click 대비 Visit 전환율
"""

import re
from typing import Dict, List, Optional, Tuple

from models.campaign_data import CampaignDataset, Insight, MediaPerformance

from . import axes
from . import metrics as M
from . import phrasing as P
from .config import InsightConfig

# KPI 명칭 → 퍼널 단계
_STAGE_WORDS: Dict[str, Tuple[str, ...]] = {
    'awareness': ('impression', 'imps', '노출', 'reach', '도달'),
    'engagement': ('view', '조회', 'vtr', 'engagement', '참여'),
    'action': ('click', '클릭', 'ctr', 'visit', '유입', 'conversion', '전환',
               'order', 'cart', '구매'),
}
_STAGE_LABEL = {'awareness': '노출·도달', 'engagement': '조회·참여',
                'action': '클릭·유입'}
_STAGE_ORDER = ('awareness', 'engagement', 'action')


def _stage_of(name: str) -> str:
    low = (name or '').lower()
    for stage, words in _STAGE_WORDS.items():
        if any(w in low for w in words):
            return stage
    return ''


# ─────────────────────────── 1. 퍼널 단계별 달성률 대조

def _kpi_funnel(dataset: CampaignDataset,
                cfg: InsightConfig) -> Optional[Insight]:
    pb = dataset.postbuy
    if not pb or not pb.kpi_targets:
        return None

    by_stage: Dict[str, List[float]] = {}
    detail: Dict[str, List[str]] = {}
    cap = cfg.th('max_achievement_rate') or 5.0
    for t in pb.kpi_targets:
        rate = t.achievement_rate
        if rate is None and t.target and t.actual:
            rate = t.actual / t.target if t.target else None
        if rate is None or rate <= 0 or rate > cap:
            continue
        stage = _stage_of(t.kpi_name)
        if not stage:
            continue
        by_stage.setdefault(stage, []).append(float(rate))
        # 같은 KPI 명이 매체별로 반복되므로 스코프·매체를 붙여 구분한다
        # ('Impression 123% · Impression 124%' 처럼 읽히면 근거가 되지 않음)
        # 상품명이 길면('Trueview Instream') 잘려서 오히려 안 읽힌다 —
        # 그럴 때는 더 짧고 분명한 매체명을 쓴다
        who = (t.product or '').strip()
        if not who or len(who) > 12:
            who = (t.media or t.scope or who or '').strip()
        who_short = P.short_label(who, 12) if who else ''
        detail.setdefault(stage, []).append(
            f'{who_short} {t.kpi_name} {P.rate(rate)}'.strip())

    stages = [s for s in _STAGE_ORDER if s in by_stage]
    if len(stages) < 2:
        return None

    avg = {s: sum(by_stage[s]) / len(by_stage[s]) for s in stages}
    top_stage = max(stages, key=lambda s: avg[s])
    bottom_stage = min(stages, key=lambda s: avg[s])
    if top_stage == bottom_stage:
        return None
    gap = avg[top_stage] - avg[bottom_stage]
    if gap < (cfg.th('min_stage_gap') or 0.10):
        return None

    # 한 줄이 길면 렌더러가 '…' 로 잘라낸다 — 대표 2건까지만 인용한다
    evidence = [f'{_STAGE_LABEL[s]} 평균 달성률 {P.rate(avg[s])} '
                f'({" · ".join(detail[s][:2])})' for s in stages]

    upper_ok = avg[top_stage] >= 1.0
    lower_short = avg[bottom_stage] < 1.0

    if upper_ok and lower_short:
        pattern = 'P1'
        finding = (f'{_STAGE_LABEL[top_stage]} 달성률 {P.rate(avg[top_stage])} 초과 달성 대비 '
                   f'{_STAGE_LABEL[bottom_stage]} {P.rate(avg[bottom_stage])} 미달')
        rec = (f'차기 캠페인 시 {_STAGE_LABEL[bottom_stage]} 단계 KPI 기준 매체·상품 재편성 권장 — '
               f'상단 물량 일부를 전환 기여 지면으로 이관 검토')
    else:
        pattern = 'P6'
        finding = (f'퍼널 단계 간 달성률 편차 {P.rate(gap)} 확인 — '
                   f'{_STAGE_LABEL[top_stage]} 우위 · {_STAGE_LABEL[bottom_stage]} 열위')
        rec = (f'차기 캠페인 시 단계별 KPI 목표의 정합성 재설정 권장 — '
               f'{_STAGE_LABEL[bottom_stage]} 목표 현실화 및 기여 매체 보강')

    return Insight(
        axis=axes.E_FUNNEL,
        pattern=pattern,
        finding=finding,
        recommendation=rec,
        evidence=evidence[:cfg.th('max_evidence_per_insight') or 3],
        sources=P.join_sources([P.source_label(pb.source_file, 'KPI 달성 현황')]),
        priority=2.2 + gap,
        metrics={'achievement_rate': avg[bottom_stage],
                 'top_stage': top_stage, 'bottom_stage': bottom_stage,
                 'stage_gap': gap},
    )


# ─────────────────────────── 2. 목적(퍼널 단계)별 효율

def _purpose_efficiency(dataset: CampaignDataset,
                        cfg: InsightConfig) -> Optional[Insight]:
    dr = dataset.daily_report
    if not dr:
        return None
    rows: List[MediaPerformance] = [r for r in dr.media_performance
                                    if r.axis == 'purpose' and (r.purpose or '').strip()]
    if len(rows) < (cfg.th('min_compare_items') or 2):
        return None

    grouped: Dict[str, List[MediaPerformance]] = {}
    for r in rows:
        grouped.setdefault(r.purpose.strip(), []).append(r)
    if len(grouped) < 2:
        return None

    agg = [(name, M.aggregate(group), len(group))
           for name, group in grouped.items()]
    total_spend = sum((m.spend or 0) for _, m, _ in agg) or None

    # 클릭 기준 기여 대비 예산 비중
    scored = [(n, m, c) for n, m, c in agg if (m.clicks or 0) > 0]
    if len(scored) < 2:
        return None
    total_clicks = sum((m.clicks or 0) for _, m, _ in scored) or None
    scored.sort(key=lambda x: (x[1].clicks or 0), reverse=True)

    top_name, top_m, _ = scored[0]
    click_share = ((top_m.clicks or 0) / total_clicks) if total_clicks else None
    spend_share = M.spend_share(top_m.spend, total_spend)
    if click_share is None or spend_share is None:
        return None
    lift = click_share - spend_share
    if abs(lift) < (cfg.th('min_share_lift') or 0.05):
        return None

    evidence = [
        f'{n} · 집행 {P.eok(m.spend)} · 클릭 {P.cnt(m.clicks)} '
        f'(기여 {P.share_rate((m.clicks or 0) / total_clicks)})'
        for n, m, _ in scored[:3]]

    if lift > 0:
        pattern, rec = 'P2', (
            f'차기 캠페인 시 {top_name} 목적 라인 예산 비중 상향 편성 권장 — '
            f'투입 대비 클릭 기여 우위 구간')
        finding = (f'{top_name} 목적 라인에서 예산 비중 {P.share_rate(spend_share)} 대비 '
                   f'클릭 기여 {P.share_rate(click_share)} 확보')
    else:
        pattern, rec = 'P1', (
            f'{top_name} 목적 라인의 물량 대비 기여 점검 권장 — '
            f'지면·소재 조합 재설계 또는 예산 재배분 검토')
        finding = (f'{top_name} 목적 라인 예산 비중 {P.share_rate(spend_share)} 대비 '
                   f'클릭 기여 {P.share_rate(click_share)}로 투입 대비 성과 열위')

    return Insight(
        axis=axes.E_FUNNEL,
        pattern=pattern,
        finding=finding,
        recommendation=rec,
        evidence=evidence[:cfg.th('max_evidence_per_insight') or 3],
        sources=P.join_sources([
            P.source_label(rows[0].source.file_name, rows[0].section)]),
        priority=1.8 + abs(lift),
        metrics={'purpose': top_name, 'click_share': click_share,
                 'spend_share': spend_share, 'lift': lift},
    )


# ─────────────────────────── 3. Click → Visit 전환 품질

_VISIT_RE = re.compile(
    r'click\s*대비\s*visit[^0-9]{0,12}([0-9]+(?:\.[0-9]+)?)\s*%', re.IGNORECASE)


def _click_to_visit(dataset: CampaignDataset,
                    cfg: InsightConfig) -> Optional[Insight]:
    """
    포스트바이 헤드라인에서 'Click 대비 Visit 비율'을 읽는다.

    analytics 표는 매체마다 열 구성이 달라 파싱이 불안정하므로, 보고서가
    이미 계산해 문장으로 적어 둔 값을 인용한다 (임의 재계산 금지).
    """
    pb = dataset.postbuy
    if not pb:
        return None
    for sec in pb.sections:
        for h in list(sec.headlines) + list(sec.notes):
            m = _VISIT_RE.search(h or '')
            if not m:
                continue
            pct = float(m.group(1)) / 100.0
            good = pct >= 0.35
            return Insight(
                axis=axes.E_FUNNEL,
                pattern='P2' if good else 'P1',
                finding=(f'디지털 광고 클릭 대비 실유입(Visit) 전환율 '
                         f'{P.rate(pct, 1)} 기록'),
                recommendation=(
                    '차기 캠페인 시 유입 전환 우수 지면 중심으로 랜딩 동선 확대 권장 — '
                    '클릭 단가보다 유입 단가 기준 최적화 병행'
                    if good else
                    '차기 캠페인 시 랜딩 페이지 로딩·동선 점검 권장 — '
                    '클릭 이후 이탈 구간의 개선으로 유입 효율 제고'),
                evidence=[f'{sec.title or "Adobe Analytics"} 기준 {h.strip()[:70]}',
                          '클릭 지표 달성이 실유입으로 자동 연결되지 않는 구간 확인'],
                sources=P.join_sources([
                    P.source_label(pb.source_file, sec.title or 'Analytics')]),
                priority=2.0,
                metrics={'click_to_visit': pct},
            )
    return None


# ─────────────────────────── 진입점

def generate(dataset: CampaignDataset, cfg: InsightConfig,
             excluded: List[str]) -> List[Insight]:
    out: List[Insight] = []
    for fn, why in (
            (lambda: _kpi_funnel(dataset, cfg), 'KPI 퍼널 단계 2개 미만 또는 편차 기준 미달'),
            (lambda: _purpose_efficiency(dataset, cfg), '목적별 실적 비교 대상 부족'),
            (lambda: _click_to_visit(dataset, cfg), 'Click 대비 Visit 전환율 문구 미확보')):
        try:
            ins = fn()
        except Exception as e:
            excluded.append(f'전환·퍼널 축 규칙 실패: {e}')
            continue
        if ins:
            out.append(ins)
        else:
            excluded.append(f'전환·퍼널 축 — {why}')
    return out
