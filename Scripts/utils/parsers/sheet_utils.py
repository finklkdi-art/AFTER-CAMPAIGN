# -*- coding: utf-8 -*-
"""
엑셀 시트 파싱 공용 유틸

실제 캠페인 6건을 조사한 결과 다음 변이가 확인되어, 위치가 아닌 내용으로 탐색한다.
  - 헤더 행 위치: 7 ~ 38 행으로 제각각
  - 컬럼 어휘   : Period / 기간 / 일정, Targeting / 타겟팅
  - 병합셀      : 상위 항목이 첫 행에만 있고 이어지는 행은 비어 있음
  - 소계 행     : Total / Sub Total / SUB TOTAL / 소계 / 합계 혼용
"""

import re
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd


def read_sheet(book: pd.ExcelFile, sheet: Any, **kwargs) -> pd.DataFrame:
    """
    열려 있는 워크북 핸들에서 시트 하나를 읽는다.

    🔴 시트마다 pd.read_excel(경로, ...) 를 호출하면 워크북 전체가 매번
    처음부터 다시 파싱된다. 시트가 N개면 N번 재파싱되어 대형 데일리리포트가
    수십 초~수 분씩 걸린다.
    (실측: 25시트 8.4MB 파일 90초 → 핸들 재사용 시 18초, 4.9배)

    반드시 pd.ExcelFile 핸들을 한 번만 열어 이 함수로 시트를 읽을 것.
    """
    return book.parse(sheet_name=sheet, **kwargs)


# 컬럼 이름 정규화 사전 — 왼쪽(정규명) : 오른쪽(관측된 표기들)
COLUMN_ALIASES: Dict[str, Sequence[str]] = {
    'media':        ('media', '매체'),
    'product':      ('product', '상품'),
    'category':     ('category', '구분', '카테고리'),
    'purpose':      ('purpose', 'objective', '목적', '캠페인 목적'),
    'creative':     ('creative', '소재'),
    'period':       ('period', '기간', '일정', '집행기간', '집행 기간'),
    'device':       ('device', '디바이스'),
    'targeting':    ('targeting', '타겟팅', '타게팅'),
    'unit_price':   ('ad unit price', '단가'),
    'budget':       ('예산',),
    'list_price':   ('공시단가',),
    'exp_imps':     ('예상 노출', '예상노출'),
    'exp_clicks':   ('예상 클릭', '예상클릭'),
    'exp_views':    ('예상 조회', '예상조회'),
    'date':         ('일자', 'date'),
    'note':         ('비고', 'note'),
    'billed':       ('청구 금액', '청구금액'),
    'spend':        ('집행 금액', '집행금액', '집행 비용', '집행비용'),
    'impressions':  ('노출수', '노출 수', '노출', 'imps.', 'imps', 'impression'),
    'views':        ('조회수', '조회 수', '조회', 'view'),
    'clicks':       ('클릭수', '클릭 수', '클릭', 'click'),
    'vtr':          ('vtr',),
    'ctr':          ('ctr',),
    'cpm':          ('cpm', 'cpm(원)', 'cpm (원)'),
    'cpv':          ('cpv', 'cpv(원)', 'cpv (원)'),
    'cpc':          ('cpc', 'cpc(원)', 'cpc (원)'),
    'reach':        ('reach',),
    'frequency':    ('freq.', 'freq', 'frequency'),
    'cpr':          ('cpr', 'cpr(도달당비용)'),
}

# 소계/합계 행 판정
_TOTAL_RE = re.compile(r'(sub\s*)?total|소계|합계|누계', re.IGNORECASE)

# 숫자 정리 (콤마, 원, %, 공백)
_NUM_CLEAN_RE = re.compile(r'[,\s원₩]')


def norm(value: Any) -> str:
    """셀 값을 비교용 문자열로 정규화 (셀 내 개행은 공백으로)"""
    if value is None:
        return ''
    s = re.sub(r'\s*\n\s*', ' ', str(value)).strip()
    return '' if s.lower() == 'nan' else s


def norm_key(value: Any) -> str:
    """컬럼명 비교용 — 소문자 + 공백 제거"""
    return re.sub(r'\s+', ' ', norm(value)).strip().lower()


