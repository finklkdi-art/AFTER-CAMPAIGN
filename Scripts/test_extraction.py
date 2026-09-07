# -*- coding: utf-8 -*-
"""
Test script to show extracted data from Campaign Knowledge
"""

import os
import sys
import io

# UTF-8 콘솔 인코딩 설정
if sys.platform.startswith('win'):
    os.system('chcp 65001 > nul')
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path

from data_scanning import run_step1


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


# Stage 1 실행
folder = pick_campaign_folder()
print("\n테스트: Campaign Knowledge 추출 데이터 확인")
print("=" * 70)
print(f"대상 캠페인: {folder}")

knowledge = run_step1(folder)

print("\n[1] 제안서(Proposal) 정보")
print("-" * 70)
proposal = knowledge.proposal
print(f"  파일명: {proposal.get('file_name', 'N/A')}")
print(f"  형식: {proposal.get('file_type', 'N/A')}")
print(f"  상태: {proposal.get('status', 'N/A')}")
print(f"  추론 역할: {proposal.get('detected_role', 'N/A')} (신뢰도: {proposal.get('confidence', 0):.0%})")
print(f"  KPI 후보: {len(proposal.get('kpi_plan', []))}개")

if proposal.get('kpi_plan'):
    print("\n  KPI 샘플:")
    for i, kpi in enumerate(proposal.get('kpi_plan', [])[:2], 1):
        source = kpi.get('source', 'N/A')
        print(f"    {i}. [출처: {source}]")

print("\n[2] 포스트바이(PostBuy) 정보")
print("-" * 70)
postbuy = knowledge.postbuy
print(f"  파일명: {postbuy.get('file_name', 'N/A')}")
print(f"  형식: {postbuy.get('file_type', 'N/A')}")
print(f"  상태: {postbuy.get('status', 'N/A')}")
print(f"  추론 역할: {postbuy.get('detected_role', 'N/A')} (신뢰도: {postbuy.get('confidence', 0):.0%})")
print(f"  KPI 실적: {len(postbuy.get('kpi_actual', []))}개")

if postbuy.get('metadata', {}).get('report_period'):
    print(f"  보고 기간: {postbuy['metadata']['report_period']}")

print("\n[3] 보조 문서들(Supporting Documents)")
print("-" * 70)
if knowledge.supporting_documents:
    print(f"  총 {len(knowledge.supporting_documents)}개")
    for i, doc in enumerate(knowledge.supporting_documents, 1):
        print(f"  {i}. {doc['file_name']}")
        print(f"     - 형식: {doc['file_type']}")
        print(f"     - 역할: {doc.get('detected_role', 'N/A')} (신뢰도: {doc.get('confidence', 0):.0%})")
        print(f"     - 추출 표 개수: {len(doc.get('tables', []))}개")
else:
    print("  없음")

print("\n[4] 캠페인 메타데이터")
print("-" * 70)
proposal_metadata = proposal.get('metadata', {})
postbuy_metadata = postbuy.get('metadata', {})

print(f"  제안서 기간: {proposal_metadata.get('campaign_period', 'N/A')}")
print(f"  포스트바이 기간: {postbuy_metadata.get('report_period', 'N/A')}")
print(f"  카테고리: {knowledge.category}")

print("\n[5] Checklist 요약")
print("-" * 70)
checklist = knowledge.get_checklist_items()
print(f"  총 항목: {len(checklist)}개")
if len(checklist) > 0:
    for item in checklist:
        print(f"    - {item}")
else:
    print("    예외사항 없음 (정상)")

print("\n[6] 파이프라인 로그")
print("-" * 70)
log = knowledge.pipeline_log
print(f"  Step 1 완료: {log['step1_completed']}")
print(f"  소요 시간: {log['execution_time_seconds']:.2f}초")
print(f"  오류: {log['errors_count']}, 경고: {log['warnings_count']}, 정보: {log['info_count']}")

print("\n" + "=" * 70)
print("테스트 완료")
print("=" * 70)
