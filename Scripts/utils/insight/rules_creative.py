# -*- coding: utf-8 -*-
"""
축 D — 크리에이티브 (소재별·포맷별 기여도)

원천: 매체 시트 '상품별 × 소재별 효율' 표 (MediaPerformance.axis == 'creative')
      + 미디어믹스 PlanLine.creative (계획된 소재 = 의도)

파서가 이미 소재별 실적 행을 뽑고 있으나 지금까지 이를 읽는 규칙이 없었다.
파서 수정 없이 축 하나를 통째로 확보하는 지점이다.

도출 관점 3가지
  1. 소재 간 효율 격차      — 같은 매체 안에서 어떤 소재가 성과를 냈는가
  2. 포맷별 기여도          — 영상/이미지/배너 등 포맷 축의 성과 차이
  3. 소재 다양성 · 피로도   — 단일 소재 장기 운영 여부 (계획축 대조)
"""

from typing import Dict, List, Optional, Tuple

from models.campaign_data import (
    CampaignDataset, Insight, MediaPerformance, MetricSet)

from . import axes
from . import metrics as M
from . import phrasing as P
from .config import InsightConfig

# 소재 표기 → 포맷 (운영 중 바뀔 값이라 향후 Config 외부화 대상)
_FORMAT_WORDS: Dict[str, Tuple[str, ...]] = {
    '영상': ('영상', '비디오', 'video', '필름', 'film', '틱톡', 'shorts', '쇼츠',
             '인스트림', 'instream', 'trueview', '범퍼', 'bumper', '30s', '15s', '6s'),
    '이미지': ('이미지', 'image', '배너', 'banner', '비즈보드', 'gfa', 'da',
               '썸네일', '카드', '피드'),
    '인플루언서': ('인플루언서', 'influencer', '브랜디드', '협찬', '리뷰'),
}


def _format_of(label: str) -> str:
    """소재 표기에서 포맷을 판정 (모르면 빈 문자열)"""
    low = (label or '').lower()
    for fmt, words in _FORMAT_WORDS.items():
        if any(w.lower() in low for w in words):
            return fmt
    return ''


def _creative_rows(dataset: CampaignDataset) -> List[MediaPerformance]:
    dr = dataset.daily_report
    if not dr:
        return []
    return [r for r in dr.media_performance
            if r.axis == 'creative' and (r.creative or '').strip()]


# ─────────────────────────── 1. 소재 간 효율 격차

def _creative_gaps(rows: List[MediaPerformance],
                   cfg: InsightConfig) -> List[Insight]:
    """매체별 소재 간 격차 — 조건을 넘는 매체를 모두 내보낸다"""
    found: List[Insight] = []

    for media, group in M.group_by_media(rows).items():
        items = [(r.creative, r.metrics, r) for r in group if r.creative]
        if len(items) < (cfg.th('min_compare_items') or 2):
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
        # 같은 소재명끼리 비교하면 'A에서 … A 대비' 가 되어 근거가 사라진다
        if (best_label or '').strip() == (worst_label or '').strip():
            continue
        ratio = M.gap_ratio(getattr(best_m, cost_metric),
                            getattr(worst_m, cost_metric), cost_metric)
        if ratio is None or ratio < (cfg.th('min_gap_ratio') or 1.15):
            continue

        by_label = {label: mp for label, _, mp in items}
        mp = by_label.get(best_label)
        media_name = cfg.media_display(media)
        best_short = P.short_label(best_label, 30)
        worst_short = P.short_label(worst_label, 30)
        saving = M.saving_pct(getattr(best_m, cost_metric),
                              getattr(worst_m, cost_metric))

        evidence = [
            f'{best_short} '
            f'{P.pair(quality_metric, getattr(best_m, quality_metric), cost_metric, getattr(best_m, cost_metric), cfg)}',
            f'{worst_short} '
            f'{P.pair(quality_metric, getattr(worst_m, quality_metric), cost_metric, getattr(worst_m, cost_metric), cfg)}',
        ]
        saving_text = P.saving_phrase(saving, cost_metric, cfg)
        if saving_text:
            evidence.append(f'소재 간 {saving_text} 격차 확인 ({len(items)}종 비교)')

        candidate = Insight(
            axis=axes.D_CREATIVE,
            pattern='P2',
            finding=(f'{media_name} 소재 중 {best_short}에서 '
                     + P.josa_ro(P.pair(quality_metric,
                                        getattr(best_m, quality_metric),
                                        cost_metric,
                                        getattr(best_m, cost_metric), cfg))
                     + ' 최우수 효율 기록'),
            recommendation=(
                f'차기 캠페인 시 {best_short} 계열 소재 비중 확대 편성 권장 — '
                f'{P.with_particle(worst_short, "은/는")} 보조 물량 또는 교체 검토'),
            evidence=evidence[:cfg.th('max_evidence_per_insight') or 3],
            sources=P.join_sources(
                [P.source_label(mp.source.file_name, mp.section)] if mp else []),
            priority=min(float(ratio), 3.0) + 0.2,
            metrics={'media': media_name, 'media_raw': media,
                     'best': best_label, 'worst': worst_label,
                     'best_format': _format_of(best_label),
                     'cost_metric': cost_metric, 'gap_ratio': ratio,
                     'creative_count': len(items)},
        )
        found.append(candidate)

    found.sort(key=lambda i: i.priority, reverse=True)
    return found


