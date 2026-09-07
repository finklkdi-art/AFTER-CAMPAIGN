# -*- coding: utf-8 -*-
"""
차기 캠페인 전략 방향 — 4개 영역

  매체 운영 / 타겟팅 / 소재·메시지 / 예산 배분

각 항목은 근거(basis)에 수치를 반드시 동반한다. 근거를 만들 수 없는 영역은
문항을 만들지 않고 제외 사유를 남긴다 (데이터 없는 긍정 포장 금지).
"""

from typing import Dict, List, Optional

from models.campaign_data import (
    CampaignDataset, Insight, MediaPerformance, StrategyItem,
)

from . import metrics as M
from . import phrasing as P
from .config import InsightConfig


AREA_MEDIA = '매체 운영'
AREA_TARGETING = '타겟팅'
AREA_CREATIVE = '소재·메시지'
AREA_BUDGET = '예산 배분'


def _from_media(insights: List[Insight], cfg: InsightConfig
                ) -> Optional[StrategyItem]:
    rows = [i for i in insights if i.axis == 'media' and i.metrics.get('best')]
    if not rows:
        return None
    best = max(rows, key=lambda i: i.priority)
    m = best.metrics
    label = cfg.metric_label(m.get('cost_metric', 'cpv'))
    share = m.get('best_share')

    # 소액 테스트 물량에서 나온 효율 우위를 '중심 운영' 으로 적으면 과대 서술이 된다.
    # 항목을 빼지는 않고(비중 하한 미설정) 표현을 물량 규모에 맞춘다.
    if share is not None and share < 0.05:
        direction = f'{m["best"]} 테스트 물량 확대 후 본물량 편성 검토'
        basis_tail = f' (집행 비중 {P.share_rate(share)} 기준)'
    else:
        direction = f'{m["best"]} 중심 운영 유지 및 물량 확대'
        basis_tail = ''
    return StrategyItem(
        area=AREA_MEDIA,
        direction=direction,
        basis=(f'{label} 기준 {P.with_particle(m["best"])} {m["worst"]} 대비 '
               f'{m.get("gap_ratio", 0):.1f}배 효율 우위' + basis_tail),
        sources=list(best.sources),
    )


def _from_targeting(insights: List[Insight]) -> Optional[StrategyItem]:
    rows = [i for i in insights if i.axis == 'targeting']
    if not rows:
        return None
    best = max(rows, key=lambda i: i.priority)
    m = best.metrics
    if m.get('best_type'):
        direction = (f'{m["best_type"]} 타겟 비중 확대 및 '
                     f'{m.get("worst_type", "타 유형")} 타겟 동시 테스트')
        basis = (f'{m.get("media_count", 1)}개 매체에서 {m["best_type"]} 타겟이 '
                 f'{m.get("worst_type", "")} 타겟 대비 효율 우위 확인')
    else:
        direction = f'{m.get("best", "")} 라인 비중 확대'
        raw = m.get('best_raw', '')
        basis = (f'{m.get("media", "")} 내 타겟팅 라인 간 '
                 f'{m.get("gap_ratio", 0):.1f}배 효율 격차 확인'
                 + (f' (최우수 라인 {raw[:40]})' if raw else ''))
    return StrategyItem(area=AREA_TARGETING, direction=direction,
                        basis=basis, sources=list(best.sources))


def _from_creative(dataset: CampaignDataset, cfg: InsightConfig
                   ) -> Optional[StrategyItem]:
    """소재별 실적표(axis='creative')가 있을 때만 방향을 제시한다"""
    dr = dataset.daily_report
    if not dr:
        return None
    rows = [r for r in dr.media_performance if r.axis == 'creative' and r.creative]
    if len(rows) < 2:
        return None

    kind = M.media_kind(M.aggregate(rows), cfg)
    cost_metric, quality_metric = M.primary_metric(kind, cfg)

    # 소재명으로 합산 (같은 소재가 여러 상품에 걸쳐 운영되는 구조)
    by_creative: Dict[str, List[MediaPerformance]] = {}
    for r in rows:
        by_creative.setdefault(r.creative, []).append(r)
    if len(by_creative) < 2:
        return None

    items = [(name, M.aggregate(group)) for name, group in by_creative.items()]
    usable = [(n, m) for n, m in items if M.is_comparable(m, kind, cfg)]
    ranked = M.rank(usable, quality_metric)
    if len(ranked) < 2:
        return None

    best_name, best_m = ranked[0]
    worst_name, worst_m = ranked[-1]
    ratio = M.gap_ratio(getattr(best_m, quality_metric),
                        getattr(worst_m, quality_metric), quality_metric)
    if ratio is None or ratio < 1.05:
        return None

    return StrategyItem(
        area=AREA_CREATIVE,
        direction=f'{best_name} 소재 축 중심 재편 및 우수 소재 우선 노출',
        basis=(f'{best_name} '
               f'{P.metric_value(quality_metric, getattr(best_m, quality_metric), cfg)} vs '
               f'{worst_name} '
               f'{P.metric_value(quality_metric, getattr(worst_m, quality_metric), cfg)} '
               f'({ratio:.1f}배 격차)'),
        sources=P.join_sources([P.source_label(rows[0].source.file_name,
                                               rows[0].section)]),
    )


