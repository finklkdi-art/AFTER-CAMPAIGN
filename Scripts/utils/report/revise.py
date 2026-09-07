# -*- coding: utf-8 -*-
"""
Stage 4.5 — 슬라이드 문안 수정 어댑터 (Rule Book 1.4)

AE 의 자유 서술형 지시를 Claude API 로 해석해 해당 슬라이드의 문안만 다듬는다.
프로젝트의 유일한 외부 통신 지점이며, Rule Book 1.4 의 5대 조건을 코드로 강제한다.

  1) 허용 범위   — 문안(prose)만. 수치·출처·표 데이터는 전송도 교체도 하지 않는다
  2) 최소 전송   — 슬라이드 1장의 문안 + 지시문. 원본 문서·데이터셋은 절대 전송 금지
                   전송 내용 전문은 disclosure() 로 화면에 먼저 보여준다
  3) 키 관리     — .env 또는 환경변수에서만 로드. 코드·저장소에 하드코딩 금지
  4) 강등 동작   — 키 없음/통신 실패/응답 불량 시 규칙 기반 프리셋으로 자동 강등.
                   API 없이도 전 기능이 동작한다
  5) 감사        — 결과에 mode/preset/error 를 남겨 호출부가 Checklist 에 기재한다

🔴 수치 보호
  전송 대상에서 수치 카드·출처를 배제하고, 응답은 **줄 수가 같을 때만** 반영한다.
  LLM 이 근거 수치를 바꿔 쓰는 경로를 원천 차단한다 (Rule Book 3.2 데이터-해석 1:1).
"""

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

MODEL = 'claude-opus-5'
MAX_TOKENS = 16000
TIMEOUT_SEC = 60.0

# 문안 슬롯 정의 — 블록별로 '문안'으로 취급하는 경로만 여기에 둔다.
# 여기에 없는 필드(cards 의 수치·basis, blocks 의 evidence, sources)는
# 전송도 교체도 하지 않는다.
#
# 🔴 'summary' 는 의도적으로 제외했다.
#    캠페인 요약의 key_parts 는 ["총 ", "4.77억", " 운영 / 총 노출 ", ...] 처럼
#    강조 수치가 문장 중간에 런(run)으로 끼어든 구조다.
#    · 조각 단위로 보내면 "4.77억" 자체가 수정 대상이 된다
#    · 합쳐서 보내면 어느 조각이 강조였는지 되돌릴 수 없다
#    요약 문장은 데이터에서 결정론적으로 조립되므로 문안 수정 대상이 아니다.
PROSE_SLOTS: Dict[str, Tuple[str, ...]] = {
    'lesson': ('bullets',),
    'insight': ('blocks',),
    'strategy': ('headline', 'cards'),
}

# 수치 토큰 — 정수·소수·퍼센트·배수 표기를 모두 잡는다
_NUM_RE = re.compile(r'\d[\d,]*(?:\.\d+)?')

SYSTEM_PROMPT = (
    '너는 광고 대행사의 캠페인 결과보고서 문안을 다듬는 편집자다.\n'
    '규칙:\n'
    '1. 사실을 새로 만들지 마라. 주어진 문안에 없는 수치·매체명·고유명사를 '
    '추가하거나 바꾸지 마라.\n'
    '2. 문장은 명사형으로 끝내라 ("~의 필요", "~ 권고"). 동사 종결 금지.\n'
    '3. 근거 없는 긍정 포장을 하지 마라.\n'
    '4. 줄 수를 입력과 정확히 같게 유지하라. 줄을 합치거나 나누지 마라.\n'
    '5. 출력은 JSON 만. 형식: {"lines": ["...", "..."]}\n'
    '   설명·머리말·코드펜스 없이 JSON 객체 하나만 출력하라.'
)


# ═══════════════════════════ 결과 자료구조

@dataclass
class ReviseRequest:
    """수정 요청 — 전송 대상은 여기 담긴 것뿐이다"""
    block_id: str
    block_label: str
    lines: List[str]                       # 현재 문안 (수치 카드·출처 제외)
    instruction: str                       # AE 지시문


@dataclass
class ReviseResult:
    lines: List[str] = field(default_factory=list)
    mode: str = 'preset'                   # 'api' | 'preset'
    preset: str = ''                       # 강등 시 적용한 프리셋 이름
    note: str = ''
    error: str = ''
    usage: Dict[str, Any] = field(default_factory=dict)

    @property
    def used_api(self) -> bool:
        return self.mode == 'api'


# ═══════════════════════════ 3) 키 관리

