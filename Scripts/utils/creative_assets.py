# -*- coding: utf-8 -*-
"""
소재 이미지 자산 탐색 및 소재명 매칭

캠페인 폴더에 소재 이미지를 넣어두면 소재 카드 슬라이드에 자동으로 들어간다.
파일명과 소재명 표기가 정확히 같을 수 없으므로(실측: 소재명 '①세탁물편(가로형47초)',
파일명 '워시타워_세탁물편_가로.jpg') 정규화한 뒤 부분 일치로 맞춘다.

claude.md 2장: 이미지·영상은 파싱 대상이 아니며 메타데이터만 수집한다.
여기서도 파일 내용을 해석하지 않고 경로만 넘긴다 (렌더러가 그림으로 삽입).
영상 파일은 썸네일을 뽑을 수 없어 목록만 알린다.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 슬라이드에 삽입 가능한 이미지
IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')
# 삽입은 못 하지만 자산 보유 여부를 알려야 하는 형식
VIDEO_EXTS = ('.mp4', '.mov', '.avi', '.mkv', '.wmv')

# 소재명·파일명 정규화에서 떼어낼 표기
#   ①②③ 순번 기호, 괄호 주석, 초수, 방향, 구분자
_ORDINALS = '①②③④⑤⑥⑦⑧⑨⑩'
_DROP_WORDS = ('가로형', '세로형', '가로', '세로', '일부공개', '초', 'sec',
               '영상', '이미지', '배너', '편집본', 'final', 'f')
_NON_WORD_RE = re.compile(r'[^0-9a-z가-힣]+')


def _normalize(text: str) -> str:
    """비교용 문자열 — 기호·공백·군더더기 표기 제거"""
    s = (text or '').lower()
    for ch in _ORDINALS:
        s = s.replace(ch, ' ')
    s = _NON_WORD_RE.sub(' ', s)
    for w in _DROP_WORDS:
        s = s.replace(w, ' ')
    return re.sub(r'\s+', '', s)


def _tokens(text: str) -> List[str]:
    """부분 일치 판정에 쓸 토큰 (2글자 이상)"""
    s = (text or '').lower()
    for ch in _ORDINALS:
        s = s.replace(ch, ' ')
    parts = _NON_WORD_RE.sub(' ', s).split()
    return [p for p in parts if len(p) >= 2 and p not in _DROP_WORDS]


def scan_assets(folder: str) -> Tuple[List[Path], List[Path]]:
    """
    캠페인 폴더에서 이미지·영상 자산을 찾는다 (하위 폴더 포함).

    Returns:
        (이미지 파일 목록, 영상 파일 목록)
    """
    base = Path(folder)
    if not base.is_dir():
        return [], []
    images, videos = [], []
    for p in sorted(base.rglob('*')):
        if not p.is_file() or p.name.startswith('~$'):
            continue
        ext = p.suffix.lower()
        if ext in IMAGE_EXTS:
            images.append(p)
        elif ext in VIDEO_EXTS:
            videos.append(p)
    return images, videos


def _score(creative: str, asset: Path) -> int:
    """
    소재명과 파일명의 일치 점수 (0 = 불일치).

    점수가 높을수록 확실한 매칭 — 정규화 문자열 포함 > 토큰 겹침.
    """
    name = asset.stem
    c_norm, a_norm = _normalize(creative), _normalize(name)
    if not c_norm or not a_norm:
        return 0

    if c_norm == a_norm:
        return 1000
    if c_norm in a_norm or a_norm in c_norm:
        return 500 + min(len(c_norm), len(a_norm))

    c_tokens, a_tokens = set(_tokens(creative)), set(_tokens(name))
    shared = c_tokens & a_tokens
    if not shared:
        return 0
    return 100 + sum(len(t) for t in shared)


def match_assets(creatives: List[str], images: List[Path]
                 ) -> Dict[str, Optional[Path]]:
    """
    소재명에 이미지를 1:1로 배정한다.

    점수가 높은 조합부터 확정하고, 이미 쓴 파일은 다시 쓰지 않는다.
    맞는 파일이 없으면 None (렌더러가 자리표시자로 표시).

    Args:
        creatives: 소재명 목록
        images: 후보 이미지 경로 목록

    Returns:
        {소재명: 이미지 경로 또는 None}
    """
    pairs: List[Tuple[int, str, Path]] = []
    for c in creatives:
        for img in images:
            s = _score(c, img)
            if s > 0:
                pairs.append((s, c, img))
    pairs.sort(key=lambda t: t[0], reverse=True)

    result: Dict[str, Optional[Path]] = {c: None for c in creatives}
    used: set = set()
    for _, c, img in pairs:
        if result[c] is not None or img in used:
            continue
        result[c] = img
        used.add(img)
    return result
