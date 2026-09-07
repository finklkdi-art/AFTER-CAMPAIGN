# -*- coding: utf-8 -*-
"""
인사이트 규칙의 지표 계산 공용부

원칙 두 가지:
  1. 비율 지표(VTR/CTR/CPV/CPC/CPM)는 절대 평균하지 않는다.
     합계에서 다시 계산한다 (노출 가중이 무시되어 값이 왜곡되기 때문).
  2. 임계값 미달 항목은 비교에서 제외한다. 노출 수백 회짜리 라인이
     '최고 효율'로 뽑혀 근거 없는 제안이 만들어지는 것을 막는다.
"""

from typing import Dict, List, Optional, Tuple

from models.campaign_data import MediaPerformance, MetricSet

from .config import InsightConfig


# 값이 클수록 좋은 지표 / 작을수록 좋은 지표
HIGHER_IS_BETTER = ('vtr', 'ctr', 'impressions', 'views', 'clicks')
LOWER_IS_BETTER = ('cpv', 'cpc', 'cpm')


def _s(rows: List[MediaPerformance], attr: str) -> float:
    return sum(getattr(r.metrics, attr) or 0 for r in rows)


def aggregate(rows: List[MediaPerformance]) -> MetricSet:
    """
    행들을 합산하고 비율 지표를 합계 기준으로 재계산한다.

    Returns:
        MetricSet (계산 불가한 비율은 None)
    """
    spend = _s(rows, 'spend')
    billed = _s(rows, 'billed')
    imps = _s(rows, 'impressions')
    views = _s(rows, 'views')
    clicks = _s(rows, 'clicks')
    return MetricSet(
        billed=billed or None,
        spend=spend or None,
        impressions=imps or None,
        views=views or None,
        clicks=clicks or None,
        vtr=(views / imps) if imps and views else None,
        ctr=(clicks / imps) if imps and clicks else None,
        cpm=(spend / imps * 1000) if imps and spend else None,
        cpv=(spend / views) if views and spend else None,
        cpc=(spend / clicks) if clicks and spend else None,
    )


def media_kind(m: MetricSet, cfg: InsightConfig) -> str:
    """영상형 / 배너형 판정 — 조회수가 유효하면 영상형"""
    min_views = cfg.kind('video_min_views') or 1000
    if (m.views or 0) >= min_views and (m.vtr or 0) > 0:
        return 'video'
    return 'banner'


def primary_metric(kind: str, cfg: InsightConfig) -> Tuple[str, str]:
    """
    (단가 지표, 품질 지표) — 영상은 CPV/VTR, 배너는 CPC/CTR
    """
    if kind == 'video':
        return cfg.kind('video_primary_metric'), cfg.kind('video_quality_metric')
    return cfg.kind('banner_primary_metric'), cfg.kind('banner_quality_metric')


def is_comparable(m: MetricSet, kind: str, cfg: InsightConfig) -> bool:
    """비교 대상으로 삼을 만한 물량인지 (임계값 미달 라인 배제)"""
    if (m.spend or 0) < (cfg.th('min_spend') or 0):
        return False
    if (m.impressions or 0) < (cfg.th('min_impressions') or 0):
        return False
    if kind == 'video':
        return (m.views or 0) >= (cfg.th('min_views') or 0)
    return (m.clicks or 0) >= (cfg.th('min_clicks') or 0)


def better(a: Optional[float], b: Optional[float], metric: str) -> bool:
    """지표 방향을 고려해 a 가 b 보다 우수한지"""
    if a is None or b is None:
        return False
    if metric in LOWER_IS_BETTER:
        return a < b
    return a > b


def rank(items: List[Tuple[str, MetricSet]], metric: str) -> List[Tuple[str, MetricSet]]:
    """지표 방향에 맞춰 우수한 순으로 정렬 (값이 없는 항목은 제외)"""
    valid = [(label, m) for label, m in items
             if getattr(m, metric, None) not in (None, 0)]
    reverse = metric in HIGHER_IS_BETTER
    return sorted(valid, key=lambda t: getattr(t[1], metric), reverse=reverse)


def gap_ratio(best: Optional[float], worst: Optional[float],
              metric: str) -> Optional[float]:
    """
    두 값의 격차 배수 (항상 1.0 이상). 계산 불가면 None.

    작을수록 좋은 지표는 worst/best, 클수록 좋은 지표는 best/worst.
    """
    if not best or not worst:
        return None
    if metric in LOWER_IS_BETTER:
        return worst / best if best else None
    return best / worst if worst else None


def saving_pct(best: Optional[float], worst: Optional[float]) -> Optional[float]:
    """단가 절감률 — best 가 worst 대비 몇 % 낮은지 (0.39 = 39% 절감)"""
    if not best or not worst or worst <= 0:
        return None
    return max(0.0, (worst - best) / worst)


def group_by_media(rows: List[MediaPerformance]) -> Dict[str, List[MediaPerformance]]:
    """매체명으로 묶는다 (순서 보존)"""
    out: Dict[str, List[MediaPerformance]] = {}
    for r in rows:
        out.setdefault(r.media, []).append(r)
    return out


def spend_share(part: Optional[float], total: Optional[float]) -> Optional[float]:
    if not part or not total:
        return None
    return part / total