def load_api_key(project_root: Optional[Path] = None) -> Optional[str]:
    """
    API 키를 환경변수 → Streamlit Secrets → .env 순으로 찾는다.

    - 환경변수: 로컬 실행·CI
    - st.secrets: 외부 호스팅(Streamlit Community Cloud 등)의 표준 비밀 관리
      (`.streamlit/secrets.toml`, 레포에 커밋하지 않음)
    - .env: 로컬 파일 (레포에 커밋하지 않음)
    python-dotenv 의존을 두지 않기 위해 최소 파서를 직접 쓴다.
    키 값을 로그·예외 메시지에 남기지 않는다.
    """
    key = (os.environ.get('ANTHROPIC_API_KEY') or '').strip()
    if key:
        return key

    # Streamlit Secrets — 호스팅 배포의 기본 경로. streamlit 미설치·secrets
    # 미설정 시 예외가 나므로 통째로 감싼다.
    try:
        import streamlit as st
        val = st.secrets.get('ANTHROPIC_API_KEY')       # type: ignore[attr-defined]
        if val and str(val).strip():
            return str(val).strip()
    except Exception:
        pass

    if project_root is None:
        project_root = Path(__file__).resolve().parents[3]
    env_path = Path(project_root) / '.env'
    if not env_path.is_file():
        return None
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                name, _, value = line.partition('=')
                if name.strip() != 'ANTHROPIC_API_KEY':
                    continue
                value = value.strip().strip('"').strip("'")
                if value:
                    return value
    except OSError:
        return None
    return None


def api_available(project_root: Optional[Path] = None) -> Tuple[bool, str]:
    """(사용 가능 여부, 사유) — 화면에 상태를 알려주기 위한 조회"""
    try:
        import anthropic                      # noqa: F401
    except ImportError:
        return False, 'anthropic 패키지 미설치 — `pip install anthropic`'
    if not load_api_key(project_root):
        return False, ('API 키 없음 — 호스팅은 Secrets(ANTHROPIC_API_KEY), '
                       '로컬은 환경변수나 `.env` 에 설정')
    return True, 'Claude API 사용 가능'


# ═══════════════════════════ 2) 최소 전송 — 전송 내용 공개

def disclosure(request: ReviseRequest) -> str:
    """
    전송 직전 화면에 그대로 보여줄 전문.

    Rule Book 1.4-2: AE 는 무엇이 나가는지 보고 나서 실행을 결정한다.
    이 함수가 만든 문자열이 곧 전송 본문이어야 한다 (payload() 와 동일 소스).
    """
    body = payload_text(request)
    return (f'[전송 대상 · Claude API ({MODEL})]\n'
            f'슬라이드: {request.block_label}\n'
            f'--- 여기서부터 실제 전송 본문 ---\n{body}\n'
            f'--- 전송 본문 끝 ---\n'
            f'※ 원본 문서 · 전체 데이터셋 · 일자별 실적 · 출처 표기는 '
            f'전송하지 않습니다.')


def payload_text(request: ReviseRequest) -> str:
    """실제 전송 본문 (문안 + 지시문만)"""
    numbered = '\n'.join(f'{i}. {ln}' for i, ln in enumerate(request.lines, 1))
    return (f'[수정 지시]\n{request.instruction.strip()}\n\n'
            f'[현재 문안 — 총 {len(request.lines)}줄]\n{numbered}')


# ═══════════════════════════ 4) 강등 — 규칙 기반 프리셋

def _has_number(s: str) -> bool:
    return bool(re.search(r'\d', s))


def _nounize(s: str) -> str:
    """동사 종결을 명사형으로 (Rule Book 3.2 문체 규칙)"""
    table = (
        ('해야 합니다', '의 필요'), ('해야 한다', '의 필요'),
        ('필요합니다', '의 필요'), ('합니다', ' 권고'),
        ('입니다', ''), ('했습니다', '됨'), ('됩니다', '됨'),
        ('하십시오', ' 권고'), ('하세요', ' 권고'),
    )
    out = s.rstrip()
    for a, b in table:
        if out.endswith(a):
            return out[:-len(a)].rstrip() + b
    return out


PRESETS: Dict[str, Tuple[Tuple[str, ...], str]] = {
    'lesson_first': (('레슨', '런', 'lesson', '교훈', '배운'),
                     '레슨런 중심 — 제안·개선 문장을 앞으로'),
    'numbers_first': (('수치', '숫자', '데이터', '근거', 'number'),
                      '수치 중심 — 숫자가 있는 문장을 앞으로'),
    'concise': (('간결', '짧게', '줄여', '요약', 'concise'),
                '간결 — 문장 길이 축약'),
    'assertive': (('단호', '강하게', '강조', '확실', 'assertive'),
                  '단호 — 명사형 종결 강화'),
}


def pick_preset(instruction: str) -> str:
    """지시문 키워드로 프리셋을 고른다 (미매칭이면 'assertive')"""
    low = (instruction or '').lower()
    for name, (keywords, _) in PRESETS.items():
        if any(k in low for k in keywords):
            return name
    return 'assertive'


