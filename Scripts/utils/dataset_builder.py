# -*- coding: utf-8 -*-
"""
CampaignDatasetBuilder — 3개 파서를 묶어 Stage 2 입력을 구성

역할:
  1. 문서 역할(role)에 따라 알맞은 파서를 태운다
  2. 포스트바이 유무로 Full / Lite 모드를 자동 판정한다
  3. 자동으로 못 채운 항목을 DataGap 으로 모아 Stage 1.5 로 넘긴다

AI가 빈칸을 추정해 채우지 않는다 (Rule Book 2.2).
결손은 드러내고, 채울지 건너뛸지는 기획자가 정한다.
"""

from pathlib import Path
from typing import List, Optional

from models.campaign_data import (
    CampaignDataset, DataGap, GAP_PENDING, MediaSpend,
)
from models.campaign_knowledge import CampaignKnowledge
from models.checklist import ChecklistItem
from models.source_document import SourceDocument
from utils.parsers import DailyReportParser, MediaMixParser, PostbuyParser


# 결손 항목 정의 — Lite 모드에서 포스트바이가 없을 때 비는 것들
_POSTBUY_ONLY_GAPS = (
    ('kpi_target', 'KPI 확정 목표치', 'blocking', 'table',
     ['목표 대비 달성률'],
     '포스트바이가 없어 확정 목표치를 확보하지 못했습니다. '
     '미디어믹스의 예상 성과는 제안 시점 값이라 부킹 후 확정치와 다를 수 있습니다.'),
    ('reach_freq', '도달·빈도 (Reach / Freq / CPR)', 'advisory', 'table',
     ['도달 및 빈도'],
     '매체사가 제공하는 데이터로, 데일리리포트에는 포함되지 않습니다.'),
    ('search_buzz', '검색량·버즈량 트렌드', 'advisory', 'textarea',
     ['검색어 추이', '검색량 트렌드', '버즈량 트렌드'],
     'Cheil Keybox / SMA / 네이버 데이터랩 기반 지표로 별도 소스가 필요합니다.'),
    ('analytics', 'Adobe Analytics (Visit/Cart/Order)', 'advisory', 'table',
     ['AA 유입경로', 'AA 상세'],
     '별도 분석 시스템 데이터입니다.'),
    ('lesson_learned', 'Lesson Learned 초안', 'advisory', 'textarea',
     ['Lesson Learned'],
     '포스트바이에 담긴 제언을 가져올 수 없어 성과 데이터 기반 초안만 제공됩니다.'),
)


