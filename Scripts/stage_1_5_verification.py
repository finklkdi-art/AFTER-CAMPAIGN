# -*- coding: utf-8 -*-
"""
Stage 1.5: Human-in-the-loop Verification and Data Correction
기획자가 AI 추출 데이터를 검증하고 교정하는 단계
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.campaign_knowledge import CampaignKnowledge
from utils.knowledge_export import KnowledgeExport, KnowledgeValidator


class Stage1p5Verification:
    """Stage 1.5: 기획자 검증 및 데이터 교정"""

    def __init__(self, project_root: str = None):
        """
        Args:
            project_root: 프로젝트 루트 경로
        """
        if project_root is None:
            project_root = Path(__file__).parent.parent
        self.project_root = Path(project_root)
        self.temp_dir = self.project_root / 'Output' / 'Temp'
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def verify_and_correct(self, knowledge: CampaignKnowledge) -> CampaignKnowledge:
        """
        기획자가 데이터를 검증하고 교정합니다.

        Args:
            knowledge: Stage 1에서 생성된 Campaign Knowledge

        Returns:
            기획자가 검증/교정한 Campaign Knowledge
        """
        print("\n" + "=" * 70)
        print("Stage 1.5: 기획자 검증 및 데이터 교정")
        print("=" * 70)

        # Step 1: 임시 파일 생성
        print("\n[1/3] 임시 파일 생성 중...")
        temp_file = self._export_knowledge(knowledge)
        print(f"  생성된 파일: {temp_file}")

        # Step 2: 사용자 대기
        print("\n[2/3] 기획자 검증 대기 중...")
        self._wait_for_verification(temp_file)

        # Step 3: 수정된 데이터 재입력
        print("\n[3/3] 수정된 데이터 재입력 중...")
        corrected_knowledge = self._import_corrected_data(temp_file, knowledge)

        print("\n✓ Stage 1.5 완료!")
        return corrected_knowledge

    def _export_knowledge(self, knowledge: CampaignKnowledge) -> str:
        """
        Campaign Knowledge를 임시 파일로 내보냅니다.

        Args:
            knowledge: CampaignKnowledge 객체

        Returns:
            생성된 파일 경로
        """
        # Markdown 형식으로 내보내기 (읽기 쉬움)
        md_file = KnowledgeExport.export_to_markdown(
            knowledge,
            str(self.temp_dir)
        )

        # JSON 형식으로도 저장 (데이터 재입력용)
        json_file = KnowledgeExport.export_to_json(
            knowledge,
            str(self.temp_dir)
        )

        print(f"  Markdown: {Path(md_file).name}")
        print(f"  JSON (교정용): {Path(json_file).name}")

        # 파일이 생성되었음을 확인
        if os.path.exists(md_file):
            print(f"\n  ✓ 임시 파일 생성 성공")
            print(f"  경로: {self.temp_dir}")
        else:
            raise FileNotFoundError(f"Failed to create temporary file: {md_file}")

        return json_file

    def _wait_for_verification(self, temp_file: str) -> None:
        """
        기획자의 검증이 완료될 때까지 대기합니다.

        Args:
            temp_file: 임시 파일 경로
        """
        print("\n" + "-" * 70)
        print("[기획자 검증 체크리스트]")
        print("-" * 70)
        print("다음 항목들을 꼼꼼히 검증/교정하세요:")
        print("  1. 제품명 및 캠페인명 (대소문자, 띄어쓰기)")
        print("  2. KPI 기준 및 단위 명확화")
        print("  3. 크리에이티브(소재) 정보 기입")
        print("  4. 제안서 vs 포스트바이 매체 변동사항 확인")
        print("  5. 숫자 데이터 오독 여부 확인")
        print("-" * 70)

        # 파일 위치 안내
        print(f"\n임시 파일 위치: {self.temp_dir}")
        print(f"  - 읽기용: *.md (텍스트 편집기로 열기)")
        print(f"  - 교정용: Draft_Knowledge_*.json (JSON 편집)")

        # 사용자 입력 대기
        print("\n" + "!" * 70)
        print("임시 파일을 열어 데이터를 검증/교정하세요.")
        print("완료되면 Enter 키를 눌러주세요.")
        print("!" * 70 + "\n")

        # 입력 대기
        try:
            input(">>> 검증 완료했으니 Enter를 눌러 계속 진행하세요: ")
        except KeyboardInterrupt:
            print("\n사용자가 중단했습니다.")
            sys.exit(1)

    def _import_corrected_data(
        self,
        temp_file: str,
        original_knowledge: CampaignKnowledge
    ) -> CampaignKnowledge:
        """
        수정된 임시 파일을 읽어서 Campaign Knowledge를 업데이트합니다.

        Args:
            temp_file: JSON 임시 파일 경로
            original_knowledge: 원본 Campaign Knowledge

        Returns:
            업데이트된 Campaign Knowledge
        """
        try:
            if not os.path.exists(temp_file):
                print(f"\n⚠️ 임시 파일을 찾을 수 없습니다: {temp_file}")
                print("원본 데이터를 사용합니다.")
                return original_knowledge

            # JSON 파일에서 복원
            corrected_knowledge = KnowledgeExport.import_from_json(temp_file)

            # 메타데이터 검증
            validation_errors = KnowledgeValidator.validate_metadata(corrected_knowledge)
            if validation_errors:
                print("\n⚠️ 데이터 검증 오류:")
                for error in validation_errors:
                    print(f"  - {error}")
                print("\n원본 데이터를 사용합니다.")
                return original_knowledge

            print(f"\n✓ 수정된 데이터 성공적으로 로드됨")
            print(f"  캠페인명: {corrected_knowledge.campaign_name}")
            print(f"  카테고리: {corrected_knowledge.category}")

            return corrected_knowledge

        except json.JSONDecodeError as e:
            print(f"\n✗ JSON 파싱 오류: {str(e)}")
            print("원본 데이터를 사용합니다.")
            return original_knowledge
        except Exception as e:
            print(f"\n✗ 데이터 로드 중 오류: {str(e)}")
            print("원본 데이터를 사용합니다.")
            return original_knowledge


def run_stage_1_5(knowledge: CampaignKnowledge, project_root: str = None) -> CampaignKnowledge:
    """
    Stage 1.5를 실행합니다.

    Args:
        knowledge: Stage 1 결과
        project_root: 프로젝트 루트

    Returns:
        검증/교정된 Campaign Knowledge
    """
    verifier = Stage1p5Verification(project_root)
    return verifier.verify_and_correct(knowledge)


if __name__ == '__main__':
    print("Stage 1.5는 main.py를 통해 호출되어야 합니다.")
