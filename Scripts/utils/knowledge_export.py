# -*- coding: utf-8 -*-
"""
Knowledge Export/Import - Handle Campaign Knowledge serialization for human review
"""

import json
import os
from pathlib import Path
from typing import Dict, Any
from datetime import datetime
from models.campaign_knowledge import CampaignKnowledge
from models.checklist import ChecklistItem
from utils.serialization import normalize_for_json, to_portable_path, from_portable_path


# 경로 필드를 담고 있는 위치 (직렬화 시 상대경로로 변환)
def _portablize_paths(data: Dict[str, Any], base_dir: str) -> Dict[str, Any]:
    """file_path 들을 캠페인 폴더 기준 상대경로로 변환합니다."""
    for slot in ('proposal', 'postbuy'):
        if isinstance(data.get(slot), dict) and data[slot].get('file_path'):
            data[slot] = dict(data[slot])
            data[slot]['file_path'] = to_portable_path(data[slot]['file_path'], base_dir)

    for key in ('documents', 'supporting_documents'):
        items = data.get(key)
        if isinstance(items, list):
            data[key] = [
                {**item, 'file_path': to_portable_path(item.get('file_path', ''), base_dir)}
                if isinstance(item, dict) else item
                for item in items
            ]
    return data


def _restore_paths(knowledge: CampaignKnowledge) -> None:
    """상대경로를 현재 PC 기준 절대경로로 복원합니다."""
    base = knowledge.folder_path
    for slot in (knowledge.proposal, knowledge.postbuy):
        if slot.get('file_path'):
            slot['file_path'] = from_portable_path(slot['file_path'], base)
    for doc in knowledge.documents:
        doc.file_path = from_portable_path(doc.file_path, base)
    for doc in knowledge.supporting_documents:
        if isinstance(doc, dict) and doc.get('file_path'):
            doc['file_path'] = from_portable_path(doc['file_path'], base)