class CampaignDatasetBuilder:
    """CampaignKnowledge 의 문서들을 파싱해 CampaignDataset 을 만듭니다"""

    @staticmethod
    def build(knowledge: CampaignKnowledge) -> CampaignDataset:
        """
        Args:
            knowledge: Stage 1 이 만든 CampaignKnowledge

        Returns:
            CampaignDataset (실패해도 예외 없이 warnings/gaps 에 기록)
        """
        dataset = CampaignDataset()

        CampaignDatasetBuilder._parse_mixes(knowledge, dataset)
        CampaignDatasetBuilder._parse_daily(knowledge, dataset)
        CampaignDatasetBuilder._parse_postbuy(knowledge, dataset)
        CampaignDatasetBuilder._extract_intent(knowledge, dataset)

        dataset.mode = 'full' if dataset.postbuy and dataset.postbuy.kpi_targets else 'lite'

        CampaignDatasetBuilder._verify_media_spend(dataset)
        CampaignDatasetBuilder._collect_gaps(dataset)
        CampaignDatasetBuilder._report_to_checklist(knowledge, dataset)
        return dataset

    # ------------------------------------------------------------------
    # 파서 실행
    # ------------------------------------------------------------------

    @staticmethod
    def _verify_media_spend(dataset: CampaignDataset) -> None:
        """
        매체비 총합을 포스트바이 Total 행과 대조한다.

        서로 다른 두 문서(데일리리포트 Media Mix 시트 · 포스트바이 Campaign
        Summary)가 같은 값을 말하면 확신을 갖고 쓴다. 어긋나면 임의로 하나를
        고르지 않고 두 값을 모두 남겨 사람이 판단하게 한다 (claude.md 3.2).
        """
        spend = getattr(dataset.daily_report, 'media_spend', None) \
            if dataset.daily_report else None
        pb = dataset.postbuy
        pb_total = getattr(pb, 'summary_total_budget', None) if pb else None

        if spend is None:
            # 데일리리포트에 Media Mix 시트가 없어도, 포스트바이 총계가 있으면
            # 그것만으로 매체비를 세운다 — 둘 다 집행 이후 문서다.
            if pb_total is not None and dataset.daily_report is not None:
                dataset.daily_report.media_spend = MediaSpend(
                    total=pb_total, basis='postbuy_summary_total',
                    source_label=getattr(pb, 'summary_total_source', '') or '',
                    confidence='medium',
                    note='데일리리포트에 Media Mix 시트가 없어 포스트바이 총계를 사용')
            return

        if pb_total is None:
            return

        spend.verified_value = pb_total
        spend.verified_source = getattr(pb, 'summary_total_source', '') or ''
        if spend.is_verified():
            spend.confidence = 'high'
            spend.note = ''
        else:
            gap = spend.mismatch() or 0.0
            spend.confidence = 'low'
            spend.note = (f'데일리리포트 {spend.total:,.0f}원과 '
                          f'포스트바이 {pb_total:,.0f}원이 '
                          f'{abs(gap):,.0f}원 달라요')
            dataset.warnings.append('매체비 총합 — ' + spend.note)

    @staticmethod
    def _extract_intent(knowledge: CampaignKnowledge,
                        dataset: CampaignDataset) -> None:
        """
        Part 1 캠페인 개요의 원천(기획 의도)을 뽑는다.

        제안서가 없어도 브리프·요약 시트에서 유추를 시도하고, 그래도 비면
        빈 객체를 그대로 둔다 — 슬라이드는 지우지 않고 작성 가이드를 얹는다.
        누락 사실은 여기서 Checklist 에 남긴다 (렌더 시점보다 앞서야
        1페이지 Checklist 에 실린다).
        """
        from models.checklist import ChecklistItem
        try:
            from utils import intent_extractor
            dataset.intent = intent_extractor.extract(knowledge)
        except Exception as e:
            dataset.warnings.append(f'기획 의도 추출 실패: {e}')
            return

        intent = dataset.intent
        missing = intent.missing_parts()
        if not missing and not intent.is_thin():
            return

        detail = []
        if intent.sources:
            detail.append('참조 문서: ' + ', '.join(intent.sources[:3]))
        else:
            detail.append('제안서·미디어 브리프 등 기획 의도 문서를 찾지 못함')
        if intent.is_thin():
            detail.append('추출된 내용이 빈약해 슬라이드에 작성 가이드를 넣었음')

        # type·message 를 data_scanning / blocks 의 같은 사건과 정확히 일치시킨다.
        # 중복 제거 키가 `type:message` 라서(checklist_manager), 여기만 이모지나
        # 하이픈이 달라도 같은 사건이 화면에 두 줄로 뜬다. 실제로 그렇게 떴다.
        # 구체적인 누락 항목은 message 가 아니라 detail 로 내린다.
        if missing:
            detail.append(f'누락 {", ".join(missing)}')
        knowledge.add_checklist_item(ChecklistItem(
            type='overview_missing',
            severity='warning',
            message="'캠페인 개요(목표/전략/로드맵)' 소스 누락 — 수기 작성 요망",
            detail=' / '.join(detail),
            source='Stage 2 기획 의도 추출',
        ))

    @staticmethod
    def _docs(knowledge: CampaignKnowledge, role: str) -> List[SourceDocument]:
        return [d for d in knowledge.get_documents(role) if d.file_path]

    @staticmethod
    def _parse_mixes(knowledge: CampaignKnowledge, dataset: CampaignDataset) -> None:
        """미디어믹스 — 계획 라인이 가장 많은 것을 주 믹스로 삼는다"""
        results = []
        for doc in CampaignDatasetBuilder._docs(knowledge, 'media_mix'):
            r = MediaMixParser.parse(doc.file_path)
            results.append(r)
            dataset.warnings.extend(f'[{r.source_file}] {w}' for w in r.warnings)

        parsed = [r for r in results if r.lines]
        if not parsed:
            dataset.warnings.append('미디어믹스에서 집행 계획을 추출하지 못함')
            return

        parsed.sort(key=lambda r: len(r.lines), reverse=True)
        dataset.media_mix = parsed[0]
        dataset.extra_mixes = parsed[1:]

    @staticmethod
    def _parse_daily(knowledge: CampaignKnowledge, dataset: CampaignDataset) -> None:
        """데일리리포트 — 가장 일자 행이 많은 것을 채택"""
        results = []
        for doc in CampaignDatasetBuilder._docs(knowledge, 'daily_report'):
            r = DailyReportParser.parse(doc.file_path)
            results.append(r)
            dataset.warnings.extend(f'[{r.source_file}] {w}' for w in r.warnings)

        parsed = [r for r in results if r.daily_rows]
        if not parsed:
            dataset.warnings.append('데일리리포트에서 실적을 추출하지 못함')
            return
        parsed.sort(key=lambda r: len(r.daily_rows), reverse=True)
        dataset.daily_report = parsed[0]
        if len(parsed) > 1:
            # 채택되지 않은 문서를 조용히 버리지 않는다 (claude.md 3.1)
            dataset.warnings.append(
                f'데일리리포트 {len(parsed)}건 중 일자 행이 가장 많은 '
                f'[{parsed[0].source_file}] 채택 — 미반영: '
                + ', '.join(r.source_file for r in parsed[1:]))

    @staticmethod
    def _parse_postbuy(knowledge: CampaignKnowledge, dataset: CampaignDataset) -> None:
        """포스트바이 — pptx 만 대상 (이미지 PDF 는 표 추출 불가)"""
        for doc in CampaignDatasetBuilder._docs(knowledge, 'postbuy'):
            if not doc.file_path.lower().endswith('.pptx'):
                dataset.warnings.append(
                    f'[{doc.file_name}] 포스트바이가 PPTX 가 아니어서 표를 추출하지 못함')
                continue
            r = PostbuyParser.parse(doc.file_path)
            dataset.warnings.extend(f'[{r.source_file}] {w}' for w in r.warnings)
            if r.kpi_targets or r.campaign_summary:
                if dataset.postbuy is not None:
                    # 먼저 채택된 문서를 유지하고 나머지는 사유를 남긴다
                    dataset.warnings.append(
                        f'포스트바이 다수 감지 — [{dataset.postbuy.source_file}] 채택, '
                        f'[{r.source_file}] 미반영')
                    continue
                dataset.postbuy = r

    # ------------------------------------------------------------------
    # 결손 수집
    # ------------------------------------------------------------------

    @staticmethod
    def _add_gap(dataset: CampaignDataset, key: str, label: str, reason: str,
                 severity: str = 'advisory', input_kind: str = 'text',
                 slides: Optional[List[str]] = None) -> None:
        if dataset.gap(key):
            return
        dataset.gaps.append(DataGap(
            key=key, label=label, reason=reason, severity=severity,
            input_kind=input_kind, resolution=GAP_PENDING,
            affected_slides=slides or [],
        ))

    @staticmethod
    def _collect_gaps(dataset: CampaignDataset) -> None:
        """자동으로 채우지 못한 항목을 모은다"""

        # 1) 포스트바이가 없어서 비는 것들
        if dataset.mode == 'lite':
            for key, label, sev, kind, slides, reason in _POSTBUY_ONLY_GAPS:
                CampaignDatasetBuilder._add_gap(
                    dataset, key, label, reason, sev, kind, slides)

        # 2) 로드맵 시간축 — 기간이 비어 있는 계획 라인
        lines = dataset.plan_lines()
        if lines:
            no_period = [l for l in lines if not l.period_start]
            if no_period:
                ratio = len(no_period) / len(lines)
                sev = 'blocking' if ratio > 0.8 else 'advisory'
                CampaignDatasetBuilder._add_gap(
                    dataset, 'roadmap_period', '집행 기간 (로드맵 시간축)',
                    f'계획 라인 {len(lines)}건 중 {len(no_period)}건의 기간을 읽지 못했습니다. '
                    f'(병합셀로 상위 행에만 표기된 경우는 정상)',
                    sev, 'table', ['집행 로드맵', '일자별 추이'])
        else:
            CampaignDatasetBuilder._add_gap(
                dataset, 'plan_lines', '집행 계획 (미디어믹스)',
                '미디어믹스에서 계획 라인을 추출하지 못했습니다.',
                'blocking', 'table', ['집행 로드맵', '목표 대비 달성률'])

        # 3) 실적축
        if not dataset.daily_report or not dataset.daily_report.daily_rows:
            CampaignDatasetBuilder._add_gap(
                dataset, 'daily_actuals', '일자별 실적',
                '데일리리포트를 읽지 못해 성과 수치를 만들 수 없습니다.',
                'blocking', 'table', ['운영 요약', '매체별 성과', '일자별 추이'])

        # 4) 소재 이미지 — 프로젝트 전체에 이미지 자산이 없음
        CampaignDatasetBuilder._add_gap(
            dataset, 'creative_assets', '소재 이미지 파일',
            '캠페인 폴더에 이미지·영상 소재 파일이 없습니다. '
            '소재명은 미디어믹스에서 확보되나 썸네일은 직접 넣어야 합니다.',
            'advisory', 'textarea', ['캠페인 전략', '소재별 집행 결과'])

    @staticmethod
    def _report_to_checklist(knowledge: CampaignKnowledge,
                             dataset: CampaignDataset) -> None:
        """결손과 경고를 Checklist 에 반영한다 (조용한 소실 금지)"""
        # 'Full / Lite' 는 내부 모드 이름이다. Checklist 는 보고서 1페이지에
        # 그대로 실려 광고주도 보게 되므로, 제품 내부 용어를 남기지 않는다.
        mode_label = ('포스트바이를 포함해 구성' if dataset.mode == 'full'
                      else '포스트바이 없이 구성')
        knowledge.add_checklist_item(ChecklistItem(
            type='dataset_mode',
            severity='info',
            message=f'데이터 구성: {mode_label}',
            detail='; '.join(f'{k}={v}' for k, v in dataset.summary().items()),
            source='dataset_builder:build',
        ))

        for gap in dataset.gaps:
            knowledge.add_checklist_item(ChecklistItem(
                type=f'data_gap:{gap.key}',
                severity='error' if gap.severity == 'blocking' else 'warning',
                message=f'자동 추출 실패: {gap.label}',
                detail=f'{gap.reason} / 영향받는 슬라이드: {", ".join(gap.affected_slides) or "-"}',
                source='dataset_builder:_collect_gaps',
            ))

        for w in dataset.warnings:
            knowledge.add_checklist_item(ChecklistItem(
                type='parser_warning',
                severity='info',
                message='파서 경고',
                detail=w,
                source='dataset_builder',
            ))
