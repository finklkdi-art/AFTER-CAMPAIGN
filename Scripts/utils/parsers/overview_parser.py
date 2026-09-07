# -*- coding: utf-8 -*-
"""
Part 1 캠페인 개요(기획 의도) 추출 — 그물망 파싱

배경
  Part 1 은 '실행 前 광고주에게 제안한 의도'를 담는 영역이라 원천은 제안서다.
  그러나 실제 환경에서 제안서는 이미지로 굽힌 PDF 인 경우가 잦고(실측: 텍스트
  92자), 아예 업로드되지 않는 일도 흔하다. 따라서 제안서 하나에 의존하지 않고
  미디어브리프·포스트바이·세일즈가이드까지 넓게 훑는다.

추출 대상 (Config/overview_anchors.json 으로 키워드 외부화)
  goal      : 당면 과제 / 핵심 타겟 / 메인 카피
  strategy  : 미디어·크리에이티브 방향성 / 핵심 채널
  roadmap   : 전체 기간 / Phase 구분

원칙
  - 추측하지 않는다. 앵커가 걸린 실제 문장만 인용하고 출처를 남긴다.
  - 못 찾으면 빈 값으로 두고 confidence 를 낮춘다. 렌더러가 작성 가이드를 깐다.
  - 어떤 예외에도 파이프라인을 멈추지 않는다.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_FALLBACK: Dict[str, Any] = {
    "doc_priority": ["proposal", "media_brief", "sales_guide", "postbuy",
                     "creative", "daily_report", "media_mix"],
    "lookahead_lines": 6,
    "max_chars_per_field": 400,
    "anchors": {
        "challenge": ["캠페인 목표", "배경", "과제", "목적", "기대효과", "개요"],
        "core_target": ["핵심 타겟", "타겟 :", "타겟:", "타겟팅", "target", "tgt"],
        "key_message": ["key message", "핵심 메시지", "메인 카피", "슬로건",
                        "캠페인 테마", "kv", "메시지"],
        "direction": ["캠페인 전략", "미디어 전략", "커뮤니케이션 방향",
                      "방향성", "가이드라인", "strategy"],
        "channels": ["주요 매체", "핵심 매체", "채널", "매체 전략"],
        "roadmap": ["로드맵", "스케줄", "일정", "timeline", "phase",
                    "운영 기간", "집행 기간"],
    },
    "phase_patterns": [
        r"(?i)phase\s*([0-9])\s*[\.:：)]?\s*([^\n]{0,60})",
        r"^\s*([0-9])\)\s*([^:：\n]{2,40})[:：]\s*([^\n]{0,80})",
        r"\[([^\]]{2,20})\]\s*([^\n/]{0,60})",
    ],
    "channel_vocab": ["유튜브", "메타", "네이버", "카카오", "틱톡", "넷플릭스",
                      "티빙", "tvc", "ooh", "인플루언서", "체험단"],
    "noise_prefixes": ["*", "-", "·", "ㆍ", ">", "▶", "※", "끝."],
}

_DATE_RANGE = re.compile(
    r'(\d{1,2}\s*[/월]\s*\d{0,2}\s*(?:일)?\s*[~\-–]\s*\d{1,2}\s*[/월]\s*\d{0,2}\s*(?:일|말)?)'
    r'|(\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}\s*[~\-–]\s*\d{4}?[.\-/]?\d{1,2}[.\-/]\d{1,2})')


def _load_config(config_path: Optional[str]) -> Dict[str, Any]:
    path = (Path(config_path) if config_path else
            Path(__file__).resolve().parents[3] / 'Config' / 'overview_anchors.json')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return dict(_FALLBACK)
    merged = dict(_FALLBACK)
    for key, value in data.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            sub = dict(merged[key])
            sub.update(value)
            merged[key] = sub
        else:
            merged[key] = value
    return merged


class OverviewExtractor:
    """기획 의도 3요소를 문서 텍스트에서 발라낸다"""

    def __init__(self, config_path: Optional[str] = None):
        self.cfg = _load_config(config_path)

    # ────────────────────── 유틸

    def _clean(self, line: str) -> str:
        t = (line or '').strip()
        for p in self.cfg.get('noise_prefixes', []):
            if t.startswith(p):
                t = t[len(p):].strip()
        return t

    def _lines(self, text: str) -> List[str]:
        out = []
        for raw in (text or '').splitlines():
            t = self._clean(raw)
            if t and len(t) > 1:
                out.append(t)
        return out

    def _all_anchor_words(self) -> List[str]:
        words = []
        for group in self.cfg['anchors'].values():
            words.extend(w.lower() for w in group)
        return words

    def _section(self, lines: List[str], idx: int) -> str:
        """앵커 줄 + 뒤따르는 줄들을 다음 앵커 직전까지 모은다"""
        look = int(self.cfg.get('lookahead_lines', 6))
        others = self._all_anchor_words()
        head = lines[idx]
        # 'A : B' 형태면 콜론 뒤부터가 본문
        body = [head.split(':', 1)[1].strip() if ':' in head else head]
        for j in range(idx + 1, min(idx + 1 + look, len(lines))):
            nxt = lines[j]
            low = nxt.lower()
            # 다음 항목의 머리글이면 멈춘다 (짧고 앵커로 시작하는 줄)
            if len(nxt) < 24 and any(low.startswith(w) for w in others):
                break
            body.append(nxt)
        joined = ' / '.join(x for x in body if x)
        cap = int(self.cfg.get('max_chars_per_field', 400))
        return joined[:cap].strip(' /')

    def _is_noise(self, text: str) -> bool:
        """문서 관리용 메타 문장(보고 일정·업무 요청 등)은 기획 의도가 아니다"""
        low = (text or '').lower()
        return any(w.lower() in low for w in self.cfg.get('noise_contains', []))

    def _find(self, lines: List[str], field: str) -> Optional[str]:
        """
        앵커를 **설정에 적힌 순서대로** 시도하고 먼저 걸리는 것을 채택한다.

        가장 긴 구간을 고르면 '타겟 : 2559MF' 같은 정답 대신 '시기별 타겟팅
        예시' 처럼 길기만 한 매체 설명이 뽑힌다. 설정의 앞쪽일수록 구체적인
        앵커로 두고, 구체적인 것이 이기게 한다.
        """
        for word in self.cfg['anchors'].get(field, []):
            w = word.lower()
            for i, line in enumerate(lines):
                if w not in line.lower():
                    continue
                text = self._section(lines, i)
                if not text or len(text) < 6 or self._is_noise(text):
                    continue
                return text
        return None

    # ────────────────────── 개별 추출기

    def _phases(self, text: str) -> List[Dict[str, str]]:
        found: List[Dict[str, str]] = []
        seen = set()
        for pattern in self.cfg.get('phase_patterns', []):
            try:
                rx = re.compile(pattern, re.MULTILINE)
            except re.error:
                continue
            for m in rx.finditer(text or ''):
                groups = [g.strip() for g in m.groups() if g and g.strip()]
                if not groups:
                    continue
                raw_name = groups[0] if len(groups) == 1 else groups[-2]
                purpose = groups[-1] if len(groups) > 1 else ''
                name = re.sub(r'\s+', ' ', raw_name).strip(' :·-')
                # 이름에 붙은 기간 표기를 뗀다 — '런칭 초(4~5월)'
                period = ''
                paren = re.search(r'[\(（]([^\)）]{2,20})[\)）]', name)
                if paren:
                    period = paren.group(1).strip()
                    name = name[:paren.start()].strip()
                if not name or len(name) > 30:
                    continue
                key = name.lower()
                if key in seen:
                    continue
                seen.add(key)
                found.append({
                    'name': name,
                    'period': period,
                    'purpose': re.sub(r'\s+', ' ', purpose)[:120].strip(),
                })
        return found[:5]

    def _message(self, text: str) -> str:
        """
        메인 카피 전용 추출 — 슬로건은 문단이 아니라 짧은 문구다.

        일반 앵커 검색은 '캠페인 테마와 연계한 스포츠 IP 활용' 같은 전술 설명을
        통째로 물어 온다. 테마명·예시 카피·따옴표 문구를 우선 집는다.
        """
        src = text or ''
        parts: List[str] = []

        theme = re.search(r'(?:캠페인\s*)?테마\s*[（(]\s*([^)）]{2,24})\s*[)）]', src)
        if theme:
            parts.append(f'“{theme.group(1).strip()}”')

        slogan = re.search(r'(?:슬로건|메인\s*카피|key\s*message)\s*[:：]\s*([^\n]{4,60})',
                           src, re.IGNORECASE)
        if slogan:
            parts.append(slogan.group(1).strip())

        if len(parts) < 2:
            for m in re.finditer(r'^\s*(?:ex|예)\s*[)\]]\s*([^\n]{6,70})', src,
                                 re.MULTILINE | re.IGNORECASE):
                cand = m.group(1).strip()
                if cand not in parts:
                    parts.append(cand)
                    break

        if not parts:
            quoted = re.search(r'[“"\'‘]([^”"\'’\n]{8,60})[”"\'’]', src)
            if quoted:
                parts.append(quoted.group(1).strip())

        return ' — '.join(parts)[:180]

    def _channels(self, text: str) -> List[str]:
        low = (text or '').lower()
        out: List[str] = []
        for word in self.cfg.get('channel_vocab', []):
            if word.lower() in low:
                label = word.upper() if word.isascii() and len(word) <= 4 else word
                if label not in out:
                    out.append(label)
        return out[:12]

    def _period(self, text: str) -> str:
        m = _DATE_RANGE.search(text or '')
        if m:
            return re.sub(r'\s+', '', m.group(0))
        return ''

    # ────────────────────── 진입점

    def extract(self, documents: List[Any]) -> Dict[str, Any]:
        """
        Args:
            documents: SourceDocument 목록 (text_content 보유)

        Returns:
            CampaignKnowledge.overview 와 같은 구조의 dict
        """
        result: Dict[str, Any] = {
            'goal': {'challenge': '', 'core_target': '', 'key_message': ''},
            'strategy': {'direction': '', 'channels': []},
            'roadmap': {'period': '', 'phases': []},
            'sources': [], 'confidence': 'none', 'edited_by_ae': False,
        }

        priority = self.cfg.get('doc_priority', [])

        def rank(doc) -> int:
            role = getattr(doc, 'role', '') or ''
            return priority.index(role) if role in priority else len(priority)

        docs = sorted([d for d in (documents or [])
                       if len((getattr(d, 'text_content', '') or '')) > 120],
                      key=rank)
        if not docs:
            return result

        sources: List[str] = []
        field_map = (
            ('challenge', ('goal', 'challenge')),
            ('core_target', ('goal', 'core_target')),
            ('key_message', ('goal', 'key_message')),
            ('direction', ('strategy', 'direction')),
        )

        for doc in docs:
            text = getattr(doc, 'text_content', '') or ''
            name = getattr(doc, 'file_name', '') or ''
            lines = self._lines(text)
            used = False

            for field, (group, key) in field_map:
                if result[group][key]:
                    continue
                # 메인 카피는 문단이 아니라 문구 — 전용 추출을 먼저 시도한다
                got = (self._message(text) if field == 'key_message' else None) \
                    or self._find(lines, field)
                if got:
                    result[group][key] = got
                    used = True

            if not result['strategy']['channels']:
                chans = self._channels(text)
                if chans:
                    result['strategy']['channels'] = chans
                    used = True

            if not result['roadmap']['phases']:
                phases = self._phases(text)
                if phases:
                    result['roadmap']['phases'] = phases
                    used = True

            if not result['roadmap']['period']:
                road = self._find(lines, 'roadmap') or ''
                period = self._period(road) or self._period(text)
                if period:
                    result['roadmap']['period'] = period
                    used = True

            if used and name and name not in sources:
                sources.append(name)

        result['sources'] = sources
        result['confidence'] = self._confidence(result)
        return result

    @staticmethod
    def _confidence(result: Dict[str, Any]) -> str:
        filled = sum([
            bool(result['goal']['challenge']),
            bool(result['goal']['core_target']),
            bool(result['goal']['key_message']),
            bool(result['strategy']['direction']),
            bool(result['strategy']['channels']),
            bool(result['roadmap']['phases']),
        ])
        if filled >= 5:
            return 'high'
        if filled >= 3:
            return 'medium'
        if filled >= 1:
            return 'low'
        return 'none'


# ────────────────────── 완성도 판정 (렌더러·체크리스트 공용)

def has_goal(overview: Optional[Dict[str, Any]]) -> bool:
    g = (overview or {}).get('goal') or {}
    return bool(g.get('challenge') or g.get('core_target') or g.get('key_message'))


def has_strategy(overview: Optional[Dict[str, Any]]) -> bool:
    s = (overview or {}).get('strategy') or {}
    return bool(s.get('direction') or s.get('channels'))


def has_roadmap(overview: Optional[Dict[str, Any]]) -> bool:
    r = (overview or {}).get('roadmap') or {}
    return bool(r.get('phases'))


def extract(documents: List[Any],
            config_path: Optional[str] = None) -> Dict[str, Any]:
    """모듈 진입점 — 예외를 밖으로 던지지 않는다"""
    try:
        return OverviewExtractor(config_path).extract(documents)
    except Exception:
        return {
            'goal': {'challenge': '', 'core_target': '', 'key_message': ''},
            'strategy': {'direction': '', 'channels': []},
            'roadmap': {'period': '', 'phases': []},
            'sources': [], 'confidence': 'none', 'edited_by_ae': False,
        }