# ─────────────────────────── 2. 포맷별 기여도

def _format_contribution(rows: List[MediaPerformance],
                         cfg: InsightConfig) -> Optional[Insight]:
    """영상/이미지/인플루언서 등 포맷 축으로 묶어 기여도 비교"""
    buckets: Dict[str, List[MediaPerformance]] = {}
    for r in rows:
        fmt = _format_of(r.creative)
        if fmt:
            buckets.setdefault(fmt, []).append(r)
    if len(buckets) < 2:
        return None

    agg: List[Tuple[str, MetricSet, int]] = [
        (fmt, M.aggregate(group), len(group)) for fmt, group in buckets.items()]
    total_spend = sum((m.spend or 0) for _, m, _ in agg) or None

    # 클릭 기여를 공통 축으로 본다 (포맷 간 CPV/CPC 는 성격이 달라 직접 비교 불가)
    scored = [(fmt, m, n) for fmt, m, n in agg if (m.clicks or 0) > 0]
    if len(scored) < 2:
        return None
    scored.sort(key=lambda x: (x[1].clicks or 0), reverse=True)

    top_fmt, top_m, top_n = scored[0]
    total_clicks = sum((m.clicks or 0) for _, m, _ in scored) or None
    click_share = ((top_m.clicks or 0) / total_clicks) if total_clicks else None
    spend_share = M.spend_share(top_m.spend, total_spend)

    evidence: List[str] = []
    for fmt, m, n in scored[:3]:
        share = ((m.clicks or 0) / total_clicks) if total_clicks else None
        evidence.append(
            f'{fmt} {n}종 · 클릭 {P.cnt(m.clicks)}'
            + (f' (기여 {P.share_rate(share)})' if share is not None else '')
            + (f' · 집행 {P.eok(m.spend)}' if m.spend else ''))

    # 예산 비중보다 기여가 높으면 '효율 우위', 낮으면 '재배분 여지'
    if (click_share is not None and spend_share is not None
            and click_share > spend_share * (cfg.th('min_gap_ratio') or 1.10)):
        pattern = 'P2'
        rec = (f'차기 캠페인 시 {top_fmt} 포맷 제작 비중 상향 편성 권장 — '
               f'예산 비중 {P.share_rate(spend_share)} 대비 '
               f'클릭 기여 {P.share_rate(click_share)}로 투입 대비 성과 우위')
    else:
        pattern = 'P6'
        rec = (f'{top_fmt} 편중 구조 완화 검토 — '
               f'포맷별 병행 운영으로 지면 커버리지 확대 권장')

    return Insight(
        axis=axes.D_CREATIVE,
        pattern=pattern,
        finding=(f'소재 포맷 중 {top_fmt}에서 클릭 기여 '
                 f'{P.share_rate(click_share) if click_share is not None else "-"} '
                 f'최상위 확보'),
        recommendation=rec,
        evidence=evidence[:cfg.th('max_evidence_per_insight') or 3],
        sources=P.join_sources([
            P.source_label(rows[0].source.file_name, rows[0].section)]),
        priority=1.6 + (click_share or 0),
        metrics={'best_format': top_fmt, 'click_share': click_share,
                 'spend_share': spend_share, 'format_count': len(buckets),
                 'creative_count': sum(n for _, _, n in agg)},
    )


