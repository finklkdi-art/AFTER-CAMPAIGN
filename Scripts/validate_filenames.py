#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
파일명 규칙 검증 스크립트 (File Naming Convention Validator)

Project Rule Book에서 정의한 파일명 규칙을 따르는지 검증합니다.
- 형식: YYMMDD_품목_자료명_v[VERSION]_Cheil.확장자
- 예: 260820_가전_결과리포트_v0_Cheil.pptx

사용법: python validate_filenames.py [폴더경로]
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Tuple

# ============================================================================
# 설정값 (Configuration)
# ============================================================================

# 파일명 규칙 (정규표현식)
FILENAME_PATTERN = r'^(\d{6})_([가-힣A-Za-z0-9]+)_([가-힣A-Za-z0-9_]+)_v(\d+)_Cheil\.[a-zA-Z0-9]+$'

# 허용 확장자
ALLOWED_EXTENSIONS = {'.xlsx', '.pptx', '.pdf', '.md', '.csv', '.json'}

# 품목 분류 기준 (Rule Book 정의)
VALID_CATEGORIES = {
    '가전': '가전제품 (냉장고, 세탁기, 에어컨 등)',
    '에어케어': '에어케어 제품',
    '구독': 'AI 구독 서비스',
    '식품': '식품 및 음료',
    '금융': '금융 상품',
    '통신': '통신 서비스',
}

# 자료명 유형 (Rule Book 정의)
VALID_DOC_TYPES = {
    '결과리포트': '최종 보고서 (PPT)',
    '성과분석': '성과 데이터 분석 (XLSX)',
    '인사이트': '전략적 인사이트 (MD)',
    '제안서': '캠페인 제안서 (PPTX)',
    '데이터분석': '상세 데이터 분석 (XLSX)',
    '전략제안': '개선안 및 전략 제안 (PPTX)',
}

# ============================================================================
# 검증 함수
# ============================================================================

def parse_filename(filename: str) -> Dict:
    """
    파일명을 파싱하여 구성 요소 추출

    Returns:
        파싱된 정보 딕셔너리 또는 None
    """
    match = re.match(FILENAME_PATTERN, filename)
    if not match:
        return None

    date_str, category, doc_name, version, ext = (
        match.group(1),
        match.group(2),
        match.group(3),
        match.group(4),
        os.path.splitext(filename)[1].lower()
    )

    return {
        'filename': filename,
        'date': date_str,
        'category': category,
        'doc_name': doc_name,
        'version': version,
        'extension': ext,
    }

def validate_date(date_str: str) -> Tuple[bool, str]:
    """
    날짜 형식 검증 (YYMMDD)
    """
    if len(date_str) != 6 or not date_str.isdigit():
        return False, "날짜 형식 오류: YYMMDD 형식이어야 함"

    yy, mm, dd = int(date_str[:2]), int(date_str[2:4]), int(date_str[4:6])

    if mm < 1 or mm > 12:
        return False, f"월(MM) 범위 오류: {mm} (1~12 범위)"

    if dd < 1 or dd > 31:
        return False, f"일(DD) 범위 오류: {dd} (1~31 범위)"

    return True, "✅ 유효한 날짜"

def validate_category(category: str) -> Tuple[bool, str]:
    """
    품목(카테고리) 검증
    """
    if category in VALID_CATEGORIES:
        return True, f"✅ 유효한 품목: {VALID_CATEGORIES[category]}"

    suggestions = [k for k in VALID_CATEGORIES.keys()
                   if category.lower() in k.lower()]

    if suggestions:
        return False, f"❌ 미등록 품목. 제안: {', '.join(suggestions)}"

    return False, f"❌ 미등록 품목. 허용값: {', '.join(VALID_CATEGORIES.keys())}"

def validate_doc_type(doc_name: str) -> Tuple[bool, str]:
    """
    자료명(문서 유형) 검증
    """
    if doc_name in VALID_DOC_TYPES:
        return True, f"✅ 유효한 자료명: {VALID_DOC_TYPES[doc_name]}"

    # 부분 일치 체크
    for valid_name in VALID_DOC_TYPES.keys():
        if valid_name in doc_name or doc_name in valid_name:
            return True, f"⚠️ 유효하지만 정의되지 않은 자료명: {doc_name}"

    return False, f"❌ 미등록 자료명. 제안: {', '.join(list(VALID_DOC_TYPES.keys())[:3])}"

def validate_extension(filename: str) -> Tuple[bool, str]:
    """
    파일 확장자 검증
    """
    ext = os.path.splitext(filename)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        return False, f"❌ 허용되지 않는 확장자: {ext}. 허용: {', '.join(ALLOWED_EXTENSIONS)}"

    return True, f"✅ 유효한 확장자: {ext}"