def canonical_column(raw: Any) -> Optional[str]:
    """관측된 컬럼 표기를 정규명으로 변환 (모르면 None)"""
    key = norm_key(raw)
    if not key:
        return None
    for canon, aliases in COLUMN_ALIASES.items():
        if key in aliases:
            return canon
    # 괄호 주석이 붙은 경우 앞부분만으로 재시도 — "노출 (회)" 등
    head = re.split(r'[(\[]', key)[0].strip()
    if head and head != key:
        for canon, aliases in COLUMN_ALIASES.items():
            if head in aliases:
                return canon
    return None


def is_total_row(*values: Any) -> bool:
    """소계/합계 행인지"""
    for v in values:
        s = norm(v)
        if s and _TOTAL_RE.search(s):
            return True
    return False


def row_is_total(df: pd.DataFrame, row: int) -> bool:
    """
    행 전체를 훑어 소계/합계 행인지 판정한다.

    실측상 소계 라벨이 놓이는 열이 파일마다 제각각이라
    (무빙스타일 '영상 Total'=열1, 시스템에어컨 '영상 SUB TOTAL'=열4)
    특정 열만 검사하면 놓친다.
    """
    if row >= len(df):
        return False
    for v in df.iloc[row]:
        s = norm(v)
        if s and not isinstance(v, (int, float)) and _TOTAL_RE.search(s):
            return True
    return False


def scan_right(df: pd.DataFrame, row: int, col: int, span: int = 6) -> Any:
    """
    라벨 오른쪽으로 훑어 첫 유효값을 찾는다.
    병합셀 때문에 바로 옆 칸이 비어 있는 경우가 많다.
    """
    for j in range(col + 1, min(col + 1 + span, df.shape[1])):
        v = df.iat[row, j]
        if norm(v):
            return v
    return None


def to_number(value: Any) -> Optional[float]:
    """숫자로 해석. 실패하면 None (추측하지 않음)"""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return None if pd.isna(value) else float(value)
    s = norm(value)
    if not s:
        return None
    pct = s.endswith('%')
    s = _NUM_CLEAN_RE.sub('', s).rstrip('%')
    if not s or s in {'-', '#DIV/0!', 'N/A'}:
        return None
    try:
        n = float(s)
    except ValueError:
        return None
    return n / 100 if pct else n


def find_header_row(df: pd.DataFrame, required: Sequence[str],
                    limit: int = 45) -> Optional[int]:
    """
    정규명 기준으로 헤더 행을 찾는다.

    Args:
        df: header=None 으로 읽은 DataFrame
        required: 반드시 포함되어야 할 정규 컬럼명들
        limit: 탐색할 최대 행 수

    Returns:
        헤더 행 인덱스 (없으면 None)
    """
    want = set(required)
    for i in range(min(limit, len(df))):
        found = {canonical_column(v) for v in df.iloc[i]}
        found.discard(None)
        if want <= found:
            return i
    return None


def column_map(df: pd.DataFrame, header_row: int) -> Dict[str, int]:
    """헤더 행에서 {정규컬럼명: 열 인덱스}. 중복 시 첫 번째를 채택."""
    mapping: Dict[str, int] = {}
    for j, v in enumerate(df.iloc[header_row]):
        canon = canonical_column(v)
        if canon and canon not in mapping:
            mapping[canon] = j
    return mapping


def cell(df: pd.DataFrame, row: int, col: Optional[int]) -> Any:
    """안전한 셀 접근"""
    if col is None or col >= df.shape[1] or row >= len(df):
        return None
    return df.iat[row, col]


def forward_fill(values: List[str]) -> List[str]:
    """병합셀로 비어 있는 값을 위 값으로 채운다"""
    out, last = [], ''
    for v in values:
        s = norm(v)
        if s:
            last = s
        out.append(last)
    return out


def find_sheet(sheet_names: Sequence[str], patterns: Sequence[str]) -> Optional[str]:
    """
    정규식 패턴으로 시트를 찾는다. 앞선 패턴을 우선한다.

    Args:
        sheet_names: 시트 이름 목록
        patterns: 정규식 문자열 목록
    """
    for pat in patterns:
        rx = re.compile(pat, re.IGNORECASE)
        for sn in sheet_names:
            if rx.search(sn):
                return sn
    return None


def parse_date(value: Any) -> Optional[str]:
    """날짜 셀을 YYYY-MM-DD 로. 실패 시 None"""
    if value is None:
        return None
    if hasattr(value, 'strftime'):
        try:
            return value.strftime('%Y-%m-%d')
        except Exception:
            return None
    s = norm(value)
    if not s:
        return None
    try:
        ts = pd.to_datetime(s, errors='coerce')
    except Exception:
        return None
    return None if pd.isna(ts) else ts.strftime('%Y-%m-%d')


