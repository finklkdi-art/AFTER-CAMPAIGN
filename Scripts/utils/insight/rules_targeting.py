# -*- coding: utf-8 -*-
"""
축 2 — 타겟팅별 비교

원천: 매체 시트 '타겟팅 별 효율' 표 (axis='targeting')

실제 보고서의 Lesson Learned 핵심 축이다.
  "유튜브 및 META, 관심사 타겟팅 라인 대비 데모 타겟에서 VTR, CPV 모두 우수한 성과 기록"

타겟팅 표기(MF3554∩관심사+구매의도 / MF2554 ...)를 Config 의 키워드로 유형화해
여러 매체에서 같은 유형이 우세한 경우를 더 강한 신호로 취급한다.
"""

from typing import Dict, List, Optional, Tuple

from models.campaign_data import CampaignDataset, Insight, MetricSet

from . import metrics as M
from . import phrasing as P
from .config import InsightConfig


def _type_label(label: str, cfg: InsightConfig) -> str:
    """타겟팅 유형 표기 — 분류되면 '데모 타겟', 아니면 원문"""
    kind = cfg.classify_targeting(label)
    return f'{kind} 타겟' if kind else label


def _per_media(dataset: CampaignDataset, cfg: InsightConfig
               ) -> List[Tuple[str, str, str, MetricSet, MetricSet, float, str]]:
    """
    매체별 타겟팅 우열.

    Returns:
        [(매체, 최우수 라인, 최하위 라인, 최우수 지표, 최하위 지표,
          격차 배수, 단가지표)]
    """
    dr = dataset.daily_report
    if not dr:
        return []
    # 라인명이 '-' / '_' / 공백뿐인 행은 문장에서 "라인 중 -에서" 처럼 읽혀
    # 근거가 사라진 문장이 된다. 비교 대상에서 제외한다.
    def _named(label: str) -> bool:
        t = (label or '').strip().strip('-_·.')
        return len(t) > 0

    rows = [r for r in dr.media_performance
            if r.axis == 'targeting' and _named(r.targeting)]
    out = []
    for media, group in M.group_by_media(rows).items():
        kind = M.media_kind(M.aggregate(group), cfg)
        cost_metric, _ = M.primary_metric(kind, cfg)
        usable = [(r.targeting, r.metrics) for r in group
                  if M.is_comparable(r.metrics, kind, cfg)]
        ranked = M.rank(usable, cost_metric)
        if len(ranked) < 2:
            continue
        (best_label, best_m), (worst_label, worst_m) = ranked[0], ranked[-1]
        ratio = M.gap_ratio(getattr(best_m, cost_metric),
                            getattr(worst_m, cost_metric), cost_metric)
        if ratio is None or ratio < (cfg.th('min_gap_ratio') or 1.15):
            continue
        out.append((media, best_label, worst_label, best_m, worst_m,
                    ratio, cost_metric))
    return out