def _from_budget(dataset: CampaignDataset, insights: List[Insight],
                 cfg: InsightConfig) -> Optional[StrategyItem]:
    """매체별 예산 비중과 효율을 교차하여 배분 권고"""
    dr = dataset.daily_report
    if not dr or not dr.media_totals:
        return None
    rows = dr.media_totals
    total = sum(r.metrics.spend or 0 for r in rows)
    if not total:
        return None

    # 효율 우수 매체 (매체 인사이트에서 채택된 것)
    media_insights = [i for i in insights
                      if i.axis == 'media' and i.metrics.get('best')]
    best_names = [i.metrics['best'] for i in media_insights]
    best_name = best_names[0] if best_names else None
    if not best_name:
        return None

    # 매체 인사이트의 best 는 표기 정리된 이름이므로 같은 기준으로 비교한다
    share = {cfg.media_display(r.media): (r.metrics.spend or 0) / total
             for r in rows}
    best_share = share.get(best_name)
    if best_share is None:
        return None

    # 재검토 대상은 '효율 하위로 지목된 매체' 중 비중이 가장 큰 것.
    # 단순히 최대 비중 매체를 지목하면, 다른 축에서 최우수로 뽑힌 매체를
    # 재검토 대상으로 함께 적어 인사이트끼리 모순되는 문장이 만들어진다.
    worst_names = [i.metrics.get('worst') for i in media_insights
                   if i.metrics.get('worst')]
    review = [(n, share[n]) for n in worst_names
              if n in share and n not in best_names]
    if not review:
        review = [(n, s) for n, s in share.items() if n not in best_names]

    if review:
        review_name, review_share = max(review, key=lambda kv: kv[1])
        direction = (f'{best_name} 비중 {P.share_rate(best_share)} → 확대, '
                     f'{review_name} 비중 {P.share_rate(review_share)} → 효율 재검토')
    else:
        direction = (f'{best_name} 비중 유지({P.share_rate(best_share)}) 및 '
                     f'하위 효율 매체 정리')
    return StrategyItem(
        area=AREA_BUDGET,
        direction=direction,
        basis=(f'총 집행 {P.eok(total)} 기준 매체별 예산 비중 · '
               f'효율 우위 매체 {best_name}'),
        sources=P.join_sources([P.source_label(dr.source_file, '일자별 통합')]),
    )


def generate(dataset: CampaignDataset, insights: List[Insight],
             cfg: InsightConfig, excluded: List[str]) -> List[StrategyItem]:
    """인사이트와 실적을 근거로 차기 전략 방향을 구성한다"""
    builders = (
        (AREA_MEDIA, lambda: _from_media(insights, cfg)),
        (AREA_TARGETING, lambda: _from_targeting(insights)),
        (AREA_CREATIVE, lambda: _from_creative(dataset, cfg)),
        (AREA_BUDGET, lambda: _from_budget(dataset, insights, cfg)),
    )
    out: List[StrategyItem] = []
    for area, build in builders:
        try:
            item = build()
        except Exception as e:                  # 규칙 오류로 파이프라인을 멈추지 않음
            excluded.append(f'차기 전략 [{area}] 생성 실패: {e}')
            continue
        if item:
            out.append(item)
        else:
            excluded.append(f'차기 전략 [{area}] — 근거 데이터 미확보로 미기재')
    return out[:cfg.th('max_strategy_items') or 4]
