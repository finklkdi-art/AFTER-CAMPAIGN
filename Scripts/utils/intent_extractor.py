# -*- coding: utf-8 -*-
"""
Part 1 캠페인 개요 — 기획 의도(Intent) 추출기

제안서·미디어 브리프 등 '캠페인 실행 이전' 문서에서 아래 셋을 발라낸다.
  캠페인 목표   당면 과제 · 핵심 타겟 · 메인 카피
  캠페인 전략   미디어/크리에이티브 믹스 방향성 · 핵심 채널
  캠페인 로드맵 월별·주차별 타임라인과 Phase 구분

설계 전제
  · 동료 AE 가 제안서를 올리지 않고 포스트바이만 올리는 경우가 잦다.
    따라서 제안서가 없어도 미디어 브리프·데일리리포트 요약 시트 등에서
    개요를 유추하도록 앵커를 넓게 던진다(그물망 파싱).
  · 못 찾는 것이 실패가 아니다. 빈 CampaignIntent 를 돌려주고, 렌더러가
    작성 가이드를 얹는다. 예외를 던져 파이프라인을 멈추지 않는다.
  · 추출값은 '후보'다. Stage 1.5 에서 AE 가 확인·수정한다 (Rule Book 2.2).
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from models.campaign_data import CampaignIntent, IntentPhase, Provenance
from models.campaign_knowledge import CampaignKnowledge
from models.source_document import SourceDocument

_FALLBACK: Dict[str, Any] = {
    "doc_priority": ["proposal", "media_brief", "sales_guide", "creative",
                     "media_mix", "daily_report", "postbuy", "unknown"],
    "anchors": {
        "challenge": ["당면 과제", "캠페인 배경", "캠페인 목표", "배경", "목적"],
        "core_target": ["핵심 타겟", "Core Target", "타겟팅", "Target", "타겟"],
        "key_message": ["메인 카피", "Key Message", "핵심 메시지", "슬로건", "KV"],
        "mix_direction": ["캠페인 전략", "미디어 전략", "커뮤니케이션 전략", "전략"],
        "channels": ["주요 매체", "활용 매체", "집행 매체", "채널"],
        "roadmap": ["캠페인 로드맵", "스케줄", "Timeline", "일정", "Phase"],
    },
    "known_channels": ["유튜브", "메타", "네이버", "카카오", "틱톡", "OOH"],
    "phase_pattern": r"(Phase\s*[0-9]+|[1-4]\s*차\b|런칭기|성수기|확산기|전환기)",
    "capture": {"max_chars": 160, "min_chars": 6},
}

# 캡처 앞머리에서 걷어낼 구분자
_LEAD = ' \t:：=·•▪◦-–—>》」』])>'
# 값으로 보기 어려운 잡음 (표 머리글·페이지 번호 등)
_NOISE = re.compile(r'^[\s0-9.\-–—|/()]*$')
_DATE = re.compile(r'\d{1,2}\s*[/.월]\s*\d{0,2}')


def _load_config(project_root: Optional[Path] = None) -> Dict[str, Any]:
    """Config/intent_anchors.json — 없거나 깨져도 내장 기본값으로 동작"""
    if project_root:
        path = Path(project_root) / 'Config' / 'intent_anchors.json'
    else:
        path = (Path(__file__).resolve().parent.parent.parent
                / 'Config' / 'intent_anchors.json')
    merged = json.loads(json.dumps(_FALLBACK))       # deep copy
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return merged
    for key, value in data.items():
        if key.startswith('_'):
            continue
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            sub = dict(merged[key])
            sub.update(value)
            merged[key] = sub
        else:
            merged[key] = value
    return merged


# ─────────────────────────── 캡처

def _clean(seg: str) -> str:
    seg = seg.replace('​', ' ').strip()
    seg = seg.lstrip(_LEAD).strip()
    # 다음 항목 머리글이 붙어 오면 거기서 끊는다
    seg = re.split(r'\s{3,}|[|]{2,}', seg)[0]
    return ' '.join(seg.split())


def _candidates(text: str, anchor: str, max_chars: int) -> List[str]:
    """
    앵커 뒤 텍스트를 후보로 만든다.

    문서마다 표기가 달라 두 형태를 모두 본다.
      (a) 같은 줄:  '핵심 타겟 : 2534 남녀'
      (b) 다음 줄:  '핵심 타겟\n2534 남녀'
    """
    out: List[str] = []
    low, a = text.lower(), anchor.lower()
    start = 0
    while True:
        i = low.find(a, start)
        if i < 0:
            break
        start = i + len(a)
        tail = text[start:start + max_chars]

        same_line = _clean(tail.split('\n', 1)[0])
        if same_line:
            out.append(same_line)

        parts = tail.split('\n', 1)
        if len(parts) > 1:
            for nxt in parts[1].split('\n'):
                nxt = _clean(nxt)
                if nxt:
                    out.append(nxt)
                    break
        if len(out) >= 6:
            break
    return out


def _pick(text: str, anchors: List[str], cap: Dict[str, int],
          reject: List[str]) -> Tuple[str, str]:
    """
    앵커 목록을 순서대로 던져 첫 유효 후보를 고른다.

    Returns:
        (값, 사용한 앵커) — 못 찾으면 ('', '')
    """
    min_chars = int(cap.get('min_chars', 6))
    max_chars = int(cap.get('max_chars', 160))
    for anchor in anchors:
        for cand in _candidates(text, anchor, max_chars):
            if len(cand) < min_chars or len(cand) > max_chars:
                continue
            if _NOISE.match(cand):
                continue
            # 다른 앵커만 덩그러니 잡힌 경우 배제
            if any(cand.strip().lower() == r.lower() for r in reject):
                continue
            return cand, anchor
    return '', ''


# ─────────────────────────── 항목별 추출

def _extract_channels(text: str, known: List[str]) -> List[str]:
    """본문에 등장하는 알려진 매체명을 등장 순서대로 수집"""
    found: List[str] = []
    low = text.lower()
    for name in known:
        if name.lower() in low and name not in found:
            found.append(name)
    return found


def _extract_phases(text: str, pattern: str) -> List[IntentPhase]:
    """Phase 표기가 있는 줄에서 (이름, 기간, 목적)을 뽑는다"""
    try:
        rx = re.compile(pattern, re.IGNORECASE)
    except re.error:
        return []
    phases: List[IntentPhase] = []
    seen = set()
    for line in text.split('\n'):
        line = ' '.join(line.split())
        if not line or len(line) > 180:
            continue
        m = rx.search(line)
        if not m:
            continue
        name = ' '.join(m.group(0).split())
        if name.lower() in seen:
            continue
        seen.add(name.lower())

        rest = _clean(line[m.end():])
        period = ''
        dates = _DATE.findall(line)
        if len(dates) >= 2:
            period = f'{dates[0]} ~ {dates[1]}'
        elif dates:
            period = dates[0]
        # 목적에서 기간 표기는 걷어낸다
        purpose = _DATE.sub('', rest).strip(' ~-–—|·,')
        purpose = ' '.join(purpose.split())[:60]

        phases.append(IntentPhase(name=name, period=period, purpose=purpose))
        if len(phases) >= 6:
            break
    return phases


# ─────────────────────────── 진입점

def _ordered_docs(knowledge: CampaignKnowledge,
                  priority: List[str]) -> List[SourceDocument]:
    """역할 우선순위대로 문서를 세운다 (목록에 없는 역할은 맨 뒤)"""
    docs = [d for d in (knowledge.documents or [])
            if d.is_usable() and (d.text_content or '').strip()]

    def rank(d: SourceDocument) -> int:
        try:
            return priority.index(d.role)
        except ValueError:
            return len(priority)

    return sorted(docs, key=rank)


def extract(knowledge: CampaignKnowledge,
            project_root: Optional[Path] = None) -> CampaignIntent:
    """
    기획 의도를 추출한다. 어떤 경우에도 예외를 던지지 않는다.

    Returns:
        CampaignIntent — 하나도 못 찾으면 빈 객체 (렌더러가 가이드로 대체)
    """
    intent = CampaignIntent()
    try:
        cfg = _load_config(project_root)
    except Exception:
        cfg = json.loads(json.dumps(_FALLBACK))

    anchors: Dict[str, List[str]] = cfg.get('anchors', {})
    cap: Dict[str, int] = cfg.get('capture', {})
    docs = _ordered_docs(knowledge, cfg.get('doc_priority', []))
    if not docs:
        return intent

    # 다른 앵커가 통째로 잡히는 것을 막기 위한 배제 목록
    reject = [a for group in anchors.values() for a in group]

    text_fields = (
        ('challenge', 'challenge'),
        ('core_target', 'core_target'),
        ('key_message', 'key_message'),
        ('mix_direction', 'mix_direction'),
    )

    for doc in docs:
        text = doc.text_content or ''
        if not text.strip():
            continue
        label = f'{doc.file_name}'

        for field_name, anchor_key in text_fields:
            if getattr(intent, field_name):
                continue
            value, used = _pick(text, anchors.get(anchor_key, []), cap, reject)
            if value:
                setattr(intent, field_name, value)
                intent.snippets[field_name] = f'{used} → {value}'
                if label not in intent.sources:
                    intent.sources.append(label)

        if not intent.channels:
            found = _extract_channels(text, cfg.get('known_channels', []))
            # 채널은 '주요 매체' 앵커 주변에서 잡히면 더 정확하지만,
            # 없으면 문서 전체 등장 매체로 갈음한다 (그물망)
            if found:
                intent.channels = found[:8]
                intent.snippets['channels'] = ', '.join(found[:8])
                if label not in intent.sources:
                    intent.sources.append(label)

        if not intent.phases:
            phases = _extract_phases(text, cfg.get('phase_pattern', ''))
            if phases:
                for p in phases:
                    p.source = Provenance(file_name=doc.file_name)
                intent.phases = phases
                if label not in intent.sources:
                    intent.sources.append(label)

        if not intent.timeline_note:
            value, used = _pick(text, anchors.get('roadmap', []), cap, reject)
            if value:
                intent.timeline_note = value
                intent.snippets['roadmap'] = f'{used} → {value}'
                if label not in intent.sources:
                    intent.sources.append(label)

    return intent