def apply_preset(lines: List[str], preset: str) -> List[str]:
    """
    규칙 기반 재구성.

    🔴 내용을 창작하지 않는다. 순서 변경·어미 정리·축약만 한다.
    줄 수는 반드시 유지한다 (슬롯 수가 곧 슬라이드 구조이므로).
    """
    out = list(lines)
    if preset == 'lesson_first':
        hint = ('권고', '필요', '검토', '조정', '확대', '개선', '상향', '강화')
        out.sort(key=lambda s: 0 if any(h in s for h in hint) else 1)
    elif preset == 'numbers_first':
        out.sort(key=lambda s: 0 if _has_number(s) else 1)
    elif preset == 'concise':
        out = [(s if len(s) <= 42 else s[:41].rstrip() + '…') for s in out]
    elif preset == 'assertive':
        out = [_nounize(s) for s in out]
    return out


# ═══════════════════════════ 본체

def _parse_reply(text: str, expected: int) -> Tuple[List[str], str]:
    """
    응답에서 lines 배열을 꺼낸다.

    줄 수가 다르면 채택하지 않는다 — 슬롯 수가 달라지면 슬라이드 구조가
    깨지고, 어느 근거가 어느 문장에 붙는지 대응이 무너진다.
    """
    body = (text or '').strip()
    if body.startswith('```'):
        body = re.sub(r'^```[a-zA-Z]*\s*|\s*```$', '', body).strip()
    try:
        data = json.loads(body)
    except ValueError:
        m = re.search(r'\{.*\}', body, re.S)
        if not m:
            return [], '응답이 JSON 형식이 아님'
        try:
            data = json.loads(m.group())
        except ValueError:
            return [], '응답 JSON 파싱 실패'

    lines = data.get('lines') if isinstance(data, dict) else None
    if not isinstance(lines, list) or not all(isinstance(x, str) for x in lines):
        return [], '응답에 lines 문자열 배열이 없음'
    lines = [x.strip() for x in lines]
    if len(lines) != expected:
        return [], f'줄 수 불일치 (요청 {expected} / 응답 {len(lines)})'
    if any(not x for x in lines):
        return [], '빈 문안이 포함됨'
    return lines, ''


def numeric_drift(before: List[str], after: List[str]) -> List[str]:
    """
    수정 전후로 수치가 바뀌었는지 검사한다.

    프롬프트로 "수치를 바꾸지 말라"고 지시하는 것은 구조적 보장이 아니다.
    이 프로젝트는 모든 주장에 근거 수치를 병기하므로(Rule Book 3.2),
    문안 교정이 근거 수치를 흔들면 보고서의 신뢰가 무너진다.
    전체 문안의 수치 다중집합(multiset)이 같은지 대조해 강등 판단에 쓴다.

    Returns: 사라진/새로 생긴 수치 목록 (빈 리스트면 이상 없음)
    """
    def bag(lines: List[str]) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for ln in lines:
            for tok in _NUM_RE.findall(ln or ''):
                key = tok.replace(',', '')
                out[key] = out.get(key, 0) + 1
        return out

    b, a = bag(before), bag(after)
    diff: List[str] = []
    for k in sorted(set(b) | set(a)):
        if b.get(k, 0) != a.get(k, 0):
            diff.append(f'{k} ({b.get(k, 0)}→{a.get(k, 0)}회)')
    return diff