class KnowledgeExport:
    """Campaign Knowledge를 파일로 내보내고 가져옵니다"""

    @staticmethod
    def export_to_json(knowledge: CampaignKnowledge, output_dir: str) -> str:
        """
        Campaign Knowledge를 JSON 파일로 내보냅니다.

        Args:
            knowledge: CampaignKnowledge 객체
            output_dir: 출력 디렉토리

        Returns:
            생성된 파일 경로
        """
        os.makedirs(output_dir, exist_ok=True)

        # 파일명 생성
        timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
        filename = f"Draft_Knowledge_{timestamp}.json"
        file_path = os.path.join(output_dir, filename)

        # JSON으로 변환
        data = knowledge.to_dict()

        # 경로를 캠페인 폴더 기준 상대경로로 (AE 간 이식성 확보)
        data = _portablize_paths(data, knowledge.folder_path)

        # NaN / Infinity / Timestamp 등 비표준 값을 표준 JSON으로 정규화
        data = normalize_for_json(data)

        # 파일 저장 (allow_nan=False 로 비표준 토큰 유입을 차단)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)

        return file_path

    @staticmethod
    def export_to_markdown(knowledge: CampaignKnowledge, output_dir: str) -> str:
        """
        Campaign Knowledge를 Markdown 형식으로 내보냅니다.

        Args:
            knowledge: CampaignKnowledge 객체
            output_dir: 출력 디렉토리

        Returns:
            생성된 파일 경로
        """
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
        filename = f"Draft_Knowledge_{timestamp}.md"
        file_path = os.path.join(output_dir, filename)

        content = []
        content.append("# Campaign Knowledge - 기획자 검증용 임시 문서")
        content.append(f"\n**생성일**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        content.append(f"**캠페인 ID**: {knowledge.campaign_id}\n")

        # ========== 메타데이터 섹션 (최상단) ==========
        content.append("\n## [필수 검증] 캠페인 메타데이터 및 기본 요소\n")
        content.append("⚠️ **아래 항목들은 기획자가 반드시 검증/교정하세요.**\n")

        content.append("### 1. 제품명 및 캠페인명")
        content.append(f"- 제품명: {knowledge.category}")
        content.append(f"- 캠페인명: {knowledge.campaign_name}")
        content.append(f"- 캠페인 ID: {knowledge.campaign_id}\n")

        content.append("### 2. KPI 기준 및 단위")
        content.append("**제안서 KPI:**")
        if knowledge.proposal.get('kpi_plan'):
            for i, kpi in enumerate(knowledge.proposal.get('kpi_plan', [])[:3], 1):
                content.append(f"  {i}. {kpi}")
        else:
            content.append("  - 자동 추출 실패 (수동 확인 필요)")

        content.append("\n**포스트바이 KPI:**")
        if knowledge.postbuy.get('kpi_actual'):
            for i, kpi in enumerate(knowledge.postbuy.get('kpi_actual', [])[:3], 1):
                content.append(f"  {i}. {kpi}")
        else:
            content.append("  - 자동 추출 실패 (수동 확인 필요)")

        content.append("\n### 3. 크리에이티브(소재) 정보")
        content.append("- 가로형 영상: (수동 입력 필요)")
        content.append("- 세로형 숏폼: (수동 입력 필요)")
        content.append("- 디지털 배너: (수동 입력 필요)")
        content.append("- 기타: (수동 입력 필요)\n")

        content.append("### 4. 매체 변동사항 (제안서 vs 포스트바이)")
        proposal_file = knowledge.proposal.get('file_name', 'N/A')
        postbuy_file = knowledge.postbuy.get('file_name', 'N/A')
        content.append(f"- 제안서: {proposal_file}")
        content.append(f"- 포스트바이: {postbuy_file}")
        content.append("- 매체 누락/드랍 여부: (확인 필요)\n")

        # ========== 상세 데이터 ==========
        content.append("\n## 상세 데이터\n")

        content.append("### 제안서(Proposal) 정보")
        proposal = knowledge.proposal
        content.append(f"- 상태: {proposal.get('status', 'N/A')}")
        content.append(f"- 파일명: {proposal.get('file_name', 'N/A')}")
        content.append(f"- 형식: {proposal.get('file_type', 'N/A')}")
        content.append(f"- 인코딩: {proposal.get('encoding', 'N/A')}")
        content.append(f"- 추론 역할: {proposal.get('detected_role', 'N/A')} (신뢰도: {proposal.get('confidence', 0):.0%})\n")

        content.append("### 포스트바이(PostBuy) 정보")
        postbuy = knowledge.postbuy
        content.append(f"- 상태: {postbuy.get('status', 'N/A')}")
        content.append(f"- 파일명: {postbuy.get('file_name', 'N/A')}")
        content.append(f"- 형식: {postbuy.get('file_type', 'N/A')}")
        content.append(f"- 인코딩: {postbuy.get('encoding', 'N/A')}")
        content.append(f"- 추론 역할: {postbuy.get('detected_role', 'N/A')} (신뢰도: {postbuy.get('confidence', 0):.0%})\n")

        content.append("### Checklist 항목")
        checklist = knowledge.get_checklist_items()
        if checklist:
            for item in checklist:
                content.append(f"- [{item.severity.upper()}] {item.message}")
                content.append(f"  └─ {item.detail}")
        else:
            content.append("- 예외사항 없음 (정상)")

        content.append("\n---\n")
        content.append("**검증 완료 후 저장하세요. 이 파일이 자동 인식됩니다.**")

        # 파일 저장
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(content))

        return file_path

    @staticmethod
    def import_from_json(file_path: str) -> CampaignKnowledge:
        """
        JSON 파일에서 Campaign Knowledge를 복원합니다.

        Args:
            file_path: JSON 파일 경로

        Returns:
            복원된 CampaignKnowledge 객체
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 복원은 CampaignKnowledge.from_dict 에 위임한다.
        # to_dict 와 한 곳에서 짝으로 관리되므로 필드 누락에 의한 소실이 발생하지 않음.
        knowledge = CampaignKnowledge.from_dict(data)

        # 상대경로를 현재 PC 기준으로 되돌림
        _restore_paths(knowledge)

        return knowledge


class KnowledgeValidator:
    """기획자가 수정한 데이터를 검증합니다"""

    @staticmethod
    def validate_metadata(knowledge: CampaignKnowledge) -> list:
        """
        메타데이터 검증

        Args:
            knowledge: CampaignKnowledge 객체

        Returns:
            검증 오류 리스트
        """
        errors = []

        # 캠페인명 확인
        if not knowledge.campaign_name:
            errors.append("캠페인명이 비어있습니다")

        # 제안서/포스트바이 최소 하나 확인
        if (knowledge.proposal['status'] == 'missing' and
            knowledge.postbuy['status'] == 'missing'):
            errors.append("제안서와 포스트바이 중 최소 하나는 있어야 합니다")

        return errors
