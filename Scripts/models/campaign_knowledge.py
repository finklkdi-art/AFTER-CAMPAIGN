# -*- coding: utf-8 -*-
"""
Campaign Knowledge - Main data structure for storing parsed campaign information
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from .checklist import ChecklistItem
from .source_document import SourceDocument

# 직렬화 포맷 버전. from_dict 가 구버전 데이터를 식별하는 데 사용함
SCHEMA_VERSION = 2


@dataclass
class CampaignKnowledge:
    """
    캠페인 전체 정보를 담는 메모리 객체
    제안서(Proposal) + 포스트바이(PostBuy) 데이터 통합 저장
    """

    # ========== 메타데이터 ==========
    campaign_id: str                    # "260820_가전_결과리포트"
    campaign_name: str                  # "CE 통합 신혼 캠페인" 또는 폴더명
    category: str = ""                  # "가전", "에어컨" 등
    date_created: str = ""              # "260820" 또는 현재 시각
    folder_path: str = ""               # Input 폴더의 실제 경로
    advertiser: str = ""                # "삼성전자" — Stage 1.5 에서 AE 직접 입력

    # ========== 제안서(Proposal) 데이터 ==========
    proposal: Dict[str, Any] = field(default_factory=lambda: {
        "file_path": None,
        "file_name": None,
        "file_type": None,              # "pdf", "xlsx", "pptx", "docx"
        "encoding": "utf-8",
        "status": "missing",            # "found", "missing", "error"
        "error_msg": None,
        "detected_role": None,          # 동적 추론된 역할
        "confidence": 0.0,              # 역할 추론 신뢰도 (0.0~1.0)

        "metadata": {
            "campaign_period": None,    # "2026.08.01 ~ 2026.08.31"
            "budget_total": None,       # 전체 예산
            "target_audience": None,    # "20-30대 고소득층"
            "campaign_goal": None,      # 캠페인 목표
            "extracted_from": []        # 어느 파일에서 추출됐는지
        },

        "kpi_plan": [],                 # 계획된 KPI 목록
        "media_mix": [],                # 매체별 예산/전략
        "strategy_details": {},         # 상세 전략 정보
        "raw_extracted_data": {}        # 원본 파일에서 추출한 모든 데이터
    })

    # ========== 포스트바이(PostBuy) 데이터 ==========
    postbuy: Dict[str, Any] = field(default_factory=lambda: {
        "file_path": None,
        "file_name": None,
        "file_type": None,
        "encoding": "utf-8",
        "status": "missing",
        "error_msg": None,
        "detected_role": None,          # 동적 추론된 역할
        "confidence": 0.0,

        "metadata": {
            "report_period": None,
            "actual_spend": None,
            "report_date": None,
            "extracted_from": []
        },

        "kpi_actual": [],               # 실제 성과 KPI
        "media_performance": [],        # 매체별 성과
        "summary_statistics": {},       # 종합 통계
        "raw_extracted_data": {}
    })

    # ========== 추가 보조 문서들 (미디어브리프, 데일리리포트 등) ==========
    supporting_documents: List[Dict[str, Any]] = field(default_factory=list)

    # ========== 문서 레지스트리 (Rule Book 2.0 데이터 보존 원칙) ==========
    # 파싱된 모든 인풋 문서를 절단·덮어쓰기 없이 보존하는 단일 원천.
    # 위의 proposal / postbuy / supporting_documents 는 구버전 호환용 '대표 문서' 뷰이며,
    # 전체 데이터는 항상 이 리스트를 통해 조회할 것.
    documents: List[SourceDocument] = field(default_factory=list)

    # ========== Part 1 캠페인 개요 (기획 의도) ==========
    # 제안서·미디어브리프 등 '실행 前 의도'를 담은 문서에서 추출한다.
    # 제안서가 이미지 PDF 라 텍스트가 안 나오는 경우가 잦아, 미디어브리프·
    # 포스트바이까지 그물망으로 훑고 결과가 비면 렌더러가 작성 가이드를 깐다.
    overview: Dict[str, Any] = field(default_factory=lambda: {
        "goal": {
            "challenge": "",        # 당면 과제 — 왜 진행했는가
            "core_target": "",      # 핵심 타겟
            "key_message": "",      # 메인 카피 / 슬로건
        },
        "strategy": {
            "direction": "",        # 미디어·크리에이티브 믹스 방향성
            "channels": [],         # 활용 핵심 채널 리스트
        },
        "roadmap": {
            "period": "",           # 전체 캠페인 기간
            "phases": [],           # [{"name","period","purpose"}]
        },
        "sources": [],              # 어느 문서에서 왔는지 (파일명)
        "confidence": "none",       # high | medium | low | none
        "edited_by_ae": False,      # Stage 1.5 에서 사람이 손댔는지
    })

    # ========== Stage 1.5 기획자 검증 입력 ==========
    # 원본 추출 데이터(kpi_plan/kpi_actual)는 추적성을 위해 보존하고,
    # 기획자가 정리한 값은 아래 필드에 별도 저장함
    verified_kpi: List[Dict[str, Any]] = field(default_factory=list)
    creative_info: Dict[str, Any] = field(default_factory=dict)

    # ========== 검증 및 예외 정보 ==========
    validation: Dict[str, Any] = field(default_factory=lambda: {
        "checklist_items": [],          # ChecklistItem 객체들
        "encoding_status": {
            "proposal_encoding": None,
            "postbuy_encoding": None,
            "issues": []
        },
        "file_format_status": {
            "proposal_format": None,
            "postbuy_format": None,
            "issues": []
        },
        "data_coherence": {
            "kpi_matching_issues": [],  # KPI 필드명 불일치 등
            "time_range_issues": [],    # 시간 범위 불일치
            "data_anomalies": []        # 이상치 (음수값, 극단값 등)
        }
    })

    # ========== 추적 정보 ==========
    pipeline_log: Dict[str, Any] = field(default_factory=lambda: {
        "step1_completed": False,
        "step1_timestamp": None,
        "step2_completed": False,
        "step3_completed": False,
        "step4_completed": False,
        "errors_count": 0,
        "warnings_count": 0,
        "info_count": 0,
        "total_checks_performed": 0,
        "execution_time_seconds": 0.0
    })

    def add_checklist_item(self, item: ChecklistItem) -> None:
        """Checklist 항목 추가"""
        self.validation['checklist_items'].append(item)

        # 심각도별 카운트 업데이트
        if item.severity == 'error':
            self.pipeline_log['errors_count'] += 1
        elif item.severity == 'warning':
            self.pipeline_log['warnings_count'] += 1
        elif item.severity == 'info':
            self.pipeline_log['info_count'] += 1

    def get_checklist_items(self, severity: Optional[str] = None) -> List[ChecklistItem]:
        """Checklist 항목 조회"""
        items = self.validation['checklist_items']
        if severity:
            return [item for item in items if item.severity == severity]
        return items

    # ========== 문서 레지스트리 접근 ==========

    def add_document(self, document: SourceDocument) -> None:
        """문서를 레지스트리에 보존합니다. 기존 문서를 덮어쓰지 않습니다."""
        self.documents.append(document)

    def get_documents(self, role: Optional[str] = None,
                      usable_only: bool = True) -> List[SourceDocument]:
        """
        역할별 문서를 조회합니다.

        Args:
            role: 역할 키 (None이면 전체)
            usable_only: 파싱 성공한 문서만 반환할지 여부

        Returns:
            조건에 맞는 SourceDocument 리스트
        """
        docs = self.documents
        if usable_only:
            docs = [d for d in docs if d.is_usable()]
        if role is not None:
            docs = [d for d in docs if d.role == role]
        return docs

    def get_document(self, file_name: str) -> Optional[SourceDocument]:
        """파일명으로 문서를 찾습니다."""
        for doc in self.documents:
            if doc.file_name == file_name:
                return doc
        return None

    def role_counts(self) -> Dict[str, int]:
        """역할별 문서 개수 (Stage 1.5 역할 확정 화면에서 사용)"""
        counts: Dict[str, int] = {}
        for doc in self.documents:
            counts[doc.role] = counts.get(doc.role, 0) + 1
        return counts

    def total_table_rows(self) -> int:
        """보존 중인 표의 총 행 수 (데이터 소실 여부 점검용)"""
        return sum(doc.table_row_count() for doc in self.documents)

    def get_summary(self) -> Dict[str, Any]:
        """Campaign Knowledge 요약"""
        return {
            'campaign_id': self.campaign_id,
            'campaign_name': self.campaign_name,
            'category': self.category,
            'proposal_status': self.proposal['status'],
            'postbuy_status': self.postbuy['status'],
            'checklist_count': len(self.validation['checklist_items']),
            'errors': self.pipeline_log['errors_count'],
            'warnings': self.pipeline_log['warnings_count'],
            'infos': self.pipeline_log['info_count']
        }

    # ========== 직렬화 (to_dict 와 from_dict 는 반드시 대칭) ==========
    #
    # 경고: 한쪽에만 필드를 추가하면 데이터가 조용히 소실됨.
    # 필드를 추가할 때는 아래 두 메서드를 반드시 함께 고치고,
    # 라운드트립 테스트(test_roundtrip.py)로 대칭성을 확인할 것.

    # 두 메서드가 함께 다루어야 하는 단순 대입 필드 목록
    _PLAIN_FIELDS = (
        'campaign_id', 'campaign_name', 'category', 'date_created', 'folder_path',
        'advertiser',
        'proposal', 'postbuy', 'supporting_documents',
        'verified_kpi', 'creative_info', 'overview',
    )

    def to_dict(self) -> dict:
        """딕셔너리로 변환 (직렬화용). from_dict 와 대칭."""
        data: Dict[str, Any] = {'schema_version': SCHEMA_VERSION}

        for name in self._PLAIN_FIELDS:
            data[name] = getattr(self, name)

        data['documents'] = [doc.to_dict() for doc in self.documents]
        data['validation'] = {
            'checklist_items': [item.to_dict() for item in self.validation['checklist_items']],
            'encoding_status': self.validation['encoding_status'],
            'file_format_status': self.validation['file_format_status'],
            'data_coherence': self.validation['data_coherence'],
        }
        data['pipeline_log'] = self.pipeline_log
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'CampaignKnowledge':
        """딕셔너리에서 복원. to_dict 와 대칭."""
        knowledge = cls(
            campaign_id=data.get('campaign_id', ''),
            campaign_name=data.get('campaign_name', ''),
            category=data.get('category', ''),
            date_created=data.get('date_created', ''),
            folder_path=data.get('folder_path', ''),
        )

        # 생성자에서 이미 처리한 항목을 제외한 나머지 대입 필드
        for name in cls._PLAIN_FIELDS:
            if name in ('campaign_id', 'campaign_name', 'category',
                        'date_created', 'folder_path'):
                continue
            if name in data and data[name] is not None:
                setattr(knowledge, name, data[name])

        # 문서 레지스트리
        knowledge.documents = [
            SourceDocument.from_dict(d) for d in (data.get('documents') or [])
        ]

        # 검증 정보
        validation = data.get('validation') or {}
        knowledge.validation['checklist_items'] = [
            ChecklistItem(
                type=item.get('type', ''),
                severity=item.get('severity', 'info'),
                message=item.get('message', ''),
                detail=item.get('detail', ''),
                source=item.get('source', ''),
                timestamp=item.get('timestamp', ''),
            )
            for item in (validation.get('checklist_items') or [])
        ]
        for key in ('encoding_status', 'file_format_status', 'data_coherence'):
            if key in validation and validation[key] is not None:
                knowledge.validation[key] = validation[key]

        if data.get('pipeline_log'):
            knowledge.pipeline_log = data['pipeline_log']

        return knowledge
