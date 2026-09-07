# -*- coding: utf-8 -*-
"""
Checklist Manager - Manage and format checklist items
"""

from typing import Any, Dict, List
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
        Checklist에서 중복 항목을 합칩니다.

        같은 사건(type + message)이 여러 단계에서 보고될 수 있습니다.
        예전에는 **먼저 온 것만 남기고 나머지를 버렸는데**, 뒤에 온 항목이
        더 구체적인 detail 을 갖고 있으면 그 설명이 조용히 사라졌습니다
        (claude.md 3.1 — 조용한 소실은 최악의 실패). 이제 항목을 버리지 않고
        detail 을 이어 붙여 근거를 모두 보존합니다.

        심각도가 서로 다르면 더 높은 쪽을 남깁니다 — 한쪽이 '꼭 확인'이라고
        본 사건을 '참고'로 낮춰 보고하면 안 되기 때문입니다.

        Args:
            knowledge: CampaignKnowledge 객체
        """
        items = knowledge.validation['checklist_items']
        merged: Dict[str, Any] = {}
        order: List[str] = []

        for item in items:
            # 유니크 키: type + message
            key = f"{item.type}:{item.message}"
            if key not in merged:
                merged[key] = item
                order.append(key)
                continue

            kept = merged[key]
            new_detail = (getattr(item, 'detail', '') or '').strip()
            old_detail = (getattr(kept, 'detail', '') or '').strip()
            if new_detail and new_detail not in old_detail:
                kept.detail = f'{old_detail} / {new_detail}' if old_detail else new_detail
            # 심각도는 높은 쪽으로 끌어올린다
            if (ChecklistManager.SEVERITY_ORDER.get(item.severity, 3)
                    < ChecklistManager.SEVERITY_ORDER.get(kept.severity, 3)):
                kept.severity = item.severity

        knowledge.validation['checklist_items'] = [merged[k] for k in order]

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
