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
    '문서보안 프로그램에 로그인되어 있는지 확인하고 다시 시도해 주세요. '
    '그래도 안 되면 파일 우클릭 → 문서보안 해제 후 올려 주세요.'
)

# 왜 '로그인 확인'이 먼저인가 — 이 상태는 파일이 아니라 **환경**에 달려 있다.
#
# NASCA 는 커널 필터 드라이버로 동작해서, 보안 에이전트가 활성인 동안에는
# 읽기 시점에 투명하게 복호화된 바이트를 돌려준다. 에이전트가 잠겨 있으면
# 같은 파일이 `<## NASCA` 헤더로 시작하는 암호문으로 읽힌다.
#
# 실측(2026-09-08): 동일한 6개 파일이 오전에는 전부 DRM 감지 → 오후에는 전부
# 정상 파싱됐다. 파일 수정 시각은 그대로였다 — 바뀐 건 파일이 아니라 에이전트
# 상태였다. 그래서 예전 안내처럼 '복호화해서 다시 넣으세요' 를 첫 번째 조치로
# 시키면, 사실은 로그인만 하면 될 사람에게 헛수고를 시키게 된다.


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
