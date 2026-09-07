# -*- coding: utf-8 -*-
"""
축 4 — 기간·Phase별 추이

원천: 데일리리포트 <일자별 통합> 의 일자별 행과 비고(운영 이벤트)

Phase 구간은 비고에 'Phase1, 전매체 라이브' 처럼 명시된 경우에만 나눈다.
표기가 없으면 구간을 임의로 만들지 않고(추측 금지) 피크 구간만 다룬다.
피크일의 귀인도 그 날짜에 실제 이벤트가 있을 때만 문장에 넣는다.
"""

import re
from typing import Dict, List, Optional, Tuple

from models.campaign_data import (
    CampaignDataset, DailyRow, Insight, MediaPerformance, MetricSet,
)

from . import metrics as M
from . import phrasing as P
from .config import InsightConfig


def _as_perf(rows: List[DailyRow]) -> List[MediaPerformance]:
    """일자별 행을 집계 함수에 넣기 위한 어댑터"""
    return [MediaPerformance(metrics=r.metrics) for r in rows]


def _phase_segments(dataset: CampaignDataset, cfg: InsightConfig
                    ) -> List[Tuple[str, List[DailyRow]]]:
    """
    비고에 Phase 표기가 있는 경우 일자별 행을 구간으로 나눈다.

    Returns:
        [(구간명, 일자별 행)] — 표기가 없으면 빈 목록
    """
    dr = dataset.daily_report
    if not dr:
        return []
    rx = re.compile(cfg.phase_pattern, re.IGNORECASE)

    # Phase 번호가 등장한 날짜들을 수집
    marks: List[Tuple[str, str]] = []          # (날짜, 구간명)
    for row in dr.daily_rows:
        m = rx.search(row.note or '')
        if not m:
            continue
        num = next((g for g in m.groups() if g), '')
        if not num:
            continue
        marks.append((row.date, f'Phase{num}'))
    if not marks:
        return []

    # 같은 구간명이 여러 번 나오면 첫 등장일을 구간 시작으로 본다
    starts: Dict[str, str] = {}
    for date, name in marks:
        starts.setdefault(name, date)
    ordered = sorted(starts.items(), key=lambda kv: kv[1])
    if len(ordered) < 2:
        return []

    segments: List[Tuple[str, List[DailyRow]]] = []
    for i, (name, start) in enumerate(ordered):
        end = ordered[i + 1][1] if i + 1 < len(ordered) else None
        rows = [r for r in dr.daily_rows
                if r.date >= start and (end is None or r.date < end)]
        if rows:
            segments.append((name, rows))
    return segments if len(segments) >= 2 else []


def _peak_insight(dataset: CampaignDataset, cfg: InsightConfig
                  ) -> Optional[Insight]:
    """집행 피크 구간 인사이트"""
    dr = dataset.daily_report
    rows = dr.daily_rows
    use_spend = any(r.metrics.spend for r in rows)
    key = 'spend' if use_spend else 'impressions'
    valued = [(r, getattr(r.metrics, key) or 0) for r in rows]
    valued = [(r, v) for r, v in valued if v > 0]
    if len(valued) < (cfg.th('min_daily_rows') or 7):
        return None

    peak_row, peak_value = max(valued, key=lambda t: t[1])
    avg = sum(v for _, v in valued) / len(valued)
    if not avg or peak_value / avg < (cfg.th('min_gap_ratio') or 1.15):
        return None

    label = cfg.metric_label(key)
    peak_text = (P.eok(peak_value) if key == 'spend' else P.cnt(peak_value))
    avg_text = (P.eok(avg) if key == 'spend' else P.cnt(avg))

    finding = (f'집행 피크일은 {P.day_label(peak_row.date)}로 '
               f'{label} {peak_text} 기록 — 일 평균 {avg_text} 대비 '
               f'{peak_value / avg:.1f}배 집중 운영')
    evidence = [
        f'집행 기간 {P.period_label(valued[0][0].date, valued[-1][0].date)} · '
        f'운영일 {len(valued)}일 기준',
        f'일 평균 {label} {avg_text} / 피크일 {label} {peak_text}',
    ]

    # 제안은 피크일에 실제로 기록된 이벤트 유형에 맞춰 서술한다.
    # 이벤트가 없으면 귀인하지 않고 편차 자체만 다룬다 (추측 금지).
    rec = '일자별 집행 편차 확인 — 차기 캠페인 시 균등 소진 설정 검토 권고'
    if peak_row.note:
        evidence.append(f'피크일 운영 이벤트 · {peak_row.note[:70]}')
        kinds = cfg.match_event(peak_row.note)
        if '소재' in kinds:
            rec = ('소재 교체 시점에 물량 변동 발생 — 차기 캠페인 시 '
                   '러닝체인지 구간의 소진 계획 사전 설계 권고')
        elif '라이브' in kinds:
            rec = ('매체 라이브 시점에 물량 집중 — 차기 캠페인 시 '
                   '라이브 일정 분산 배치 권고')
        elif '종료' in kinds:
            rec = ('집행 종료 구간에 물량 집중 — 차기 캠페인 시 '
                   '종료 전 잔여 예산 소진 일정 사전 관리 권고')

    return Insight(
        axis='period',
        finding=finding,
        recommendation=rec,
        evidence=evidence[:cfg.th('max_evidence_per_insight') or 3],
        sources=P.join_sources([P.source_label(dr.source_file, '일자별 통합')]),
        priority=1.5 + min(peak_value / avg, 3.0),
        metrics={'peak_date': peak_row.date, 'peak_value': peak_value,
                 'avg': avg, 'metric': key},
    )