def generate(dataset: CampaignDataset, cfg: InsightConfig,
             excluded: List[str]) -> List[Insight]:
    """타겟팅 비교 인사이트를 도출한다"""
    dr = dataset.daily_report
    if not dr:
        return []
    if not any(r.axis == 'targeting' for r in dr.media_performance):
        excluded.append('타겟팅 비교 — 타겟팅별 실적표 미확보')
        return []

    findings = _per_media(dataset, cfg)
    if not findings:
        excluded.append(
            f'타겟팅 비교 — 매체별 타겟팅 라인이 2개 미만이거나 격차가 기준'
            f'({cfg.th("min_gap_ratio")}배) 미만')
        return []

    # 유형이 분류된 건들에서 같은 유형이 2개 이상 매체에서 우세하면 통합 문장
    type_wins: Dict[str, List[tuple]] = {}
    for row in findings:
        media, best_label, worst_label = row[0], row[1], row[2]
        best_type = cfg.classify_targeting(best_label)
        worst_type = cfg.classify_targeting(worst_label)
        if best_type and worst_type and best_type != worst_type:
            type_wins.setdefault((best_type, worst_type), []).append(row)

    quality_of = {'cpv': 'vtr', 'cpc': 'ctr'}
    out: List[Insight] = []

    for (best_type, worst_type), rows in sorted(
            type_wins.items(), key=lambda kv: -len(kv[1])):
        if len(rows) < 2:
            continue
        media_names = ' 및 '.join(cfg.media_display(r[0]) for r in rows[:3])
        cost_metric = rows[0][6]
        quality_metric = quality_of.get(cost_metric, 'vtr')
        evidence = []
        for media, best_label, worst_label, best_m, worst_m, ratio, cm in rows[:3]:
            evidence.append(
                f'{cfg.media_display(media)} {P.short_label(best_label, 22)} '
                f'{P.pair(quality_metric, getattr(best_m, quality_metric), cm, getattr(best_m, cm), cfg)} / '
                f'{P.short_label(worst_label, 22)} '
                f'{P.pair(quality_metric, getattr(worst_m, quality_metric), cm, getattr(worst_m, cm), cfg)}')
        out.append(Insight(
            axis='targeting',
            finding=(f'{media_names}, {worst_type} 타겟팅 라인 대비 '
                     f'{best_type} 타겟에서 '
                     f'{cfg.metric_label(quality_metric)}·{cfg.metric_label(cost_metric)} '
                     f'모두 우수한 성과 기록'),
            recommendation=(f'차기 캠페인 시 {best_type} 타겟 비중 확대 및 '
                            f'{worst_type} 타겟 동시 테스트 운영 권고'),
            evidence=evidence[:cfg.th('max_evidence_per_insight') or 3],
            sources=P.join_sources([
                P.source_label(r.source.file_name, r.section)
                for r in dr.media_performance if r.axis == 'targeting'][:1]),
            priority=6.0 + len(rows),          # 여러 매체 공통 신호를 최우선
            metrics={'best_type': best_type, 'worst_type': worst_type,
                     'media_count': len(rows)},
        ))
        break                                   # 통합 문장은 1건으로 충분

    if not out:
        # 통합 신호가 없으면 격차가 가장 큰 단일 매체 건을 채택
        media, best_label, worst_label, best_m, worst_m, ratio, cm = max(
            findings, key=lambda r: r[5])
        quality_metric = quality_of.get(cm, 'vtr')
        saving = M.saving_pct(getattr(best_m, cm), getattr(worst_m, cm))
        evidence = [
            f'{P.short_label(best_label, 34)} '
            f'{P.pair(quality_metric, getattr(best_m, quality_metric), cm, getattr(best_m, cm), cfg)}',
            f'{P.short_label(worst_label, 34)} '
            f'{P.pair(quality_metric, getattr(worst_m, quality_metric), cm, getattr(worst_m, cm), cfg)}',
        ]
        saving_text = P.saving_phrase(saving, cm, cfg)
        if saving_text:
            evidence.append(f'타겟팅 라인 간 {saving_text} 격차 확인')
        media_name = cfg.media_display(media)
        out.append(Insight(
            axis='targeting',
            finding=(f'{media_name} 타겟팅 라인 중 {_type_label(best_label, cfg)}에서 '
                     + P.josa_ro(P.pair(quality_metric,
                                        getattr(best_m, quality_metric),
                                        cm, getattr(best_m, cm), cfg))
                     + ' 우수한 성과 기록'),
            recommendation=(f'{media_name} 운영 시 {_type_label(best_label, cfg)} 라인 '
                            f'비중 확대 권고'),
            evidence=evidence[:cfg.th('max_evidence_per_insight') or 3],
            sources=P.join_sources([
                P.source_label(r.source.file_name, r.section)
                for r in dr.media_performance
                if r.axis == 'targeting' and r.media == media][:1]),
            priority=3.0 + min(float(ratio), 3.0),
            metrics={'media': media_name, 'media_raw': media,
                     'best': _type_label(best_label, cfg),   # 전략 카드 표기용
                     'best_raw': best_label,                 # 원문 라인명 보존
                     'worst': _type_label(worst_label, cfg),
                     'worst_raw': worst_label,
                     'gap_ratio': ratio},
        ))

    return out
