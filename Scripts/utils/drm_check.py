# -*- coding: utf-8 -*-
"""
사내 문서보안(DRM) 감지

NASCA 등 사내 DRM 이 적용된 파일은 인가 프로그램(Office 등)에서만 열리고,
파이썬 파서에서는 "format cannot be determined" 류의 기술적 오류만 남는다.
AE 가 원인을 바로 알 수 있도록 헤더를 검사해 한국어 안내로 바꾼다.

주의: 본 모듈은 감지·안내만 한다. DRM 해제는 사내 절차(문서보안 해제/반출 승인)를
따라야 하며 우회를 시도하지 않는다.
"""

from pathlib import Path
from typing import Optional

# 관측된 시그니처 (Examples/Input 실측): b'<## NASCA DRM FILE'
_SIGNATURES = (
    (b'<## NASCA', 'NASCA 문서보안(DRM)'),
)

DRM_GUIDE = (
    '사내 문서보안이 적용되어 파싱할 수 없습니다. '
    '파일을 문서보안 해제(복호화)한 뒤 캠페인 폴더에 다시 넣고 재파싱하세요. '
    '(해제 방법: 파일 우클릭 → 문서보안 메뉴, 또는 사내 반출/해제 절차)'
)


def detect_drm(file_path: str) -> Optional[str]:
    """
    DRM 적용 여부를 검사합니다.

    Returns:
        DRM 이면 사용자 안내 문자열, 정상 파일이면 None
    """
    try:
        with open(file_path, 'rb') as f:
            head = f.read(32)
    except OSError:
        return None
    for sig, name in _SIGNATURES:
        if head.startswith(sig):
            return f'{name} 적용 파일 — {DRM_GUIDE}'
    return None
