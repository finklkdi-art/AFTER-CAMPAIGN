# -*- coding: utf-8 -*-
"""
축 1 — 매체·상품별 효율 비교

원천 우선순위:
  1. 일자별 통합 시트의 매체별 Total 블록 (axis='media') — 매체 간 비교
  2. 매체 시트 '상품 별 효율' 표 (axis='product')       — 매체 내 상품 비교

영상형과 배너형은 성격이 달라 한 줄로 비교하지 않는다 (tone-guide 예문 관례:
"영상 매체는 유튜브에서 가장 우수하게 운영, 배너 매체는 네이버 GFA에서 CTR 우수").
"""

from typing import Dict, List, Optional, Tuple

from models.campaign_data import CampaignDataset, Insight, MediaPerformance, MetricSet

from . import metrics as M
from . import phrasing as P
from .config import InsightConfig


def _kind_split(rows: List[MediaPerformance], cfg: InsightConfig
                ) -> Dict[str, List[Tuple[str, MetricSet, MediaPerformance]]]:
    """매체 목록을 영상형/배너형으로 나누고 비교 가능한 것만 남긴다"""
    out: Dict[str, List[Tuple[str, MetricSet, MediaPerformance]]] = {
        'video': [], 'banner': []}
    for r in rows:
        m = r.metrics
        kind = M.media_kind(m, cfg)
        if not M.is_comparable(m, kind, cfg):
            continue
        out[kind].append((r.media, m, r))
    return out


def _kind_label(kind: str) -> str:
    return '영상 매체' if kind == 'video' else '배너 매체'


def _media_insight(kind: str,
                   items: List[Tuple[str, MetricSet, MediaPerformance]],
                   total_spend: Optional[float],
                   cfg: InsightConfig) -> Optional[Insight]:
    """한 유형(영상/배너) 안에서 매체 간 효율 비교 인사이트 1건"""
    if len(items) < (cfg.th('min_compare_items') or 2):
        return None

    cost_metric, quality_metric = M.primary_metric(kind, cfg)
    ranked = M.rank([(label, m) for label, m, _ in items], cost_metric)
    if len(ranked) < 2:
        return None

    best_label, best_m = ranked[0]
    worst_label, worst_m = ranked[-1]
    ratio = M.gap_ratio(getattr(best_m, cost_metric),
                        getattr(worst_m, cost_metric), cost_metric)
    if ratio is None or ratio < (cfg.th('min_gap_ratio') or 1.15):
        return None

    by_label = {label: mp for label, _, mp in items}
    best_mp = by_label.get(best_label)
    share = M.spend_share(best_m.spend, total_spend)

    # 문장에는 매체군 접두를 뗀 표기를 쓰고, 원본은 metrics·출처에 보존한다
    best_name = cfg.media_display(best_label)
    worst_name = cfg.media_display(worst_label)

    # [발견] 수치 먼저, 해석 뒤
    finding = (f'{_kind_label(kind)} 중 {best_name}에서 '
               + P.josa_ro(P.pair(quality_metric,
                                  getattr(best_m, quality_metric),
                                  cost_metric,
                                  getattr(best_m, cost_metric), cfg))
               + ' 가장 우수한 효율 기록')

    # [근거]
    evidence: List[str] = []
    saving = M.saving_pct(getattr(best_m, cost_metric),
                          getattr(worst_m, cost_metric))
    saving_text = P.saving_phrase(saving, cost_metric, cfg)
    if saving_text:
        evidence.append(
            f'{worst_name} {P.metric_value(cost_metric, getattr(worst_m, cost_metric), cfg)} '
            f'대비 {saving_text} 수준으로 운영')
    group_m = M.aggregate([mp for _, _, mp in items])
    evidence.append(
        f'{_kind_label(kind)} 전체 {P.metric_value(cost_metric, getattr(group_m, cost_metric), cfg)} · '
        f'{P.metric_value(quality_metric, getattr(group_m, quality_metric), cfg)} '
        f'({len(items)}개 매체 합계 기준)')
    if share is not None:
        evidence.append(
            f'{best_name} 집행 {P.eok(best_m.spend)} · '
            f'{_kind_label(kind)} 내 예산 비중 {P.share_rate(share)}')

    # [제안] 비중이 낮으면 확대, 이미 높으면 유지·집중
    if share is not None and share < 0.05:
        rec = (f'{best_name} 소액 물량에서 확인된 효율 우위 — '
               f'차기 캠페인 시 테스트 물량 확대 후 본물량 편성 검토 권고')
    elif share is not None and share < 0.4:
        rec = (f'차기 캠페인 시 {best_name} 예산 비중 확대 운영 권고 — '
               f'{cfg.metric_label(cost_metric)} 효율 우위 구간에 물량 집중')
    else:
        rec = (f'{cfg.metric_label(cost_metric)} 효율 최우선 시 '
               f'{best_name} 중심 운영 유지 권고')

    sources = P.join_sources([
        P.source_label(best_mp.source.file_name, best_mp.section)
        if best_mp else ''])

    return Insight(
        axis='media',
        finding=finding,
        recommendation=rec,
        evidence=evidence[:cfg.th('max_evidence_per_insight') or 3],
        sources=sources,
        # 격차 배수를 그대로 쓰면 28배 같은 극단값이 다른 축을 밀어낸다 —
        # 기여 상한을 두어 축 간 비교가 가능한 범위로 정규화한다
        priority=min(float(ratio), 4.0) * (1.0 + (share or 0)),
        metrics={'kind': kind,
                 'best': best_name, 'worst': worst_name,      # 문장 표기
                 'best_raw': best_label, 'worst_raw': worst_label,
                 'cost_metric': cost_metric, 'gap_ratio': ratio,
                 'best_value': getattr(best_m, cost_metric),
                 'best_share': share},
    )


