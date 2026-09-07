# -*- coding: utf-8 -*-
"""
Checklist Manager - Manage and format checklist items
"""

from typing import List, Dict
from models.checklist import ChecklistItem
from models.campaign_knowledge import CampaignKnowledge


class ChecklistManager:
    """Checklist 항목을 관리하고 포맷팅합니다"""

    SEVERITY_ORDER = {'error': 0, 'warning': 1, 'info': 2}

    @staticmethod
    def sort_checklist(knowledge: CampaignKnowledge) -> List[ChecklistItem]:
        """
        Checklist 항목들을 심각도별로 정렬합니다.

        Args:
            knowledge: CampaignKnowledge 객체

        Returns:
            정렬된 ChecklistItem 리스트
        """
        items = knowledge.get_checklist_items()
        return sorted(
            items,
            key=lambda x: (
                ChecklistManager.SEVERITY_ORDER.get(x.severity, 3),
                x.type
            )
        )

    @staticmethod
    def deduplicate_checklist(knowledge: CampaignKnowledge) -> None:
        """
        Checklist에서 중복 항목을 제거합니다.

        Args:
            knowledge: CampaignKnowledge 객체
        """
        items = knowledge.validation['checklist_items']
        unique_items = {}

        for item in items:
            # 유니크 키: type + message
            key = f"{item.type}:{item.message}"
            if key not in unique_items:
                unique_items[key] = item

        knowledge.validation['checklist_items'] = list(unique_items.values())

    @staticmethod
    def get_checklist_summary(knowledge: CampaignKnowledge) -> Dict[str, int]:
        """
        Checklist 요약 통계를 반환합니다.

        Args:
            knowledge: CampaignKnowledge 객체

        Returns:
            {'errors': int, 'warnings': int, 'infos': int, 'total': int}
        """
        items = knowledge.get_checklist_items()
        return {
            'errors': len([i for i in items if i.severity == 'error']),
            'warnings': len([i for i in items if i.severity == 'warning']),
            'infos': len([i for i in items if i.severity == 'info']),
            'total': len(items)
        }

    @staticmethod
    def format_checklist_for_ppt(knowledge: CampaignKnowledge) -> str:
        """
        Checklist을 PPT 슬라이드용 텍스트로 포맷팅합니다.

        Args:
            knowledge: CampaignKnowledge 객체

        Returns:
            포맷팅된 텍스트
        """
        ChecklistManager.deduplicate_checklist(knowledge)
        sorted_items = ChecklistManager.sort_checklist(knowledge)

        output = []
        output.append("=" * 60)
        output.append("[Checklist] - 최종 검수 및 보정 항목")
        output.append("=" * 60)
        output.append("")

        if not sorted_items:
            output.append("✓ 모든 검증 완료 - 예외사항 없음")
            output.append("")
        else:
            # 심각도별로 그룹화
            errors = [i for i in sorted_items if i.severity == 'error']
            warnings = [i for i in sorted_items if i.severity == 'warning']
            infos = [i for i in sorted_items if i.severity == 'info']

            if errors:
                output.append("❌ [필수 확인] 오류 항목:")
                output.append("")
                for item in errors:
                    output.append(f"  • {item.message}")
                    output.append(f"    └─ {item.detail}")
                output.append("")

            if warnings:
                output.append("⚠️ [권장 확인] 경고 항목:")
                output.append("")
                for item in warnings:
                    output.append(f"  • {item.message}")
                    output.append(f"    └─ {item.detail}")
                output.append("")

            if infos:
                output.append("ℹ️ [정보] 참고 항목:")
                output.append("")
                for item in infos:
                    output.append(f"  • {item.message}")
                    if item.detail:
                        output.append(f"    └─ {item.detail}")
                output.append("")

        summary = ChecklistManager.get_checklist_summary(knowledge)
        output.append("-" * 60)
        output.append(f"총 건수: {summary['total']} | 오류: {summary['errors']} | 경고: {summary['warnings']} | 정보: {summary['infos']}")
        output.append("=" * 60)

        return "\n".join(output)

    @staticmethod
    def print_checklist(knowledge: CampaignKnowledge) -> None:
        """
        Checklist을 콘솔에 출력합니다.

        Args:
            knowledge: CampaignKnowledge 객체
        """
        print(ChecklistManager.format_checklist_for_ppt(knowledge))
