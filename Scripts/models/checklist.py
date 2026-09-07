# -*- coding: utf-8 -*-
"""
Checklist Item model for Campaign Knowledge validation
"""

from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ChecklistItem:
    """
    Checklist에 기록될 예외사항 항목
    """
    type: str                          # "input_missing", "format_mismatch", "data_anomaly" 등
    severity: str                      # "error", "warning", "info"
    message: str                       # 사용자 친화적 메시지
    detail: str                        # 기술적 상세 설명
    source: str                        # 어느 단계/파일에서 발견됐는지
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def __str__(self) -> str:
        """문자열 표현"""
        severity_icon = {
            'error': '❌',
            'warning': '⚠️',
            'info': 'ℹ️'
        }
        icon = severity_icon.get(self.severity, '•')
        return f"{icon} [{self.type}] {self.message}"

    def to_dict(self) -> dict:
        """딕셔너리로 변환"""
        return {
            'type': self.type,
            'severity': self.severity,
            'message': self.message,
            'detail': self.detail,
            'source': self.source,
            'timestamp': self.timestamp
        }
