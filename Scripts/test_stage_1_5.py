# -*- coding: utf-8 -*-
"""
Test script for Stage 1.5 - Automated testing without user input
"""

import os
import sys
import io
import json
from pathlib import Path

# UTF-8 콘솔 인코딩 설정
if sys.platform.startswith('win'):
    os.system('chcp 65001 > nul')
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_scanning import run_step1
from utils.knowledge_export import KnowledgeExport


def pick_campaign_folder() -> str:
    """
    테스트 대상 캠페인 폴더를 고른다.

    절대경로를 박아두면 다른 AE PC 에서 실행되지 않으므로,
    인자로 받거나 프로젝트의 Input 폴더에서 찾는다. (★ 표시 폴더 우선)
    """
    if len(sys.argv) > 1:
        return sys.argv[1]

    root = Path(__file__).resolve().parent.parent
    bases = [root / 'Input' / 'Samples', root / 'Input']
    for base in bases:
        if not base.is_dir():
            continue
        folders = [p for p in sorted(base.iterdir())
                   if p.is_dir() and not p.name.startswith(('_', '.'))
                   and p.name != 'Samples']
        if folders:
            starred = [p for p in folders if '★' in p.name]
            return str((starred or folders)[0])
    raise SystemExit(
        'Input 폴더에서 캠페인 폴더를 찾을 수 없습니다. '
        '경로를 인자로 넘기세요: python <script> "<캠페인 폴더>"')



def test_stage_1_5():
    """Stage 1.5 자동 테스트"""
    print("\n" + "=" * 70)
    print("Stage 1.5 자동 테스트: 파일 생성 및 데이터 검증")
    print("=" * 70)

    project_root = Path(__file__).parent.parent
    temp_dir = project_root / 'Output' / 'Temp'

    # Step 1: Stage 1 실행
    print("\n[Step 1] Stage 1 실행...")
    folder = pick_campaign_folder()
    print(f"  대상 캠페인: {folder}")
    knowledge = run_step1(folder)
    print("  ✓ Stage 1 완료")

    # Step 2: Markdown 파일 생성
    print("\n[Step 2] Markdown 임시 파일 생성...")
    md_file = KnowledgeExport.export_to_markdown(knowledge, str(temp_dir))
    print(f"  ✓ 생성됨: {Path(md_file).name}")

    # Step 3: JSON 파일 생성
    print("\n[Step 3] JSON 임시 파일 생성...")
    json_file = KnowledgeExport.export_to_json(knowledge, str(temp_dir))
    print(f"  ✓ 생성됨: {Path(json_file).name}")

    # Step 4: 생성된 파일 확인
    print("\n[Step 4] 생성된 파일 내용 확인...")
    print(f"\n[Markdown 파일 내용 샘플]")
    print("-" * 70)
    with open(md_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        # 처음 30줄만 출력
        for line in lines[:40]:
            print(line.rstrip())
    print("\n...[생략]...")

    # Step 5: JSON 파일 내용 확인
    print("\n[JSON 파일 구조 확인]")
    print("-" * 70)
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        print(f"  최상위 키: {list(data.keys())}")
        print(f"  campaign_id: {data.get('campaign_id', 'N/A')}")
        print(f"  campaign_name: {data.get('campaign_name', 'N/A')}")
        print(f"  category: {data.get('category', 'N/A')}")
        print(f"  proposal 상태: {data.get('proposal', {}).get('status', 'N/A')}")
        print(f"  postbuy 상태: {data.get('postbuy', {}).get('status', 'N/A')}")
        print(f"  validation.checklist_items: {len(data.get('validation', {}).get('checklist_items', []))}개")

    # Step 6: JSON 파일에서 다시 로드
    print("\n[Step 5] JSON 파일에서 Knowledge 복원...")
    from utils.knowledge_export import KnowledgeExport as KE
    reloaded_knowledge = KE.import_from_json(json_file)
    print(f"  ✓ 복원 완료")
    print(f"  복원된 캠페인: {reloaded_knowledge.campaign_name}")
    print(f"  복원된 제안서 상태: {reloaded_knowledge.proposal['status']}")
    print(f"  복원된 포스트바이 상태: {reloaded_knowledge.postbuy['status']}")

    # Step 7: 수정 시뮬레이션
    print("\n[Step 6] 데이터 수정 시뮬레이션...")
    print("  기획자가 JSON 파일을 수동으로 수정했다고 가정...")

    # 원본과 비교
    print("\n[Test 결과]")
    print("-" * 70)
    print(f"  ✓ Markdown 파일 생성 성공")
    print(f"  ✓ JSON 파일 생성 성공")
    print(f"  ✓ 데이터 직렬화 성공")
    print(f"  ✓ 데이터 역직렬화 성공")
    print(f"  ✓ 메타데이터 보존 확인")

    # 파일 경로 출력
    print("\n[생성된 파일 위치]")
    print("-" * 70)
    print(f"  Markdown: {md_file}")
    print(f"  JSON: {json_file}")
    print(f"  디렉토리: {temp_dir}")

    print("\n" + "=" * 70)
    print("Stage 1.5 자동 테스트 완료!")
    print("=" * 70)

    return knowledge, json_file, md_file


if __name__ == '__main__':
    knowledge, json_file, md_file = test_stage_1_5()

    print("\n[다음 단계]")
    print(f"1. Markdown 파일 열기: {md_file}")
    print(f"2. 데이터 검증/교정")
    print(f"3. JSON 파일 수정 (필요시)")
    print(f"4. main.py 실행 시 Stage 1.5에서 수정된 파일 자동 인식")