def revise(request: ReviseRequest, *,
           project_root: Optional[Path] = None,
           allow_api: bool = True) -> ReviseResult:
    """
    문안을 수정한다. API 를 쓸 수 없거나 실패하면 프리셋으로 강등한다.

    이 함수는 **예외를 던지지 않는다.** 어떤 실패에도 결과를 돌려주어
    파이프라인이 멈추지 않게 한다 (Rule Book 1.4-4 / 3.3).
    """
    if not request.lines:
        return ReviseResult(lines=[], mode='preset',
                            error='수정할 문안이 없음')

    def degrade(reason: str) -> ReviseResult:
        name = pick_preset(request.instruction)
        return ReviseResult(
            lines=apply_preset(request.lines, name),
            mode='preset', preset=name,
            note=PRESETS[name][1], error=reason)

    if not allow_api:
        return degrade('AE 가 API 사용을 선택하지 않음')

    ok, reason = api_available(project_root)
    if not ok:
        return degrade(reason)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=load_api_key(project_root),
                                     timeout=TIMEOUT_SEC, max_retries=1)
        kwargs = dict(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            # 단순 문안 교정이므로 낮은 effort 로 지연·비용을 줄인다
            output_config={'effort': 'low'},
            messages=[{'role': 'user', 'content': payload_text(request)}],
        )
        try:
            # 정책 거절 시 서버측 폴백 (권장 기본값)
            resp = client.beta.messages.create(
                betas=['server-side-fallback-2026-07-01'],
                fallbacks='default', **kwargs)
        except anthropic.BadRequestError:
            # 베타 파라미터를 쓸 수 없는 환경이면 표준 엔드포인트로 재시도
            resp = client.messages.create(**kwargs)
    except ImportError as e:
        return degrade(f'anthropic 임포트 실패: {e}')
    except Exception as e:                     # 통신·인증·한도 등 전부 강등
        try:
            import anthropic
            if isinstance(e, anthropic.AuthenticationError):
                return degrade('API 키 인증 실패')
            if isinstance(e, anthropic.RateLimitError):
                return degrade('API 호출 한도 초과 — 잠시 후 재시도')
            if isinstance(e, anthropic.APITimeoutError):
                return degrade(f'API 응답 시간 초과 ({TIMEOUT_SEC:.0f}초)')
            if isinstance(e, anthropic.APIConnectionError):
                return degrade('네트워크 연결 실패 (사내망 차단 여부 확인)')
        except ImportError:
            pass
        return degrade(f'API 호출 실패: {type(e).__name__}')

    if getattr(resp, 'stop_reason', None) == 'refusal':
        return degrade('API 가 요청을 수행하지 않음 (정책 거절)')

    text = ''.join(b.text for b in (resp.content or [])
                   if getattr(b, 'type', '') == 'text')
    lines, err = _parse_reply(text, len(request.lines))
    if err:
        return degrade(f'응답 형식 불량 — {err}')

    # 🔴 수치 무결성 — 근거 수치가 바뀌면 채택하지 않고 강등한다
    drift = numeric_drift(request.lines, lines)
    if drift:
        return degrade('수치가 변경되어 반영하지 않음 — '
                       + ', '.join(drift[:4]))

    usage = {}
    u = getattr(resp, 'usage', None)
    if u is not None:
        usage = {'input_tokens': getattr(u, 'input_tokens', None),
                 'output_tokens': getattr(u, 'output_tokens', None)}
    return ReviseResult(lines=lines, mode='api',
                        note=f'{MODEL} 로 문안 수정', usage=usage)


# ═══════════════════════════ 1) 문안 추출 / 반영 (수치·출처 미포함)

def extract_lines(slide) -> List[str]:
    """
    슬라이드에서 수정 대상 문안만 순서대로 뽑는다.

    수치 카드(cards 의 값)와 sources 는 포함하지 않는다.
    extract_lines() 와 apply_lines() 는 같은 순서를 쓰므로 슬롯이 1:1 대응된다.
    """
    p = slide.payload or {}
    out: List[str] = []
    for key in PROSE_SLOTS.get(slide.block_id, ()):
        v = p.get(key)
        if key == 'headline' and isinstance(v, str):
            out.append(v)
        elif key == 'key_parts' and isinstance(v, list):
            out.extend(str(x.get('text', '')) for x in v
                       if isinstance(x, dict))
        elif key == 'bullets' and isinstance(v, list):
            out.extend(str(x) for x in v)
        elif key == 'blocks' and isinstance(v, list):
            for b in v:
                if isinstance(b, dict):
                    out.append(str(b.get('finding', '')))
                    out.append(str(b.get('recommendation', '')))
        elif key == 'cards' and isinstance(v, list):
            for c in v:
                if isinstance(c, dict):        # strategy: direction 만
                    out.append(str(c.get('direction', '')))
    return out


def apply_lines(slide, lines: List[str]) -> bool:
    """
    수정된 문안을 슬라이드에 반영한다 (표현 계층만 변경).

    원본 데이터(dataset)는 건드리지 않으며, 되돌릴 수 있도록
    payload['_original'] 에 최초 문안을 보관한다.
    """
    slots = extract_lines(slide)
    if len(lines) != len(slots):
        return False

    p = slide.payload
    if '_original' not in p:
        p['_original'] = list(slots)

    it = iter(lines)
    for key in PROSE_SLOTS.get(slide.block_id, ()):
        v = p.get(key)
        if key == 'headline' and isinstance(v, str):
            p[key] = next(it)
        elif key == 'key_parts' and isinstance(v, list):
            for x in v:
                if isinstance(x, dict):
                    x['text'] = next(it)
        elif key == 'bullets' and isinstance(v, list):
            p[key] = [next(it) for _ in v]
        elif key == 'blocks' and isinstance(v, list):
            for b in v:
                if isinstance(b, dict):
                    b['finding'] = next(it)
                    b['recommendation'] = next(it)
        elif key == 'cards' and isinstance(v, list):
            for c in v:
                if isinstance(c, dict):
                    c['direction'] = next(it)
    return True


def restore_original(slide) -> bool:
    """최초 문안으로 되돌린다 (AE 가 수정을 취소할 때)"""
    original = (slide.payload or {}).get('_original')
    if not original:
        return False
    return apply_lines(slide, list(original))
