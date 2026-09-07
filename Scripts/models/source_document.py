# -*- coding: utf-8 -*-
"""
SourceDocument - 인풋 문서 1급 객체

Rule Book 2.0 (데이터 보존 원칙):
캠페인 폴더에는 같은 역할의 문서가 여러 개 존재하는 것이 정상이므로,
단일 슬롯에 대입하지 않고 이 객체의 리스트로 전량 보존한다.
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class SourceDocument:
    """파싱된 인풋 문서 하나를 온전히 담는 객체"""

    file_name: str
    file_path: str = ""                 # 직렬화 시 캠페인 폴더 기준 상대경로로 변환됨
    file_type: str = ""                 # "pdf", "xlsx", "pptx", "docx"
    encoding: str = "utf-8"

    # ===== 역할 추론 =====
    role: str = "unknown"               # document_roles.json 의 역할 키
    role_label: str = ""                # 사람이 읽는 역할명 ("미디어 믹스" 등)
    confidence: float = 0.0             # 0.0 ~ 1.0
    role_confirmed_by: str = "auto"     # "auto" | "human" (Stage 1.5에서 사람이 확정 시)
    role_scores: Dict[str, float] = field(default_factory=dict)  # 후보별 점수 (근거 제시용)

    # ===== 파싱 결과 (절단 없이 전량 보존) =====
    text_content: str = ""
    tables: List[Dict[str, Any]] = field(default_factory=list)

    # ===== 상태 =====
    status: str = "found"               # "found" | "error" | "skipped"
    error_msg: Optional[str] = None

    # ===== 파생 정보 =====
    def table_row_count(self) -> int:
        """보유한 표의 총 행 수"""
        return sum(len(t.get('data', []) or []) for t in self.tables)

    def is_usable(self) -> bool:
        """분석에 사용 가능한 상태인지"""
        return self.status == 'found'

    def to_dict(self) -> dict:
        """딕셔너리로 변환 (직렬화용). from_dict 와 대칭이어야 함."""
        return {
            'file_name': self.file_name,
            'file_path': self.file_path,
            'file_type': self.file_type,
            'encoding': self.encoding,
            'role': self.role,
            'role_label': self.role_label,
            'confidence': self.confidence,
            'role_confirmed_by': self.role_confirmed_by,
            'role_scores': self.role_scores,
            'text_content': self.text_content,
            'tables': self.tables,
            'status': self.status,
            'error_msg': self.error_msg,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'SourceDocument':
        """딕셔너리에서 복원. to_dict 와 대칭이어야 함."""
        return cls(
            file_name=data.get('file_name', ''),
            file_path=data.get('file_path', ''),
            file_type=data.get('file_type', ''),
            encoding=data.get('encoding', 'utf-8'),
            role=data.get('role', 'unknown'),
            role_label=data.get('role_label', ''),
            confidence=data.get('confidence', 0.0),
            role_confirmed_by=data.get('role_confirmed_by', 'auto'),
            role_scores=data.get('role_scores', {}) or {},
            text_content=data.get('text_content', ''),
            tables=data.get('tables', []) or [],
            status=data.get('status', 'found'),
            error_msg=data.get('error_msg'),
        )
