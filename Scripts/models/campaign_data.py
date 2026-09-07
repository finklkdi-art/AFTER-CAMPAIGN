# -*- coding: utf-8 -*-
"""
Stage 2 블록 데이터 계약

파서가 산출하고 리포트 생성이 소비하는 중간 표현.
모든 레코드는 출처(source)를 필수로 가진다 — Rule Book 3.2 "데이터-해석 1:1 매칭".
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


# ===================== 공통 =====================

@dataclass
class Provenance:
    """이 값이 어느 문서 어느 위치에서 왔는지"""
    file_name: str = ""
    sheet_or_slide: str = ""
    locator: str = ""            # 행 번호, 표 번호 등

    def label(self) -> str:
        parts = [p for p in (self.file_name, self.sheet_or_slide, self.locator) if p]
        return ":".join(parts)


# ===================== 계획축 (미디어믹스) =====================

@dataclass
class PlanLine:
    """미디어믹스의 집행 계획 한 줄 = 로드맵의 기본 단위"""
    media: str = ""                      # 매체 (유튜브, 카카오모먼트 ...)
    product: str = ""                    # 상품 (비즈보드, Trueview Instream ...)
    category: str = ""                   # 구분/Category (영상, 배너, Phase1 ...)
    purpose: str = ""                    # 목적 (인지, 유입, Awareness ...)
    period_raw: str = ""                 # 원본 기간 표기 ("4/18~4/30", "6/27, 7/26")
    period_start: Optional[str] = None   # 정규화 (MM-DD 또는 YYYY-MM-DD)
    period_end: Optional[str] = None
    creative: str = ""                   # 소재 표기 ("이미지 4종 (런칭편...)")
    device: str = ""
    targeting: str = ""
    budget: Optional[float] = None
    expected_impressions: Optional[float] = None
    expected_clicks: Optional[float] = None
    expected_views: Optional[float] = None
    note: str = ""
    source: Provenance = field(default_factory=Provenance)


@dataclass
class MediaMixResult:
    """미디어믹스 파싱 결과"""
    advertiser: str = ""
    campaign: str = ""
    total_budget: Optional[float] = None
    period_raw: str = ""
    lines: List[PlanLine] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    source_file: str = ""

    def plan_totals(self) -> Dict[str, float]:
        """소계 행을 제외한 순수 계획 합계"""
        def s(attr):
            return sum(getattr(l, attr) or 0 for l in self.lines)
        return {
            'budget': s('budget'),
            'impressions': s('expected_impressions'),
            'clicks': s('expected_clicks'),
            'views': s('expected_views'),
        }


# ===================== 실적축 (데일리리포트) =====================

@dataclass
class MetricSet:
    """공통 성과 지표 묶음"""
    billed: Optional[float] = None        # 청구 금액
    spend: Optional[float] = None         # 집행 금액
    impressions: Optional[float] = None
    views: Optional[float] = None
    clicks: Optional[float] = None
    vtr: Optional[float] = None
    ctr: Optional[float] = None
    cpm: Optional[float] = None
    cpv: Optional[float] = None
    cpc: Optional[float] = None


@dataclass
class DailyRow:
    """일자별 통합의 한 행 (Media Total 기준)"""
    date: str = ""                        # YYYY-MM-DD
    note: str = ""                        # 비고 = 운영 이벤트
    metrics: MetricSet = field(default_factory=MetricSet)


@dataclass
class ScheduleEvent:
    """Scheduling 슬라이드의 이벤트 주석"""
    date: str = ""
    note: str = ""
    source: Provenance = field(default_factory=Provenance)


@dataclass
class MediaPerformance:
    """
    매체별(또는 매체×상품×타겟팅×소재) 실적

    axis 는 이 행이 어느 분류축의 값인지 나타낸다. 축을 구분하지 않으면
    상품별 행과 타겟팅별 행이 한 목록에 섞여 합계가 이중 계상된다.
      media     - 일자별 통합 시트의 매체별 Total (매체 간 비교 기준)
      product   - 매체 시트 '상품 별 효율' 표
      targeting - 매체 시트 '타겟팅 별 효율' 표
      creative  - 매체 시트 '상품별 X 소재별 효율' 표
      purpose   - 매체 시트 '목적별 효율' 표 (Awareness / Consideration 등)
    """
    media: str = ""
    product: str = ""
    targeting: str = ""
    creative: str = ""
    purpose: str = ""                    # 캠페인 목적·퍼널 단계
    axis: str = "product"
    section: str = ""                    # 원본 표 라벨 (출처 병기용)
    note: str = ""                       # 축으로 쓰지 않은 표기 (초수·목적 등)
    period_raw: str = ""
    budget: Optional[float] = None
    metrics: MetricSet = field(default_factory=MetricSet)
    source: Provenance = field(default_factory=Provenance)


@dataclass
class MediaSpend:
    """
    매체비 총합 — 집행이 끝난 뒤의 문서에서만 가져온 값.

    보고서에서 가장 자주 인용되는 단 하나의 숫자라, 어디서 왔고 무엇으로
    검증됐는지를 값과 함께 들고 다닌다. 검증에 실패하면 임의로 하나를
    고르지 않고 두 값을 모두 남긴다 (claude.md 3.2).

    출처 우선순위
      1순위  데일리리포트 안 `Media Mix` 시트의 총계 행
      검증   포스트바이 `Campaign Summary` 표의 Total 행

    🔴 제안서·별도 미디어믹스(제안 시점) 예산은 쓰지 않는다. 부킹 전 숫자라
       집행 결과 보고서에 실으면 사실과 달라진다.
    """
    total: Optional[float] = None
    by_media: Dict[str, float] = field(default_factory=dict)
    basis: str = ""                  # grand_total_row | header_cell | media_sum
    source_label: str = ""           # 파일명:시트
    verified_value: Optional[float] = None
    verified_source: str = ""
    confidence: str = "none"         # high | medium | low | none
    note: str = ""

    def is_verified(self) -> bool:
        """서로 다른 두 문서가 같은 값을 말하는가."""
        if self.total is None or self.verified_value is None:
            return False
        return abs(self.total - self.verified_value) <= max(1.0, self.total * 0.001)

    def mismatch(self) -> Optional[float]:
        """두 출처의 차이 (검증값이 없으면 None)."""
        if self.total is None or self.verified_value is None:
            return None
        return self.verified_value - self.total


@dataclass
class DailyReportResult:
    """데일리리포트 파싱 결과"""
    campaign: str = ""
    period_raw: str = ""
    budget_raw: Optional[float] = None
    total: MetricSet = field(default_factory=MetricSet)          # Total 행
    daily_average: MetricSet = field(default_factory=MetricSet)  # 1일 평균 행
    daily_rows: List[DailyRow] = field(default_factory=list)
    events: List[ScheduleEvent] = field(default_factory=list)
    media_performance: List[MediaPerformance] = field(default_factory=list)
    media_totals: List[MediaPerformance] = field(default_factory=list)
    media_daily: Dict[str, List[DailyRow]] = field(default_factory=dict)
    media_names: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    source_file: str = ""
    # Media Mix 시트에서 읽은 매체비 총합 (집행 이후 기준)
    media_spend: Optional[MediaSpend] = None


# ===================== 포스트바이 =====================

@dataclass
class KpiTarget:
    """KPI 목표 대비 실적"""
    scope: str = ""                       # "Digital", "OOH" 등
    media: str = ""
    product: str = ""
    kpi_name: str = ""                    # Impression / View / Click
    target: Optional[float] = None
    actual: Optional[float] = None
    achievement_rate: Optional[float] = None   # 0.0~ (1.23 = 123%)
    source: Provenance = field(default_factory=Provenance)


@dataclass
class PostbuySection:
    """포스트바이 슬라이드 한 장"""
    slide_no: int = 0
    kind: str = "other"                   # summary / kpi / scheduling / search / buzz /
                                          # reach / analytics / lesson / media / other
    title: str = ""
    headlines: List[str] = field(default_factory=list)
    tables: List[List[List[str]]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


@dataclass
class PostbuyResult:
    """포스트바이 파싱 결과"""
    campaign: str = ""
    report_date: str = ""
    period_raw: str = ""
    summary_headline: str = ""
    sections: List[PostbuySection] = field(default_factory=list)
    campaign_summary: List[MediaPerformance] = field(default_factory=list)
    kpi_targets: List[KpiTarget] = field(default_factory=list)
    events: List[ScheduleEvent] = field(default_factory=list)
    lesson_learned: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    source_file: str = ""
    # Campaign Summary 표의 Total 행 — 매체비 총합 교차 검증용.
    # 매체별 행을 더해 만든 값과 달리 문서가 직접 말해 주는 숫자다.
    summary_total_budget: Optional[float] = None
    summary_total_source: str = ""

    def sections_of(self, kind: str) -> List[PostbuySection]:
        return [s for s in self.sections if s.kind == kind]


# ===================== Part 1 캠페인 개요 (기획 의도) =====================

@dataclass
class IntentPhase:
    """제안서가 설계한 캠페인 단계 하나"""
    name: str = ""                       # "Phase 1" / "런칭기"
    period: str = ""                     # "4/21 ~ 5/20"
    purpose: str = ""                    # "인지 확보"
    source: Provenance = field(default_factory=Provenance)


@dataclass
class CampaignIntent:
    """
    캠페인 실행 **이전**의 기획 의도 — Part 1(Overview)의 유일한 원천.

    실집행 팩트(CampaignDataset)와 엄격히 구분한다. 여기에 실적 수치를 섞으면
    '제안 의도 vs 결과' 대조가 성립하지 않는다.

    동료 AE 가 제안서를 올리지 않고 포스트바이만 올리는 경우가 잦으므로,
    비어 있는 것이 정상 상태의 하나다. 비었다고 슬라이드를 지우지 않고
    작성 가이드를 렌더한다 (Rule Book — 조용한 소실 금지).
    """
    # ── 캠페인 목표
    challenge: str = ""                  # 당면 과제 (왜 진행했는가)
    core_target: str = ""                # 핵심 타겟
    key_message: str = ""                # 메인 카피 / 슬로건

    # ── 캠페인 전략
    mix_direction: str = ""              # 미디어·크리에이티브 믹스 방향성
    channels: List[str] = field(default_factory=list)   # 핵심 채널

    # ── 캠페인 로드맵
    phases: List[IntentPhase] = field(default_factory=list)
    timeline_note: str = ""

    # ── 메타
    sources: List[str] = field(default_factory=list)
    snippets: Dict[str, str] = field(default_factory=dict)  # 앵커별 원문 조각 (검증 근거)
    summary: str = ""                    # Stage 1.5 요약본 (AE 확정)
    confirmed_by_ae: bool = False

    # ---------- 충족 판정 ----------

    def has_goal(self) -> bool:
        return bool(self.challenge or self.core_target or self.key_message)

    def has_strategy(self) -> bool:
        return bool(self.mix_direction or self.channels)

    def has_roadmap(self) -> bool:
        return bool(self.phases or self.timeline_note)

    def goal_filled(self) -> int:
        return sum(1 for v in (self.challenge, self.core_target, self.key_message) if v)

    def is_thin(self) -> bool:
        """
        '턱없이 빈약'한지 — 목표 3요소 중 1개 이하이고 전략도 비었으면 빈약.

        빈약해도 슬라이드는 남기고 작성 가이드를 얹는다.
        """
        return self.goal_filled() <= 1 and not self.has_strategy()

    def missing_parts(self) -> List[str]:
        out = []
        if not self.has_goal():
            out.append('캠페인 목표')
        if not self.has_strategy():
            out.append('캠페인 전략')
        if not self.has_roadmap():
            out.append('캠페인 로드맵')
        return out


# ===================== Stage 3 인사이트 =====================

@dataclass
class Insight:
    """
    자동 도출한 인사이트 한 건 — 실제 보고서의 3단 논법을 따른다.

      [발견 Fact]     데이터에서 확인된 팩트 (명사형 종결)
        ▽
      [평가 Context]  그 수치의 기획적 해석 — 의도와 대조
        ▽
      [제언 Action]   차기 캠페인의 구체적 실행 액션
      [근거]          수치 상세 (- 불릿)

    근거 없는 서술을 만들지 않기 위해 evidence 가 빈 인사이트는 채택하지 않는다.
    """
    axis: str = ""                       # axes.py 5축 (message/media/targeting/creative/funnel)
    finding: str = ""                    # 1단 발견
    context: str = ""                    # 2단 평가 — 기획적 해석
    recommendation: str = ""             # 3단 제언
    evidence: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    priority: float = 0.0                # 클수록 먼저 배치 (효과 크기 기준)
    metrics: Dict[str, Any] = field(default_factory=dict)
    # ── 재설계 확장 (INSIGHT_ARCHITECTURE.md §2) ──
    pattern: str = ""                    # P1~P6 서술 패턴
    intent: str = ""                     # 대조된 '원래 의도' 문장
    confidence: str = "medium"           # high | medium | low
    origin: str = "rule"                 # rule | api | ae
    block_id: str = ""                   # 부분 리렌더링 단위
    approved: bool = False               # AE 승인 여부


@dataclass
class StrategyItem:
    """차기 캠페인 전략 방향 한 줄"""
    area: str = ""                       # 매체 운영 / 타겟팅 / 소재·메시지 / 예산 배분
    direction: str = ""
    basis: str = ""                      # 근거 수치
    sources: List[str] = field(default_factory=list)


@dataclass
class InsightSet:
    """Stage 3 산출물"""
    insights: List[Insight] = field(default_factory=list)
    strategies: List[StrategyItem] = field(default_factory=list)
    excluded: List[str] = field(default_factory=list)   # 조건 미달·이상치로 제외한 사유
    warnings: List[str] = field(default_factory=list)

    def by_axis(self, axis: str) -> List['Insight']:
        return [i for i in self.insights if i.axis == axis]


# ===================== 결손 항목 =====================

# 결손 처리 상태
GAP_PENDING = 'pending'    # 아직 결정하지 않음
GAP_FILLED = 'filled'      # 기획자가 직접 입력함
GAP_SKIPPED = 'skipped'    # 기획자가 건너뛰기로 결정함


@dataclass
class DataGap:
    """
    자동 추출로 채우지 못한 항목.

    AI가 임의로 추정하지 않고(Rule Book 2.2), Stage 1.5에서 기획자가
    직접 입력하거나 건너뛸지 선택하게 한다.
    """
    key: str                             # roadmap_period / kpi_target / reach_freq ...
    label: str = ""                      # 화면에 보일 이름
    reason: str = ""                      # 왜 비었는지 (근거)
    severity: str = "advisory"           # blocking(진행 차단) | advisory(권고)
    input_kind: str = "text"             # text | table | textarea
    resolution: str = GAP_PENDING
    filled_value: Any = None
    affected_slides: List[str] = field(default_factory=list)   # 영향받는 산출물 블록

    def is_resolved(self) -> bool:
        return self.resolution in (GAP_FILLED, GAP_SKIPPED)

    def status_label(self) -> str:
        return {
            GAP_PENDING: '미결정',
            GAP_FILLED: '직접 입력함',
            GAP_SKIPPED: '건너뜀',
        }.get(self.resolution, self.resolution)


# ===================== 통합 =====================

@dataclass
class CampaignDataset:
    """
    한 캠페인의 파싱 결과 묶음.

    mode:
      full - 포스트바이 있음 (KPI 확정 목표·도달빈도·검색/버즈·AA 확보)
      lite - 포스트바이 없음 (미디어믹스 + 데일리리포트만으로 구성)
    """
    mode: str = "lite"
    media_mix: Optional[MediaMixResult] = None
    daily_report: Optional[DailyReportResult] = None
    postbuy: Optional[PostbuyResult] = None
    extra_mixes: List[MediaMixResult] = field(default_factory=list)
    gaps: List[DataGap] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    # Part 1 Overview 의 원천 — 제안서가 없으면 빈 객체가 그대로 들어온다
    intent: CampaignIntent = field(default_factory=CampaignIntent)

    # ---------- 조회 ----------

    def media_spend(self) -> Optional['MediaSpend']:
        """
        매체비 총합 — 화면과 보고서가 함께 쓰는 **단일 출처**.

        여기 한 곳으로 모은 이유: 예전에는 화면이 매체별 행을 더해서,
        보고서는 데일리리포트 Total 행을 써서 서로 다른 숫자를 보여 줬다.
        같은 캠페인에서 화면 4.8억 · 보고서 4.77억 · 실제 매체비 3.95억이
        동시에 존재했다. 값은 한 군데서만 정해야 한다.

        None 이면 집행 이후 문서에서 매체비를 찾지 못한 것이다. 그때는
        추정하지 말고 '—' 로 두어야 한다 (claude.md 3.3).
        """
        dr = self.daily_report
        spend = getattr(dr, 'media_spend', None) if dr else None
        return spend if (spend and spend.total) else None

    def gap(self, key: str) -> Optional[DataGap]:
        for g in self.gaps:
            if g.key == key:
                return g
        return None

    def pending_gaps(self) -> List[DataGap]:
        return [g for g in self.gaps if not g.is_resolved()]

    def blocking_gaps(self) -> List[DataGap]:
        return [g for g in self.pending_gaps() if g.severity == 'blocking']

    def plan_lines(self) -> List[PlanLine]:
        """주 믹스 + 보조 믹스의 계획 라인 전체"""
        lines = list(self.media_mix.lines) if self.media_mix else []
        for m in self.extra_mixes:
            lines.extend(m.lines)
        return lines

    def summary(self) -> Dict[str, Any]:
        """화면 상단 요약용"""
        dr = self.daily_report
        return {
            'mode': self.mode,
            'plan_lines': len(self.plan_lines()),
            'daily_rows': len(dr.daily_rows) if dr else 0,
            'events': len(dr.events) if dr else 0,
            'media_performance': len(dr.media_performance) if dr else 0,
            'kpi_targets': len(self.postbuy.kpi_targets) if self.postbuy else 0,
            'gaps_pending': len(self.pending_gaps()),
            'gaps_total': len(self.gaps),
        }

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'CampaignDataset':
        """
        to_dict 와 대칭. 중첩 데이터클래스까지 복원한다.

        타입 힌트를 읽어 일반적으로 복원하므로 필드를 추가해도 한쪽만 고쳐
        값이 조용히 소실되는 일이 없다 (claude.md 4장).
        """
        from utils.dataclass_io import build
        return build(cls, data)