def _phase_insight(dataset: CampaignDataset, cfg: InsightConfig
                   ) -> Optional[Insight]:
    """Phase 구간 간 운영 성격 비교"""
    segments = _phase_segments(dataset, cfg)
    if not segments:
        return None
    dr = dataset.daily_report

    stats = []
    for name, rows in segments:
        agg = M.aggregate(_as_perf(rows))
        stats.append((name, rows, agg))

    # 노출 중심 / 조회 중심을 판정할 수 있는 구간만 사용
    usable = [(n, r, a) for n, r, a in stats if (a.impressions or 0) > 0]
    if len(usable) < 2:
        return None

    top_imp = max(usable, key=lambda t: t[2].impressions or 0)
    top_view = max(usable, key=lambda t: t[2].views or 0)

    parts = []
    for name, rows, agg in usable:
        parts.append(
            f'{name} {P.period_label(rows[0].date, rows[-1].date)} · '
            f'{P.metric_value("impressions", agg.impressions, cfg)} · '
            f'{P.metric_value("views", agg.views, cfg)}')

    if top_imp[0] != top_view[0] and (top_view[2].views or 0) > 0:
        finding = (f'{top_view[0]}는 조회 중심, {top_imp[0]}는 노출 중심으로 '
                   f'구간별 운영 성격 분화 확인')
        rec = (f'차기 캠페인 시 구간 목표를 분리 설정하여 '
               f'{top_view[0]} 조회 효율 · {top_imp[0]} 노출 물량 각각 관리 권고')
    else:
        lead = top_imp
        others = [s for s in usable if s[0] != lead[0]]
        ratio = ((lead[2].impressions or 0) /
                 max(1.0, max((o[2].impressions or 0) for o in others)))
        finding = (f'{lead[0]} 구간에 노출 물량 집중 — '
                   + P.josa_ro(P.metric_value(
                       "impressions", lead[2].impressions, cfg))
                   + f' 타 구간 대비 {ratio:.1f}배 운영')
        rec = (f'구간별 물량 편중 확인 — 차기 캠페인 시 '
               f'{lead[0]} 외 구간의 노출 확보 방안 검토 권고')

    return Insight(
        axis='period',
        finding=finding,
        recommendation=rec,
        evidence=parts[:cfg.th('max_evidence_per_insight') or 3],
        sources=P.join_sources([P.source_label(dr.source_file, '일자별 통합')]),
        priority=2.5,
        metrics={'segments': [n for n, _, _ in usable]},
    )


def _event_evidence(dataset: CampaignDataset, cfg: InsightConfig) -> List[str]:
    """운영 이벤트 유형별 발생 건수 (키워드가 맞는 것만)"""
    dr = dataset.daily_report
    counts: Dict[str, int] = {}
    for e in dr.events:
        for kind in cfg.match_event(e.note):
            counts[kind] = counts.get(kind, 0) + 1
    return [f'{kind} 관련 운영 이벤트 {n}건 기록'
            for kind, n in sorted(counts.items(), key=lambda kv: -kv[1])
            if kind == '소재' and n >= 2]


def generate(dataset: CampaignDataset, cfg: InsightConfig,
             excluded: List[str]) -> List[Insight]:
    """기간·Phase 추이 인사이트를 도출한다"""
    dr = dataset.daily_report
    if not dr or len(dr.daily_rows) < (cfg.th('min_daily_rows') or 7):
        excluded.append('기간 추이 — 일자별 데이터 부족 '
                        f'({len(dr.daily_rows) if dr else 0}일)')
        return []

    out: List[Insight] = []
    phase = _phase_insight(dataset, cfg)
    if phase:
        out.append(phase)
    else:
        excluded.append('Phase 구간 비교 — 비고에 Phase 표기 없음 (구간 임의 분할 금지)')

    peak = _peak_insight(dataset, cfg)
    if peak:
        extra = _event_evidence(dataset, cfg)
        if extra:
            peak.evidence.extend(extra)
            peak.evidence = peak.evidence[:cfg.th('max_evidence_per_insight') or 3]
        out.append(peak)

    return out
