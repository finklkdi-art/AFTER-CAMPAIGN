# -*- coding: utf-8 -*-
"""
Knowledge Builder - 파싱 결과를 Campaign Knowledge 로 조립

Rule Book 2.0 (데이터 보존 원칙) 준수:
- 모든 문서를 documents 레지스트리에 전량 보존 (덮어쓰기 금지)
- 행 절단 금지
- 보존/판정에 문제가 생기면 반드시 Checklist 기재

proposal / postbuy 단일 슬롯은 구버전 호환용 '대표 문서' 뷰로만 유지되며,
전체 데이터는 knowledge.documents 에서 조회할 것.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from models.campaign_knowledge import CampaignKnowledge
from models.checklist import ChecklistItem
from models.source_document import SourceDocument
from utils.role_classifier import RoleClassifier


# 기간 표기 추출용 (예: "2025.04.21 ~ 2025.07.19", "2025-04-21~07-19")
_PERIOD_PATTERN = re.compile(
    r'(20\d{2})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})\s*일?'
    r'\s*[~\-–—]\s*'
    r'(?:(20\d{2})\s*[.\-/년]\s*)?(\d{1,2})\s*[.\-/월]\s*(\d{1,2})'
)


class KnowledgeBuilder:
    """파싱된 데이터를 Campaign Knowledge 객체로 변환합니다"""

    @staticmethod
    def extract_period(text: str) -> Optional[str]:
        """
        본문에서 캠페인 기간 표기를 추출합니다.

        정규식이 실제로 매칭된 구간만 반환하며, 찾지 못하면 None을 반환합니다.
        (추측으로 채우지 않음 — Rule Book 2.1)

        Args:
            text: 문서 본문

        Returns:
            기간 문자열 또는 None
        """
        if not text:
            return None
        match = _PERIOD_PATTERN.search(text)
        return match.group(0).strip() if match else None

    @staticmethod
    def build_knowledge(
        campaign_id: str,
        campaign_name: str,
        folder_path: str,
        parsed_files: Dict[str, Dict[str, Any]],
        validator=None,
        classifier: Optional[RoleClassifier] = None,
    ) -> CampaignKnowledge:
        """
        파싱된 파일들로부터 Campaign Knowledge를 구성합니다.

        Args:
            campaign_id: 캠페인 ID
            campaign_name: 캠페인명
            folder_path: 캠페인 폴더 경로
            parsed_files: {파일명: 파싱 결과}
            validator: (미사용, 시그니처 호환 유지)
            classifier: RoleClassifier 인스턴스 (None이면 새로 생성)

        Returns:
            CampaignKnowledge 객체
        """
        classifier = classifier or RoleClassifier()

        knowledge = CampaignKnowledge(
            campaign_id=campaign_id,
            campaign_name=campaign_name,
            folder_path=folder_path,
        )

        # 품목 추출 (하드코딩 없이 괄호 표기 + 별칭 사전)
        knowledge.category = classifier.infer_category(campaign_name)
        if not knowledge.category:
            knowledge.add_checklist_item(ChecklistItem(
                type='category_undetermined',
                severity='info',
                message='품목을 자동으로 판별하지 못함',
                detail=f'캠페인명 "{campaign_name}"에서 품목을 추출하지 못했습니다. '
                       f'출력 파일명 규칙에 필요하므로 검증 화면에서 입력하세요.',
                source='knowledge_builder:build_knowledge',
            ))

        # ===== 1) 모든 문서를 레지스트리에 보존 =====
        for file_name, parsed in parsed_files.items():
            KnowledgeBuilder._register_document(knowledge, file_name, parsed, classifier)

        # ===== 2) 역할 판정 결과를 Checklist에 반영 =====
        KnowledgeBuilder._report_role_issues(knowledge, classifier)

        # ===== 3) 구버전 호환 뷰 구성 =====
        KnowledgeBuilder._fill_legacy_slots(knowledge, classifier)

        return knowledge

    # ------------------------------------------------------------------
    # 1) 문서 등록
    # ------------------------------------------------------------------

    @staticmethod
    def _register_document(
        knowledge: CampaignKnowledge,
        file_name: str,
        parsed: Dict[str, Any],
        classifier: RoleClassifier,
    ) -> None:
        """파싱 결과 하나를 SourceDocument 로 만들어 레지스트리에 보존합니다."""
        # 파싱 실패도 기록으로 남긴다 (조용한 소실 금지)
        if parsed.get('status') == 'error':
            knowledge.add_document(SourceDocument(
                file_name=file_name,
                file_path=parsed.get('file_path', ''),
                file_type=parsed.get('file_type', ''),
                status='error',
                error_msg=parsed.get('error_msg', 'Unknown error'),
            ))
            knowledge.add_checklist_item(ChecklistItem(
                type='file_parse_error',
                severity='warning',
                message=f'파일 파싱 실패: {file_name}',
                detail=parsed.get('error_msg', 'Unknown error'),
                source=f'file_parser:{file_name}',
            ))
            return

        text_content = parsed.get('text_content', '') or ''
        classifier.last_reason = ''
        role, confidence, scores = classifier.classify(file_name, text_content)

        # '…보고' 구제 규칙이 발동했으면 근거를 남긴다 — 파일명만 보고 붙인
        # 역할이므로 사람이 확인해야 한다 (claude.md 3.3)
        if scores.get('_generic_report') and classifier.last_reason:
            knowledge.add_checklist_item(ChecklistItem(
                type='role_inferred_generic_report',
                severity='warning' if confidence < 0.5 else 'info',
                message=f"'{file_name}' 역할을 {classifier.label_of(role)}(으)로 추정 — 확인 필요",
                detail=classifier.last_reason,
                source=f'role_classifier:{file_name}',
            ))

        knowledge.add_document(SourceDocument(
            file_name=file_name,
            file_path=parsed.get('file_path', ''),
            file_type=parsed.get('file_type', ''),
            encoding=parsed.get('encoding', 'utf-8'),
            role=role,
            role_label=classifier.label_of(role),
            confidence=confidence,
            role_confirmed_by='auto',
            role_scores=scores,
            text_content=text_content,       # 절단 없음
            tables=parsed.get('tables', []) or [],   # 절단 없음
            status='found',
        ))

    # ------------------------------------------------------------------
    # 2) 역할 판정 이슈 보고
    # ------------------------------------------------------------------

    @staticmethod
    def _report_role_issues(knowledge: CampaignKnowledge, classifier: RoleClassifier) -> None:
        """역할 미확정·동일 역할 다수 상황을 Checklist에 기재합니다."""
        usable = knowledge.get_documents()

        # 역할 미확정
        for doc in usable:
            if doc.role == 'unknown':
                knowledge.add_checklist_item(ChecklistItem(
                    type='role_undetermined',
                    severity='warning',
                    message=f'문서 역할 미확정: {doc.file_name}',
                    detail=f'파일명에서 역할 단서를 찾지 못했습니다 '
                           f'(표 {doc.table_row_count():,}행 보유). '
                           f'검증 화면에서 역할을 지정하세요.',
                    source='role_classifier:classify',
                ))

        # 동일 역할 다수 — 정상 상황이지만 대표 문서 확인이 필요함
        by_role: Dict[str, List[SourceDocument]] = {}
        for doc in usable:
            if doc.role != 'unknown':
                by_role.setdefault(doc.role, []).append(doc)

        for role, docs in by_role.items():
            if len(docs) > 1:
                names = ', '.join(d.file_name for d in docs)
                knowledge.add_checklist_item(ChecklistItem(
                    type='role_multiple_documents',
                    severity='info',
                    message=f'{classifier.label_of(role)} 문서 {len(docs)}건 감지',
                    detail=f'모두 보존되었습니다. 대표 문서 지정을 확인하세요 — {names}',
                    source='knowledge_builder:_report_role_issues',
                ))

        # 보존 현황 요약 (데이터 소실 여부를 사람이 대조할 수 있게)
        if usable:
            knowledge.validation['file_format_status']['documents_preserved'] = len(usable)
            knowledge.validation['file_format_status']['total_table_rows'] = \
                knowledge.total_table_rows()

    # ------------------------------------------------------------------
    # 3) 구버전 호환 뷰
    # ------------------------------------------------------------------

    @staticmethod
    def _select_representative(
        knowledge: CampaignKnowledge,
        priority_roles: List[str],
    ) -> Tuple[Optional[SourceDocument], List[SourceDocument]]:
        """
        우선순위에 따라 대표 문서를 고르고, 해당 슬롯에 속한 전체 문서를 함께 반환합니다.

        Returns:
            (대표 문서 또는 None, 슬롯 소속 문서 전체)
        """
        members: List[SourceDocument] = []
        for role in priority_roles:
            members.extend(knowledge.get_documents(role))

        if not members:
            return None, []

        # 우선순위가 앞선 역할을 먼저, 같은 역할이면 표가 많은 문서를 대표로
        rank = {role: i for i, role in enumerate(priority_roles)}
        representative = min(
            members,
            key=lambda d: (rank.get(d.role, len(priority_roles)), -d.table_row_count()),
        )
        return representative, members

    @staticmethod
    def _fill_legacy_slots(knowledge: CampaignKnowledge, classifier: RoleClassifier) -> None:
        """
        구버전 proposal / postbuy 슬롯과 supporting_documents 를 채웁니다.

        데이터의 단일 원천은 documents 이며, 여기서는 뷰만 구성합니다.
        어떤 문서도 이 과정에서 소실되지 않습니다.
        """
        slot_specs = [
            ('proposal', knowledge.proposal, 'kpi_plan', 'campaign_period'),
            ('postbuy', knowledge.postbuy, 'kpi_actual', 'report_period'),
        ]
        represented: set = set()

        for slot_name, slot, kpi_key, period_key in slot_specs:
            priority = classifier.legacy_slot_priority(slot_name)
            representative, members = KnowledgeBuilder._select_representative(knowledge, priority)

            if representative is None:
                slot['status'] = 'missing'
                continue

            slot['file_path'] = representative.file_path
            slot['file_name'] = representative.file_name
            slot['file_type'] = representative.file_type
            slot['encoding'] = representative.encoding
            slot['status'] = 'found'
            slot['detected_role'] = representative.role
            slot['confidence'] = representative.confidence

            # raw_extracted_data 는 documents 의 완전한 중복이므로 채우지 않는다.
            # (원본 텍스트·표는 knowledge.get_documents() 로 조회할 것)
            # 중복 저장 시 감사 스냅샷이 3배로 불어남 — 2026.08.30 측정 11.4MB -> 4.0MB
            slot['raw_extracted_data'] = {'source': 'documents', 'file_name': representative.file_name}

            # 기간 추출 (매칭된 구간만, 실패 시 None 유지)
            period = KnowledgeBuilder.extract_period(representative.text_content)
            if period:
                slot['metadata'][period_key] = period

            # KPI 후보는 슬롯에 속한 전체 문서에서 모은다 (대표 문서만 보지 않음)
            for doc in members:
                represented.add(doc.file_name)
                for table in doc.tables:
                    data = table.get('data') or []
                    if not data:
                        continue
                    slot[kpi_key].append({
                        'source': f'{doc.file_name}:{table.get("sheet_name", table.get("page", ""))}',
                        'role': doc.role,
                        'data': data,          # 절단 없음
                    })

        # 어느 슬롯에도 속하지 않은 문서 (creative, unknown 등)
        for doc in knowledge.get_documents():
            if doc.file_name in represented:
                continue
            # 본문·표는 documents 에 이미 전량 보존되어 있으므로 여기서는 중복하지 않는다
            knowledge.supporting_documents.append({
                'file_name': doc.file_name,
                'file_type': doc.file_type,
                'file_path': doc.file_path,
                'detected_role': doc.role,
                'role_label': doc.role_label,
                'confidence': doc.confidence,
                'table_row_count': doc.table_row_count(),
            })