# ─────────────────────────── 3. 소재 다양성 · 피로도

def _diversity(dataset: CampaignDataset, rows: List[MediaPerformance],
               cfg: InsightConfig) -> Optional[Insight]:
    """단일 소재 장기 운영 — 계획축(PlanLine.creative)과 대조"""
    try:
        plan = list(dataset.plan_lines())
    except Exception:
        plan = []

    planned = {(l.creative or '').strip() for l in plan if (l.creative or '').strip()}
    actual = {(r.creative or '').strip() for r in rows if (r.creative or '').strip()}
    n_actual = len(actual)
    if n_actual == 0:
        return None

    # 집행 기간 (계획축에서 산출)
    starts = [l.period_start for l in plan if l.period_start]
    ends = [l.period_end for l in plan if l.period_end]
    period_text = P.period_label(min(starts), max(ends)) if starts and ends else ''

    if n_actual == 1:
        only = next(iter(actual))
        return Insight(
            axis=axes.D_CREATIVE,
            pattern='P5',
            finding=(f'집행 전 기간 단일 소재({P.short_label(only, 24)}) 운영 확인'
                     + (f' · 기간 {period_text}' if period_text else '')),
            recommendation=('차기 캠페인 시 캠페인 중반 소재 교체 또는 '
                            '멀티 소재 병행 운영 권장 — 노출 피로도 완화 목적'),
            evidence=[f'실집행 소재 {n_actual}종'
                      + (f' · 계획 소재 {len(planned)}종' if planned else ''),
                      '단일 소재 장기 노출 시 반응률 저하 요인으로 작용'],
            sources=P.join_sources([
                P.source_label(rows[0].source.file_name, rows[0].section)]),
            priority=1.9,
            metrics={'creative_count': 1, 'planned_count': len(planned),
                     'period': period_text},
        )

    # 계획 대비 실집행 소재가 줄었으면 부재-보완형
    if planned and n_actual < len(planned):
        missing = len(planned) - n_actual
        return Insight(
            axis=axes.D_CREATIVE,
            pattern='P3',
            finding=(f'계획 소재 {len(planned)}종 대비 실집행 {n_actual}종으로 '
                     f'{missing}종 미집행 확인'),
            recommendation=('차기 캠페인 시 소재 제작·검수 일정의 선행 확보 권장 — '
                            '계획 소재의 온에어 누락 방지'),
            evidence=[f'계획 소재 {len(planned)}종 · 실집행 {n_actual}종',
                      '미집행 사유는 별도 확인 필요 (제작 지연·매체 반려 등)'],
            sources=P.join_sources([
                P.source_label(rows[0].source.file_name, rows[0].section)]),
            priority=1.7,
            metrics={'creative_count': n_actual, 'planned_count': len(planned),
                     'absent': True},
        )

    return None


# ─────────────────────────── 진입점

def generate(dataset: CampaignDataset, cfg: InsightConfig,
             excluded: List[str]) -> List[Insight]:
    rows = _creative_rows(dataset)
    if not rows:
        excluded.append('크리에이티브 축 — 소재별 효율 표 미확보')
        return []

    out: List[Insight] = []
    for fn, why in ((lambda: _creative_gaps(rows, cfg), '소재 간 격차 기준 미달'),
                    (lambda: _format_contribution(rows, cfg), '포맷 구분 2종 미만'),
                    (lambda: _diversity(dataset, rows, cfg), '소재 다양성 특이사항 없음')):
        try:
            got = fn()
        except Exception as e:
            excluded.append(f'크리에이티브 축 규칙 실패: {e}')
            continue
        if not got:
            excluded.append(f'크리에이티브 축 — {why}')
        elif isinstance(got, list):
            out.extend(got)
        else:
            out.append(got)
    return out
