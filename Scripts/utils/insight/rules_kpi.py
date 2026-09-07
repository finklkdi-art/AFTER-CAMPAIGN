# -*- coding: utf-8 -*-
"""
축 3 — 목표 대비 달성률 (Full 모드 전용)

원천: 포스트바이 'KPI 달성 현황' / '목표 대비 달성율' 표 (kpi_targets)

이상치 가드:
  실측에 목표 6만회 대비 실적 562만회(9,367%) 같은 행이 있다. 목표 산정 기준이
  다른 케이스로, 그대로 문장화하면 "9,367% 초과 달성" 같은 허위 강조가 된다.
  max_achievement_rate 를 넘는 행은 인사이트에서 제외하고 사유를 남긴다.

미달 항목도 숨기지 않는다 (tone-guide 5장: 부정 지표도 원인과 함께 건조하게).
"""

from typing import Dict, List, Optional

from models.campaign_data import CampaignDataset, Insight, KpiTarget

from . import metrics as M
from . import phrasing as P
from .config import InsightConfig


# 포스트바이 KPI 표기 → 표시 라벨
_KPI_LABELS = {
    'impression': '노출', 'imps': '노출',
    'view': '조회', 'click': '클릭',
}


def _label(name: str) -> str:
    return _KPI_LABELS.get((name or '').strip().lower(), name or '-')


def _valid_rows(targets: List[KpiTarget], cfg: InsightConfig,
                excluded: List[str]) -> List[KpiTarget]:
    """이상치·불완전 행을 걸러낸다"""
    cap = cfg.th('max_achievement_rate') or 5.0
    out: List[KpiTarget] = []
    dropped: List[str] = []
    for t in targets:
        if not t.target or t.target <= 0 or t.actual is None:
            dropped.append(f'{t.product or t.media} {_label(t.kpi_name)} (목표·실적 결손)')
            continue
        r = t.achievement_rate
        if r is None and t.target:
            r = t.actual / t.target
        if r is None or r <= 0:
            dropped.append(f'{t.product or t.media} {_label(t.kpi_name)} (달성률 산출 불가)')
            continue
        if r > cap:
            dropped.append(
                f'{t.product or t.media} {_label(t.kpi_name)} '
                f'달성률 {P.rate(r)} — 목표 산정 기준 상이 의심')
            continue
        t.achievement_rate = r
        out.append(t)
    if dropped:
        excluded.append('KPI 달성률 제외 ' + f'{len(dropped)}건: ' + ' / '.join(dropped[:4]))
    return out


def _campaign_level(rows: List[KpiTarget]) -> List[KpiTarget]:
    """
    캠페인 단위 행(상품 구분이 없는 Digital 합계)을 우선 사용한다.
    없으면 전체 행을 쓴다.
    """
    top = [t for t in rows if not (t.product or '').strip()]
    return top or rows


def _plan_vs_actual_cpv(dataset: CampaignDataset,
                        cfg: InsightConfig) -> Optional[str]:
    """미디어믹스 예상 조회 기준 계획 CPV 와 실제 CPV 를 비교한 근거 문구"""
    mm, dr = dataset.media_mix, dataset.daily_report
    if not mm or not dr:
        return None
    plan = mm.plan_totals()
    plan_views, plan_budget = plan.get('views'), plan.get('budget')
    if not plan_views or not plan_budget:
        return None
    plan_cpv = plan_budget / plan_views
    actual_cpv = dr.total.cpv
    if not actual_cpv or actual_cpv <= 0:
        return None
    saving = M.saving_pct(actual_cpv, plan_cpv)
    text = P.saving_phrase(saving, 'cpv', cfg)
    if not text:
        return None
    return (f'계획 {P.metric_value("cpv", plan_cpv, cfg)} 대비 '
            f'실집행 {P.metric_value("cpv", actual_cpv, cfg)}로 {text}')


def generate(dataset: CampaignDataset, cfg: InsightConfig,
             excluded: List[str]) -> List[Insight]:
    """목표 대비 달성률 인사이트를 도출한다"""
    pb = dataset.postbuy
    if not pb or not pb.kpi_targets:
        excluded.append('목표 대비 달성률 — 포스트바이 확정 목표치 미확보 (Lite 모드)')
        return []

    rows = _valid_rows(list(pb.kpi_targets), cfg, excluded)
    if len(rows) < (cfg.th('min_achievement_items') or 2):
        excluded.append('목표 대비 달성률 — 유효 KPI 행 부족')
        return []

    top = _campaign_level(rows)

    # 지표별 최고 달성률 (같은 지표가 Phase 별로 여러 건일 수 있음)
    by_kpi: Dict[str, List[KpiTarget]] = {}
    for t in top:
        by_kpi.setdefault(_label(t.kpi_name), []).append(t)

    over = {k: v for k, v in by_kpi.items()
            if all((t.achievement_rate or 0) >= 1.0 for t in v)}
    under = {k: v for k, v in by_kpi.items()
             if any((t.achievement_rate or 0) < 1.0 for t in v)}

    best_kpi, best_row = None, None
    for k, v in by_kpi.items():
        cand = max(v, key=lambda t: t.achievement_rate or 0)
        if best_row is None or (cand.achievement_rate or 0) > (best_row.achievement_rate or 0):
            best_kpi, best_row = k, cand

    kpi_names = ' / '.join(by_kpi.keys())
    if not under:
        finding = (f'제안 대비 {kpi_names} 지표에서 전 수치 초과 달성 — '
                   f'특히 {best_kpi}에서 {P.rate(best_row.achievement_rate)} 달성')
    else:
        under_text = ' · '.join(
            f'{k} {P.rate(min((t.achievement_rate or 0) for t in v))}'
            for k, v in under.items())
        finding = (f'{kpi_names} 중 {len(over)}개 지표 초과 달성, '
                   + P.josa_ro(under_text) + ' 목표 미달 확인')

    evidence: List[str] = []
    for k, v in by_kpi.items():
        t = max(v, key=lambda x: x.achievement_rate or 0)
        scope = f'[{t.scope}] ' if t.scope else ''
        evidence.append(
            f'{scope}{k} 목표 {P.cnt(t.target)} → 실적 {P.cnt(t.actual)} '
            f'({P.rate(t.achievement_rate)})')
    cpv_text = _plan_vs_actual_cpv(dataset, cfg)
    if cpv_text:
        evidence.append(cpv_text)

    if not under:
        rec = ('차기 캠페인 목표 상향 재산정 권고 — '
               '실집행 실적을 기준선으로 반영하여 목표 현실화 필요')
    else:
        rec = (f'{" · ".join(under.keys())} 지표의 목표 산정 기준 재점검 권고 — '
               f'매체 믹스 및 단가 가정 재검토 필요')

    return [Insight(
        axis='kpi',
        finding=finding,
        recommendation=rec,
        evidence=evidence[:cfg.th('max_evidence_per_insight') or 3],
        sources=P.join_sources([P.source_label(pb.source_file, 'KPI 달성 현황')]),
        priority=8.0,                      # 목표 대비 성과는 보고의 핵심
        metrics={'kpi_count': len(by_kpi), 'under': list(under.keys()),
                 'best_kpi': best_kpi,
                 'best_rate': best_row.achievement_rate if best_row else None},
    )]