# 기간 표기 분해: "4/18~4/30", "6/30~8/27", "25/06/26 ~ 08/10",
#                 "2025-04-01~2025-04-30", "6/27, 7/26"
#
# 🔴 연도가 붙은 표기를 먼저 잡아야 한다.
#    MM-DD 규칙(_RANGE_RE)은 `\d{1,2}` 라서 "2025-04-01" 에 .search() 를 걸면
#    연도 뒷자리 "25" 를 월로 물어 "25-04" 를 만들어 낸다. 그 값은 뒤에서
#    date(2000, 25, ...) 로 넘어가 ValueError 를 내고 로드맵 슬라이드가
#    통째로 날아간다 (2026.09.09 실측 재현).
_YMD_RANGE_RE = re.compile(
    r'(?<!\d)\d{2,4}\s*[/.\-]\s*(\d{1,2})\s*[/.\-]\s*(\d{1,2})'      # 시작 Y-M-D
    r'\s*[~\-–—]\s*'
    r'(?:\d{2,4}\s*[/.\-]\s*)?(\d{1,2})\s*[/.\-]\s*(\d{1,2})(?!\d)'  # 종료 [Y-]M-D
)
_YMD_SINGLE_RE = re.compile(
    r'^(?<!\d)\d{2,4}\s*[/.\-]\s*(\d{1,2})\s*[/.\-]\s*(\d{1,2})(?!\d)'
)

_RANGE_RE = re.compile(
    r'(?<!\d)(\d{1,2})\s*[/.\-]\s*(\d{1,2})\s*[~\-–—]\s*'
    r'(?:(\d{1,2})\s*[/.\-]\s*)?(\d{1,2})(?!\d)'
)


# 단일 일자 표기: "4/25", "8/8(금)"
_SINGLE_RE = re.compile(r'^(\d{1,2})\s*[/.\-]\s*(\d{1,2})(?!\d)')


def _md(month, day) -> Optional[str]:
    """
    (월, 일) → 'MM-DD'. 달력에 없는 값이면 None — 추측하지 않는다 (Rule Book 2.1).

    검증 없이 포맷만 하던 것이 위 '25-04' 사고의 두 번째 원인이었다.
    """
    try:
        m, d = int(month), int(day)
    except (TypeError, ValueError):
        return None
    if not (1 <= m <= 12 and 1 <= d <= 31):
        return None
    return f'{m:02d}-{d:02d}'


def split_period(raw: Any) -> tuple:
    """
    기간 표기에서 (시작, 종료) 를 뽑는다. MM-DD 형식.

    - 범위 표기("4/18~4/30")  -> (시작, 종료)
    - 단일 일자("4/25", "8/8(금)") -> (일자, 일자)  하루짜리 집행
    - 쉼표 나열("6/27, 7/26") -> 첫 일자만 (비연속이라 범위로 보지 않음)
    - 해석 불가 -> (None, None). 추측하지 않는다 (Rule Book 2.1)
    """
    s = norm(raw)
    if not s:
        return None, None

    compact = s.replace(' ', '')

    # ① 연도가 붙은 범위 — "2025-04-01~2025-04-30", "25/06/26~08/10"
    m = _YMD_RANGE_RE.search(compact)
    if m:
        start, end = _md(m.group(1), m.group(2)), _md(m.group(3), m.group(4))
        return (start, end) if start and end else (None, None)

    # ② MM-DD 범위 — "4/18~4/30", "6/1~30"(월 생략)
    m = _RANGE_RE.search(compact)
    if m:
        m1, d1, m2, d2 = m.group(1), m.group(2), m.group(3), m.group(4)
        if m2 is None:
            m2 = m1
        start, end = _md(m1, d1), _md(m2, d2)
        return (start, end) if start and end else (None, None)

    # ③ 연도가 붙은 단일 일자 — "2025-04-01"
    m = _YMD_SINGLE_RE.match(compact)
    if m:
        day = _md(m.group(1), m.group(2))
        return (day, day) if day else (None, None)

    # ④ MM-DD 단일 일자 — "4/25", "8/8(금)"
    m = _SINGLE_RE.match(compact)
    if m:
        day = _md(m.group(1), m.group(2))
        return (day, day) if day else (None, None)

    return None, None