def validate_single_file(filepath: str) -> Dict:
    """
    단일 파일 검증
    """
    filename = os.path.basename(filepath)
    result = {
        'filepath': filepath,
        'filename': filename,
        'valid': True,
        'errors': [],
        'warnings': [],
        'parsed': None,
    }

    # 규칙 형식 검증
    parsed = parse_filename(filename)
    if not parsed:
        result['valid'] = False
        result['errors'].append(
            f"❌ 파일명 형식 오류: '{filename}'\n"
            f"   기준: YYMMDD_품목_자료명_v[VERSION]_Cheil.확장자"
        )
        return result

    result['parsed'] = parsed

    # 각 구성 요소 검증
    is_valid, msg = validate_date(parsed['date'])
    if not is_valid:
        result['valid'] = False
        result['errors'].append(f"📅 날짜: {msg}")

    is_valid, msg = validate_category(parsed['category'])
    if not is_valid:
        result['valid'] = False
        result['errors'].append(f"📂 품목: {msg}")

    is_valid, msg = validate_doc_type(parsed['doc_name'])
    if not is_valid:
        result['valid'] = False
        result['errors'].append(f"📋 자료명: {msg}")

    is_valid, msg = validate_extension(filename)
    if not is_valid:
        result['valid'] = False
        result['errors'].append(f"📄 확장자: {msg}")

    return result

def validate_directory(directory: str) -> List[Dict]:
    """
    디렉토리 내 모든 파일 검증
    """
    results = []
    output_folder = Path(directory) / "Output"

    if not output_folder.exists():
        print(f"⚠️ Output 폴더를 찾을 수 없습니다: {output_folder}")
        return results

    # Output 폴더 내의 모든 파일 검증
    for root, dirs, files in os.walk(output_folder):
        for file in files:
            if os.path.isfile(os.path.join(root, file)):
                filepath = os.path.join(root, file)
                result = validate_single_file(filepath)
                results.append(result)

    return results

# ============================================================================
# 리포트 출력
# ============================================================================

def print_report(results: List[Dict]):
    """
    검증 결과 보고서 출력
    """
    print("\n" + "="*80)
    print("📋 파일명 규칙 검증 보고서")
    print("="*80 + "\n")

    if not results:
        print("⚠️ 검증할 파일이 없습니다.")
        return

    valid_count = sum(1 for r in results if r['valid'])
    total_count = len(results)

    print(f"📊 검증 결과: {valid_count}/{total_count} 통과\n")

    # 통과한 파일
    if valid_count > 0:
        print("✅ 통과한 파일:")
        for result in results:
            if result['valid']:
                print(f"   • {result['filename']}")
        print()

    # 실패한 파일
    failed_results = [r for r in results if not r['valid']]
    if failed_results:
        print("❌ 실패한 파일:")
        for result in failed_results:
            print(f"\n   파일: {result['filename']}")
            for error in result['errors']:
                print(f"   {error}")
            for warning in result['warnings']:
                print(f"   {warning}")

    # 통계
    print("\n" + "-"*80)
    print(f"📈 통계: {valid_count} 통과, {total_count - valid_count} 실패")
    print("="*80 + "\n")

def print_template_example():
    """
    파일명 템플릿 예시 출력
    """
    print("\n" + "="*80)
    print("📝 파일명 템플릿 예시")
    print("="*80 + "\n")

    examples = [
        ("260820", "가전", "결과리포트", "0", "pptx", "CE 통합 신혼 캠페인 결과 리포트"),
        ("260820", "가전", "성과분석", "0", "xlsx", "에어케어 캠페인 성과 데이터"),
        ("260814", "구독", "제안서", "1", "pptx", "AI 구독클럽 미디어 믹스 제안서"),
    ]

    for date, cat, doc, ver, ext, desc in examples:
        filename = f"{date}_{cat}_{doc}_v{ver}_Cheil.{ext}"
        print(f"📄 {filename}")
        print(f"   └─ {desc}")
        print()

    print("="*80 + "\n")

# ============================================================================
# 메인 실행
# ============================================================================

def main():
    """
    메인 함수
    """
    if len(sys.argv) > 1:
        target_path = sys.argv[1]
    else:
        # 기본값: 현재 스크립트의 상위 디렉토리의 상위 디렉토리 (AX8BB)
        target_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    print(f"\n🔍 검증 대상: {target_path}")

    # 템플릿 예시 출력
    print_template_example()

    # 디렉토리 검증
    results = validate_directory(target_path)

    # 결과 보고서 출력
    print_report(results)

    return 0 if all(r['valid'] for r in results) else 1

if __name__ == '__main__':
    sys.exit(main())
