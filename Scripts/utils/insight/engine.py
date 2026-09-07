# -*- coding: utf-8 -*-
"""
Stage 3 — 인사이트 / Lesson-Learned 생성 엔진

CampaignDataset(실집행 팩트) + CampaignKnowledge(기획 의도)를 입력으로
규칙 기반 인사이트를 도출한다. 외부 API 를 호출하지 않으며 전량 로컬 계산이다
(claude.md 1장: 외부 연결 금지).

산출:
  Insight       발견 → 제안 → 근거 3단 블록 (Lesson Learned 슬라이드)
  StrategyItem  차기 캠페인 전략 방향 4개 영역

원칙:
  - 규칙 발동 조건을 충족하지 못하면 문장을 만들지 않는다. 빈 항목은 만들지 않고
    제외 사유를 InsightSet.excluded 에 남겨 Checklist 로 흘려보낸다.
  - 자동 도출된 제안은 사람이 검증해야 하는 항목이므로 반드시 Checklist 에 기재한다.
"""

from typing import List, Optional

from models.campaign_data import CampaignDataset, Insight, InsightSet
from models.campaign_knowledge import CampaignKnowledge
from models.checklist import ChecklistItem

from . import (axes, composer, rules_creative, rules_funnel, rules_kpi,
               rules_media, rules_period, rules_targeting, strategy)
from .config import InsightConfig


class InsightEngine:
    """규칙 기반 인사이트 도출"""

    def __init__(self, config_path: Optional[str] = None):
        self.cfg = InsightConfig(config_path)

    # ------------------------------------------------------------------

    def generate(self, knowledge: CampaignKnowledge,
                 dataset: CampaignDataset) -> InsightSet:
        """
        Args:
            knowledge: Stage 1.5 검증을 마친 캠페인 지식
            dataset: Stage 2 파싱 데이터셋

        Returns:
            InsightSet (규칙 오류가 나도 예외를 던지지 않음)
        """
        result = InsightSet()
        result.warnings.append(f'인사이트 규칙 설정: {self.cfg.source}')

        # 5축 규칙 (axes.py) — kpi/period 는 각각 E/B 축으로 흡수된다
        rules = (
            ('매체·상품 효율', rules_media.generate),
            ('타겟팅 비교', rules_targeting.generate),
            ('크리에이티브', rules_creative.generate),
            ('전환·퍼널', rules_funnel.generate),
            ('목표 대비 달성률', rules_kpi.generate),
            ('기간·Phase 추이', rules_period.generate),
        )
        collected: List[Insight] = []
        for name, rule in rules:
            try:
                collected.extend(rule(dataset, self.cfg, result.excluded) or [])
            except Exception as e:              # 한 규칙의 실패가 전체를 막지 않음
                result.warnings.append(f'[{name}] 규칙 실행 실패: {e}')

        # 근거 없는 문장은 채택하지 않는다
        usable = [i for i in collected if i.finding and i.evidence]
        dropped = len(collected) - len(usable)
        if dropped:
            result.excluded.append(f'근거 수치가 비어 채택하지 않은 인사이트 {dropped}건')

        # 3단 논법 마감 — 축 정규화 · 평가(2단) 채움 · 패턴 · 블록 ID
        usable = composer.finalize(usable, self.cfg, result.warnings)

        result.insights = self._select(usable, result.excluded)

        try:
            result.strategies = strategy.generate(
                dataset, result.insights, self.cfg, result.excluded)
        except Exception as e:
            result.warnings.append(f'[차기 전략] 생성 실패: {e}')

        return result

    # ------------------------------------------------------------------

    def _select(self, usable: List[Insight],
                excluded: List[str]) -> List[Insight]:
        """
        축 다양성을 지키며 게재분을 고른다.

        우선순위만으로 자르면 효율 격차가 큰 매체 축이 지면을 독식해
        '데이터 요약'처럼 보인다. 축별 상한을 두고 A→E 순 라운드로빈으로
        뽑아 5축이 고르게 실리게 한다.
        """
        per_axis = self.cfg.th('max_per_axis') or 3
        total = self.cfg.th('max_insights') or 12

        buckets: dict = {}
        for i in usable:
            buckets.setdefault(i.axis, []).append(i)

        for axis_key, items in buckets.items():
            items.sort(key=lambda x: x.priority, reverse=True)
            if len(items) > per_axis:
                excluded.append(
                    f'{axes.label(axis_key)} 축 상위 {per_axis}건만 게재 '
                    f'(도출 {len(items)}건)')
                buckets[axis_key] = items[:per_axis]

        ordered = sorted(buckets.keys(), key=axes.sort_key)
        picked: List[Insight] = []
        depth = 0
        while len(picked) < total:
            added = False
            for axis_key in ordered:
                if depth < len(buckets[axis_key]):
                    picked.append(buckets[axis_key][depth])
                    added = True
                    if len(picked) >= total:
                        break
            if not added:
                break
            depth += 1

        left = sum(len(v) for v in buckets.values()) - len(picked)
        if left > 0:
            excluded.append(f'지면 제약으로 {left}건 제외 (총 {total}건 게재)')

        covered = sorted({i.axis for i in picked}, key=axes.sort_key)
        excluded.append(
            '게재 축 — ' + ' · '.join(f'{axes.code(a)} {axes.label(a)}'
                                     for a in covered))
        return picked

    # ------------------------------------------------------------------

    @staticmethod
    def to_checklist_items(insight_set: InsightSet,
                           source: str = 'Stage 3') -> List[ChecklistItem]:
        """
        자동 도출 결과를 Checklist 항목으로 변환한다.

        자동 생성된 제안은 기획자가 반드시 눈으로 확인해야 하는 대상이므로
        건수와 제외 사유를 1페이지 Checklist 에 남긴다.
        """
        items: List[ChecklistItem] = []

        if insight_set.insights:
            preview = ' / '.join(i.finding[:40] for i in insight_set.insights[:2])
            items.append(ChecklistItem(
                type='insight_auto_generated',
                severity='warning',
                message=(f'자동 도출 인사이트 {len(insight_set.insights)}건 · '
                         f'차기 전략 {len(insight_set.strategies)}건 — 문구 검증 필요'),
                detail=f'실적 데이터 기반 규칙 산출값. 발견·근거는 수치 인용, '
                       f'제안은 자동 도출 문구임 (예: {preview})',
                source=source,
            ))
        else:
            items.append(ChecklistItem(
                type='insight_not_generated',
                severity='warning',
                message='자동 도출 인사이트 없음 — Lesson Learned 직접 작성 필요',
                detail='규칙 발동 조건(비교 대상 2개 이상·최소 물량·격차 기준)을 '
                       '충족하는 데이터가 없어 문장을 생성하지 않음',
                source=source,
            ))

        if insight_set.excluded:
            items.append(ChecklistItem(
                type='insight_excluded',
                severity='info',
                message=f'인사이트 제외 항목 {len(insight_set.excluded)}건',
                detail=' | '.join(insight_set.excluded[:6]),
                source=source,
            ))

        return items
