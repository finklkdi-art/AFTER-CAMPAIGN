# -*- coding: utf-8 -*-
"""
오류 메시지 정제 — 사용자용 문장과 개발자용 원문을 분리한다.

두 가지 문제를 한곳에서 막는다.

1. **서버 내부 경로 노출.**
   python-pptx 는 실패하면 `Package not found at 'C:\\Users\\…\\Temp\\ax…'`
   처럼 절대 경로를 그대로 문자열에 담는다. 이 문구가 화면까지 흘러가면
   AE 에게는 아무 정보도 못 주면서 호스팅 서버의 디렉터리 구조만 드러낸다.

2. **라이브러리 원문 그대로 노출.**
   'Excel file format cannot be determined, you must specify an engine
   manually' 같은 문장은 AE 가 읽고 할 수 있는 일이 없다. 원인을 사람 말로
   바꾸고, 기술 원문은 `detail` 로 따로 넘겨 로그·Checklist 에서만 쓴다.

이 모듈은 Streamlit 을 import 하지 않는다 — 백엔드(utils/·data_scanning)와
화면(dashboard/) 양쪽에서 같이 쓰기 위해서다.
"""

import re
from typing import Tuple

# 절대 경로만 골라 파일명으로 줄인다.
#   ① 낱말 경계에서 시작   ② 드라이브 문자 또는 선행 구분자   ③ 확장자로 끝남
# 이 셋을 모두 요구하지 않으면 'A/B 테스트', '노출/클릭' 같은 평범한 표현까지
# 경로로 오인해 문장을 잘라먹는다.
_SEG = r"[^\\/'\"\n\s](?:[^\\/'\"\n]*[^\\/'\"\n\s])?"
_PATH_RE = re.compile(
    r"(?:^|(?<=[\s'\"(\[]))"
    r"(?:[A-Za-z]:)?[\\/]"
    rf"(?:{_SEG}[\\/])*"
    rf"({_SEG}\.[A-Za-z0-9]{{1,6}})"
)

# 라이브러리 원문 → 사람 말. 앞에서부터 먼저 맞는 것을 쓴다.
_PARSE_HINTS: Tuple[Tuple[Tuple[str, ...], str], ...] = (
    (('문서보안', 'DRM', 'NASCA'),
     '사내 문서보안(DRM)이 걸려 있어 열 수 없어요.'),
    (('not a zip file', 'Truncated file header', 'Package not found',
      'BadZipFile', 'End-of-central-directory'),
     '파일이 손상됐거나 전송 중 잘린 것 같아요.'),
    (('Excel file format cannot be determined', 'Unsupported format',
      "No such keys(s)", 'openpyxl does not support'),
     '엑셀 파일로 열리지 않아요. 형식이 다르거나 내용이 깨졌을 수 있어요.'),
    (('No /Root object', 'Is this really a PDF', 'PdfReadError',
      'EOF marker not found'),
     'PDF 로 열리지 않아요. 파일이 손상됐을 수 있어요.'),
    (('Permission denied', 'being used by another process', 'Errno 13'),
     '파일이 다른 프로그램에서 열려 있어요. 닫고 다시 시도해 주세요.'),
    (('password', 'encrypted', 'Workbook is encrypted'),
     '암호가 걸려 있어 열 수 없어요.'),
    (('not installed', 'No module named'),
     '이 형식을 읽는 데 필요한 구성 요소가 서버에 없어요.'),
    (('MemoryError', 'Unable to allocate'),
     '파일이 너무 커서 처리하지 못했어요.'),
)

_GENERIC = '파일을 읽지 못했어요.'


# 파일명에 쓸 수 없는 문자 (Windows 기준이 가장 좁아 여기에 맞춘다)
_FS_UNSAFE_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
# Windows 예약 장치명 — 확장자를 붙여도 만들 수 없다
_FS_RESERVED = frozenset({
    'con', 'prn', 'aux', 'nul',
    *(f'com{i}' for i in range(1, 10)),
    *(f'lpt{i}' for i in range(1, 10)),
})


def safe_filename_part(text, *, fallback: str = '미지정',
                       max_len: int = 60) -> str:
    """
    파일명 한 조각을 저장 가능한 형태로 다듬는다.

    출력물 이름은 `YYMMDD_품목_자료명_v0_Cheil` 규칙을 따르는데(claude.md 1.4),
    이 중 **품목은 AE 가 직접 타이핑하는 값**이다. 'AV/VD' 처럼 슬래시가 들어간
    품목명은 실무에서 흔한데, 그대로 경로에 넣으면 존재하지 않는 하위 폴더로
    해석돼 저장이 실패한다. 리포트를 다 만들어 놓고 마지막 저장에서 터지는
    것이라 사용자 입장에선 작업을 통째로 잃는 것과 같다.

    금지문자는 지우지 않고 비슷한 전각 문자로 바꾼다 — 'AV/VD' 가 'AVVD' 가
    되면 무슨 품목인지 알아볼 수 없기 때문이다.
    """
    s = str(text if text is not None else '').strip()
    # 슬래시류는 의미가 남도록 중점으로, 나머지 금지문자는 제거
    s = s.replace('/', '·').replace('\\', '·')
    s = _FS_UNSAFE_RE.sub('', s)
    s = re.sub(r'\s+', ' ', s).strip()
    # 끝의 점·공백은 Windows 가 조용히 잘라내 이름이 어긋난다
    s = s.rstrip('. ')
    if s.lower() in _FS_RESERVED:
        s = f'{s}_'
    if len(s) > max_len:
        s = s[:max_len].rstrip('. ')
    return s or fallback


def redact_paths(text) -> str:
    """메시지에 섞인 절대 경로를 파일명만 남기고 지운다."""
    s = str(text if text is not None else '')
    s = _PATH_RE.sub(r'\1', s)
    return re.sub(r'[ \t]{2,}', ' ', s).strip()


def humanize_parse_error(raw, *, file_name: str = '') -> Tuple[str, str]:
    """
    파서 예외 원문을 (사용자 문장, 개발자 원문) 으로 나눈다.

    Args:
        raw: 라이브러리가 준 예외 문자열
        file_name: 파일명 (문장에 붙이지는 않는다 — 호출부가 이미 알고 있다)

    Returns:
        (message, detail)
        message — AE 가 읽고 다음 행동을 정할 수 있는 한 문장
        detail  — 경로만 지운 기술 원문. 로그·Checklist 상세용
    """
    detail = redact_paths(raw)
    if not detail:
        return _GENERIC, ''
    for needles, friendly in _PARSE_HINTS:
        if any(n.lower() in detail.lower() for n in needles):
            return friendly, detail
    return _GENERIC, detail
