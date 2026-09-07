# -*- coding: utf-8 -*-
"""
Step 1: Data Scanning and Campaign Knowledge Building
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# 패키지 경로 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.campaign_knowledge import CampaignKnowledge
from models.checklist import ChecklistItem
from utils.file_parser import FileParser
from utils.knowledge_builder import KnowledgeBuilder
from utils.validator import DataValidator
from utils.checklist_manager import ChecklistManager


class DataScanning:
    """Step 1: 데이터 스캔 및 Campaign Knowledge 구성"""

    @staticmethod
    def scan_campaign_folder(folder_path: str,
                             on_progress=None) -> CampaignKnowledge:
        """
        캠페인 폴더를 스캔하여 Campaign Knowledge를 구성합니다.

        Args:
            folder_path: 캠페인 폴더 경로
            on_progress: (비율 0.0~1.0, 메시지) 콜백. 로딩바 표시용이며
                         None 이면 보고하지 않는다 (CLI 동작 불변).

        Returns:
            CampaignKnowledge 객체
        """
        from ingest.progress import Progress
        prog = Progress(on_progress)
        start_time = datetime.now()
        print(f"\n[Step 1] Data Scanning 시작...")
        print(f"폴더: {folder_path}")

        # 기본 정보 추출
        folder_name = os.path.basename(folder_path)
        campaign_id = f"{datetime.now().strftime('%y%m%d')}_{folder_name}"

        # Campaign Knowledge 생성
        knowledge = CampaignKnowledge(
            campaign_id=campaign_id,
            campaign_name=folder_name.replace('★', '').strip(),
            folder_path=folder_path
        )

        print(f"Campaign ID: {knowledge.campaign_id}")
        print(f"Campaign Name: {knowledge.campaign_name}")

        # 1단계: 파일 스캔
        print("\n[1/5] 폴더 내 모든 파일 스캔 중...")
        all_files = DataScanning._scan_files(folder_path)
        print(f"  발견된 파일: {len(all_files)}개")
        # 파싱 N건 + 후처리 3단계(Knowledge 구성/검증/Checklist)
        prog.set_total(len(all_files) + 3)
        prog.report(f'문서 {len(all_files)}개 발견')

        if not all_files:
            knowledge.add_checklist_item(ChecklistItem(
                type='no_files',
                severity='error',
                message='폴더가 비어있음',
                detail=f'{folder_path}에 파일이 없습니다',
                source='DataScanning:scan_campaign_folder'
            ))
            return knowledge

        # 2단계: 파일 파싱
        print("\n[2/5] 모든 파일 파싱 중...")
        parsed_files = {}
        for file_path in all_files:
            file_name = os.path.basename(file_path)
            try:
                print(f"  → {file_name} 파싱 중...", end=" ")
                parsed_data = FileParser.parse_file(file_path)
                parsed_files[file_name] = parsed_data
                status = "OK" if parsed_data['status'] == 'success' else "NG"
                print(status)
                prog.step(f'{file_name} 파싱')
            except Exception as e:
                print(f"✗ 오류: {str(e)}")
                parsed_files[file_name] = {
                    'status': 'error',
                    'error_msg': str(e),
                    'file_path': file_path,
                    'file_name': file_name,
                    'file_type': Path(file_path).suffix.lower()[1:]
                }
                prog.step(f'{file_name} 파싱 실패')

        # 3단계: Knowledge 구성
        print("\n[3/5] Campaign Knowledge 구성 중...")
        prog.report('Campaign Knowledge 구성 중')
        try:
            knowledge = KnowledgeBuilder.build_knowledge(
                campaign_id=knowledge.campaign_id,
                campaign_name=knowledge.campaign_name,
                folder_path=folder_path,
                parsed_files=parsed_files
            )
        except Exception as e:
            knowledge.add_checklist_item(ChecklistItem(
                type='knowledge_build_error',
                severity='error',
                message='Knowledge 구성 실패',
                detail=str(e),
                source='DataScanning:scan_campaign_folder'
            ))
            print(f"  ✗ 오류: {str(e)}")

        # 4단계: 데이터 검증
        print("\n[4/5] 데이터 검증 중...")
        prog.step('Knowledge 구성 완료')
        try:
            DataValidator.validate(knowledge)
            print("  ✓ 검증 완료")
        except Exception as e:
            knowledge.add_checklist_item(ChecklistItem(
                type='validation_error',
                severity='warning',
                message='검증 과정 오류',
                detail=str(e),
                source='DataScanning:scan_campaign_folder'
            ))
            print(f"  ✗ 오류: {str(e)}")

        # Part 1 캠페인 개요(기획 의도) 추출 — 제안서가 없어도 다른 문서에서 훑는다
        try:
            from utils.parsers import overview_parser
            knowledge.overview = overview_parser.extract(knowledge.documents)
            ov = knowledge.overview
            print(f"  ✓ 캠페인 개요 추출 (신뢰도 {ov.get('confidence')}) "
                  f"— 출처 {len(ov.get('sources') or [])}건")
            if ov.get('confidence') == 'none':
                knowledge.add_checklist_item(ChecklistItem(
                    type='overview_missing',
                    severity='warning',
                    message="'캠페인 개요(목표/전략/로드맵)' 소스 누락 — 수기 작성 요망",
                    detail='제안서·미디어브리프에서 기획 의도를 찾지 못했습니다. '
                           'Part 1 슬라이드는 작성 가이드로 대체됩니다.',
                    source='Stage 1 개요 추출',
                ))
        except Exception as e:
            print(f"  ✗ 캠페인 개요 추출 실패: {e}")

        # 게재 보고 — 실제 광고 게재 화면 이미지 확보
        try:
            from pathlib import Path as _P
            from utils.parsers import placement_parser as PP
            root = _P(__file__).resolve().parents[1]
            shots = PP.extract(knowledge.documents,
                               root / 'Output' / 'Temp' / 'Placements',
                               project_root=root)
            if shots:
                knowledge.creative_info['placements'] = [s.to_dict() for s in shots]
                print(f"  ✓ 게재 화면 이미지 {len(shots)}건 확보")
            elif any(getattr(d, 'role', '') == 'placement_report'
                     for d in knowledge.documents):
                knowledge.add_checklist_item(ChecklistItem(
                    type='placement_no_image',
                    severity='warning',
                    message='게재 보고 문서에서 게재 화면 이미지를 뽑지 못했습니다',
                    detail='문서는 인식했으나 추출 가능한 이미지가 없었습니다. '
                           '크기가 너무 작거나 지원하지 않는 형식일 수 있습니다.',
                    source='Stage 1 게재보고 추출',
                ))
        except Exception as e:
            print(f"  ✗ 게재 화면 추출 실패: {e}")

        # 5단계: Checklist 정리
        print("\n[5/5] Checklist 정리 중...")
        prog.step('데이터 검증 완료')
        try:
            ChecklistManager.deduplicate_checklist(knowledge)
            summary = ChecklistManager.get_checklist_summary(knowledge)
            print(f"  ✓ 총 {summary['total']}개 항목 (오류: {summary['errors']}, 경고: {summary['warnings']}, 정보: {summary['infos']})")
        except Exception as e:
            print(f"  ✗ 오류: {str(e)}")

        # 파이프라인 로그 업데이트
        elapsed_time = (datetime.now() - start_time).total_seconds()
        knowledge.pipeline_log['step1_completed'] = True
        knowledge.pipeline_log['step1_timestamp'] = datetime.now().isoformat()
        knowledge.pipeline_log['execution_time_seconds'] = elapsed_time

        print(f"\n[Step 1] 완료! (소요 시간: {elapsed_time:.2f}초)")
        prog.done(f'파싱 완료 ({elapsed_time:.1f}초)')

        return knowledge

    @staticmethod
    def _scan_files(folder_path: str) -> list:
        """
        폴더 내의 모든 파일을 재귀적으로 스캔합니다.

        Args:
            folder_path: 스캔할 폴더 경로

        Returns:
            파일 경로 리스트
        """
        all_files = []
        try:
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    # 숨김 파일 제외
                    if not file.startswith('.'):
                        all_files.append(file_path)
        except Exception as e:
            print(f"파일 스캔 중 오류: {str(e)}")

        return all_files


def run_step1(campaign_folder_path: str,
              on_progress=None) -> CampaignKnowledge:
    """
    Step 1을 실행합니다.

    Args:
        campaign_folder_path: 캠페인 폴더 경로

    Returns:
        CampaignKnowledge 객체
    """
    return DataScanning.scan_campaign_folder(campaign_folder_path, on_progress)


if __name__ == '__main__':
    # 테스트용
    if len(sys.argv) > 1:
        folder_path = sys.argv[1]
    else:
        print("사용법: python 01_DataScanning.py <캠페인폴더경로>")
        sys.exit(1)

    knowledge = run_step1(folder_path)
    ChecklistManager.print_checklist(knowledge)
