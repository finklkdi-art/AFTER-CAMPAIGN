# -*- coding: utf-8 -*-
"""
Main Entry Point - Campaign Report Automation Solution
Stage 1: Data Scanning & Campaign Knowledge Building
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# UTF-8 콘솔 인코딩 설정
if sys.platform.startswith('win'):
    os.system('chcp 65001')
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 패키지 경로 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.campaign_knowledge import CampaignKnowledge
from utils.checklist_manager import ChecklistManager
from data_scanning import run_step1
from stage_1_5_verification import run_stage_1_5


class CampaignReportAutomation:
    """광고 캠페인 결과 리포트 자동화 솔루션 - 메인 클래스"""

    def __init__(self, project_root: str = None):
        """
        Args:
            project_root: 프로젝트 루트 경로 (기본값: Scripts 폴더의 상위)
        """
        if project_root is None:
            project_root = Path(__file__).parent.parent
        self.project_root = Path(project_root)
        self.input_dir = self.project_root / 'Input'
        self.output_dir = self.project_root / 'Output'

    def find_star_campaign_folder(self, samples_dir: str = None) -> str:
        """
        '★' 기호가 붙은 캠페인 폴더를 찾습니다.

        Args:
            samples_dir: 샘플 폴더 경로 (기본값: Input/Samples)

        Returns:
            캠페인 폴더 경로 또는 None
        """
        if samples_dir is None:
            samples_dir = str(self.input_dir / 'Samples')

        if not os.path.exists(samples_dir):
            print(f"샘플 폴더를 찾을 수 없음: {samples_dir}")
            return None

        print(f"\n샘플 폴더 검색 중: {samples_dir}")

        for item in os.listdir(samples_dir):
            if '★' in item:
                full_path = os.path.join(samples_dir, item)
                if os.path.isdir(full_path):
                    print(f"  ★ 타겟 캠페인 폴더 발견: {item}")
                    return full_path

        print("  ✗ '★' 기호가 붙은 폴더를 찾을 수 없습니다.")
        return None

    def run_stage1(self, campaign_folder: str = None) -> CampaignKnowledge:
        """
        Stage 1을 실행합니다: 데이터 스캔 및 Campaign Knowledge 구성

        Args:
            campaign_folder: 캠페인 폴더 경로 (None이면 자동 검색)

        Returns:
            CampaignKnowledge 객체
        """
        # 캠페인 폴더 결정
        if campaign_folder is None:
            campaign_folder = self.find_star_campaign_folder()

        if campaign_folder is None:
            print("\n오류: 처리할 캠페인 폴더를 찾을 수 없습니다.")
            sys.exit(1)

        if not os.path.exists(campaign_folder):
            print(f"\n오류: 폴더가 존재하지 않음: {campaign_folder}")
            sys.exit(1)

        print(f"\n캠페인 폴더: {campaign_folder}")

        # Step 1 실행
        try:
            knowledge = run_step1(campaign_folder)
            return knowledge
        except Exception as e:
            print(f"\n[오류] Stage 1 실행 중 오류: {str(e)}")
            sys.exit(1)

    def run_stage1_5(self, knowledge: CampaignKnowledge) -> CampaignKnowledge:
        """
        Stage 1.5를 실행합니다: 기획자 검증 및 데이터 교정

        Args:
            knowledge: Stage 1 결과

        Returns:
            검증/교정된 CampaignKnowledge 객체
        """
        try:
            corrected_knowledge = run_stage_1_5(knowledge, str(self.project_root))
            return corrected_knowledge
        except Exception as e:
            print(f"\n[오류] Stage 1.5 실행 중 오류: {str(e)}")
            print("원본 데이터를 계속 사용합니다.")
            return knowledge

    def print_knowledge_summary(self, knowledge: CampaignKnowledge) -> None:
        """Campaign Knowledge 요약을 출력합니다"""
        print("\n" + "=" * 70)
        print("Campaign Knowledge 요약")
        print("=" * 70)

        summary = knowledge.get_summary()
        print(f"  Campaign ID: {summary['campaign_id']}")
        print(f"  Campaign Name: {summary['campaign_name']}")
        print(f"  Category: {summary['category']}")
        print(f"  Proposal Status: {summary['proposal_status']}")
        print(f"  PostBuy Status: {summary['postbuy_status']}")
        print(f"  Checklist Items: {summary['checklist_count']}")
        print(f"    - Errors: {summary['errors']}")
        print(f"    - Warnings: {summary['warnings']}")
        print(f"    - Infos: {summary['infos']}")

        # 문서 역할 추론 결과
        print(f"\n[문서 역할 추론 결과]")
        print(f"  Proposal:")
        print(f"    - 파일명: {knowledge.proposal.get('file_name', 'N/A')}")
        print(f"    - 형식: {knowledge.proposal.get('file_type', 'N/A')}")
        print(f"    - 추론 역할: {knowledge.proposal.get('detected_role', 'unknown')} "
              f"(신뢰도: {knowledge.proposal.get('confidence', 0.0):.2%})")
        print(f"    - KPI 후보: {len(knowledge.proposal.get('kpi_plan', []))}개")

        print(f"\n  PostBuy:")
        print(f"    - 파일명: {knowledge.postbuy.get('file_name', 'N/A')}")
        print(f"    - 형식: {knowledge.postbuy.get('file_type', 'N/A')}")
        print(f"    - 추론 역할: {knowledge.postbuy.get('detected_role', 'unknown')} "
              f"(신뢰도: {knowledge.postbuy.get('confidence', 0.0):.2%})")
        print(f"    - KPI 실적: {len(knowledge.postbuy.get('kpi_actual', []))}개")

        # 보조 문서들
        if knowledge.supporting_documents:
            print(f"\n[보조 문서들] - {len(knowledge.supporting_documents)}개")
            for i, doc in enumerate(knowledge.supporting_documents, 1):
                role_emoji = {
                    'proposal': '[기획]',
                    'postbuy': '[실적]',
                    'supporting': '[보조]'
                }.get(doc.get('detected_role', 'unknown'), '[-]')
                print(f"  {i}. {doc['file_name']}")
                print(f"     형식: {doc['file_type']}, 역할: {role_emoji} (신뢰도: {doc.get('confidence', 0.0):.2%})")

        print("=" * 70)


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description='광고 캠페인 결과 리포트 자동화 솔루션 - Stage 1'
    )
    parser.add_argument(
        '--campaign',
        type=str,
        default=None,
        help='캠페인 폴더 경로 (기본값: 자동 검색)'
    )
    parser.add_argument(
        '--project-root',
        type=str,
        default=None,
        help='프로젝트 루트 경로'
    )

    args = parser.parse_args()

    # 메인 클래스 인스턴스 생성
    automation = CampaignReportAutomation(args.project_root)

    # Stage 1 실행
    print("\n" + "=" * 70)
    print("광고 캠페인 결과 리포트 자동화 솔루션")
    print("Stage 1: 데이터 스캔 및 Campaign Knowledge 구성")
    print("=" * 70)

    knowledge = automation.run_stage1(args.campaign)

    # Stage 1 결과 출력
    print("\n" + "=" * 70)
    print("Stage 1 결과")
    print("=" * 70)
    automation.print_knowledge_summary(knowledge)
    ChecklistManager.print_checklist(knowledge)

    print("\n✓ Stage 1 완료!")

    # Stage 1.5 실행: 기획자 검증 및 교정
    print("\n" + "=" * 70)
    print("Stage 1.5: 기획자 검증 및 데이터 교정")
    print("=" * 70)

    knowledge = automation.run_stage1_5(knowledge)

    # Stage 1.5 결과 출력
    print("\n" + "=" * 70)
    print("Stage 1.5 검증 완료")
    print("=" * 70)
    automation.print_knowledge_summary(knowledge)
    ChecklistManager.print_checklist(knowledge)

    print("\n✓ Stage 1.5 완료!")
    print("\n전체 파이프라인이 준비되었습니다.")

    return knowledge


if __name__ == '__main__':
    knowledge = main()