def _product_insights(dataset: CampaignDataset,
                      cfg: InsightConfig) -> List[Insight]:
    """
    매체별 상품 간 효율 격차 — 조건을 넘는 매체를 모두 내보낸다.

    이전에는 전 매체를 훑고 최고 1건만 돌려주어, 임계값을 낮춰도 도출량이
    늘지 않고 '어느 것이 뽑히나'만 바뀌었다. 게재 상한이 없어진 뒤로는
    매체별로 각각 내보내고 취사선택은 Stage 1.5 검증에 맡긴다.
    """
    dr = dataset.daily_report
    if not dr:
        return []
    rows = [r for r in dr.media_performance if r.axis == 'product']
    if not rows:
        return []

    found: List[Insight] = []
    for media, group in M.group_by_media(rows).items():
        items = [(r.product or r.media, r.metrics, r) for r in group
                 if r.product]
        if len(items) < 2:
            continue
        kind = M.media_kind(M.aggregate(group), cfg)
        cost_metric, quality_metric = M.primary_metric(kind, cfg)
        usable = [(label, m) for label, m, _ in items
                  if M.is_comparable(m, kind, cfg)]
        ranked = M.rank(usable, cost_metric)
        if len(ranked) < 2:
            continue
        best_label, best_m = ranked[0]
        worst_label, worst_m = ranked[-1]
        # 표기가 같은 두 행(타겟팅만 다른 동일 상품)을 비교하면
        # 'A에서 … A 대비 우수' 처럼 읽히는 문장이 된다 — 문장화하지 않는다
        if (best_label or '').strip() == (worst_label or '').strip():
            continue
        ratio = M.gap_ratio(getattr(best_m, cost_metric),
                            getattr(worst_m, cost_metric), cost_metric)
        if ratio is None or ratio < (cfg.th('min_gap_ratio') or 1.15):
            continue

        by_label = {label: mp for label, _, mp in items}
        mp = by_label.get(best_label)
        media_name = cfg.media_display(media)
        saving = M.saving_pct(getattr(best_m, cost_metric),
                              getattr(worst_m, cost_metric))
        evidence = [
            f'{P.short_label(best_label, 34)} '
            f'{P.pair(quality_metric, getattr(best_m, quality_metric), cost_metric, getattr(best_m, cost_metric), cfg)}',
            f'{P.short_label(worst_label, 34)} '
            f'{P.pair(quality_metric, getattr(worst_m, quality_metric), cost_metric, getattr(worst_m, cost_metric), cfg)}',
        ]
        saving_text = P.saving_phrase(saving, cost_metric, cfg)
        if saving_text:
            evidence.append(f'상품 간 {saving_text} 격차 확인')

        candidate = Insight(
            axis='media',
            finding=(f'{media_name} 상품 중 {best_label}에서 '
                     + P.josa_ro(P.pair(quality_metric,
                                        getattr(best_m, quality_metric),
                                        cost_metric,
                                        getattr(best_m, cost_metric), cfg))
                     + f' {worst_label} 대비 우수한 효율 기록'),
            recommendation=(f'{media_name} 운영 시 {best_label} 예산 집중 권고 — '
                            f'{worst_label}는 보조 물량으로 조정 검토'),
            evidence=evidence[:cfg.th('max_evidence_per_insight') or 3],
            sources=P.join_sources(
                [P.source_label(mp.source.file_name, mp.section)] if mp else []),
            priority=min(float(ratio), 3.0),
            metrics={'media': media_name, 'media_raw': media,
                     'best': best_label, 'worst': worst_label,
                     'cost_metric': cost_metric, 'gap_ratio': ratio},
        )
        found.append(candidate)

    found.sort(key=lambda i: i.priority, reverse=True)
    return found


def generate(dataset: CampaignDataset, cfg: InsightConfig,
             excluded: List[str]) -> List[Insight]:
    """매체·상품 효율 인사이트를 도출한다"""
    dr = dataset.daily_report
    if not dr:
        excluded.append('매체 효율 비교 — 데일리리포트 실적 미확보')
        return []

    rows = dr.media_totals
    origin = '일자별 통합 매체별 Total'
    if not rows:
        # 매체별 블록이 없으면 상품별 표를 매체 단위로 합산해 대체
        grouped = M.group_by_media(
            [r for r in dr.media_performance if r.axis == 'product'])
        rows = [MediaPerformance(media=name, axis='media',
                                 section='상품 별 효율 합산',
                                 metrics=M.aggregate(group),
                                 source=group[0].source)
                for name, group in grouped.items()]
        origin = '상품별 표 합산'
    if not rows:
        excluded.append('매체 효율 비교 — 매체별 실적 원천 미확보')
        return []

    total_spend = sum(r.metrics.spend or 0 for r in rows) or None
    split = _kind_split(rows, cfg)

    out: List[Insight] = []
    for kind in ('video', 'banner'):
        items = split[kind]
        if len(items) < 2:
            if items:
                excluded.append(
                    f'{_kind_label(kind)} 효율 비교 — 비교 가능 매체 {len(items)}개 (2개 이상 필요)')
            continue
        ins = _media_insight(kind, items, total_spend, cfg)
        if ins:
            ins.metrics['origin'] = origin
            out.append(ins)
        else:
            excluded.append(
                f'{_kind_label(kind)} 효율 비교 — 매체 간 격차가 기준({cfg.th("min_gap_ratio")}배) 미만')

    product_list = _product_insights(dataset, cfg)
    if product_list:
        out.extend(product_list)
    else:
        excluded.append('매체 내 상품 효율 비교 — 격차 기준을 넘는 매체 없음')

    return out
