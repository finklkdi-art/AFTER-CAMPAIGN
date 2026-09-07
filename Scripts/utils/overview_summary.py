# -*- coding: utf-8 -*-
"""
캠페인 개요(기획 의도) 압축 요약 — Claude API (claude.md 1.2 예외 조항)

파서가 훑어 온 원문은 문단째라 장표에 그대로 실을 수 없다. 비즈니스 톤으로
2~3줄로 줄인다.

준수 사항
  - 최소 전송: 개요 텍스트 필드만 보낸다. 원본 문서·데이터셋은 보내지 않는다.
  - 전송 전 payload_text() 를 화면에 그대로 보여 주고 AE 의 실행 확인을 받는다.
  - 키가 없거나 실패하면 원문을 그대로 두고 파이프라인을 계속 진행한다.
  - 입력에 없는 사실을 만들지 않는다 (환각 차단).
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

MODEL = 'claude-opus-5'
MAX_TOKENS = 2000
TIMEOUT_SEC = 40

SYSTEM_PROMPT = """당신은 광고대행사의 수석 AE다. 캠페인 결과보고서 Part 1(캠페인 개요)에
실을 '기획 의도' 문구를 다듬는다.

[입력]
제안서·미디어브리프에서 기계적으로 긁어온 원문 조각이다. 문단이 섞여 있고 군더더기가 많다.

[할 일]
각 항목을 보고서 장표에 바로 실을 수 있게 압축한다.
- challenge  : 당면 과제 — 이 캠페인을 왜 했는지. 1~2문장.
- core_target: 핵심 타겟 — 누구인지. 1~2문장.
- key_message: 메인 카피/메시지 — 슬로건이나 핵심 메시지. 짧게.
- direction  : 미디어·크리에이티브 방향성. 2~3문장.

[문체]
- 개조식 명사형 종결: ~필요 / ~공략 / ~확보 / ~전개 / ~중심
- 서술형 어미 금지: ~합니다 / ~입니다 / ~한다 / ~이다
- 한 문장 45자 이내. 비즈니스 보고 톤.
- 경쟁사는 'X사', 자사는 '당사'.

[사실 규칙 — 가장 중요]
- 입력에 없는 수치·브랜드·매체·타겟을 새로 만들지 마라.
- 입력이 비어 있거나 근거가 없으면 그 항목은 빈 문자열 ""로 두라. 지어내지 마라.
- 과장 수식어(획기적, 압도적) 금지.

[출력]
JSON 객체만 반환. 설명 문장 금지.
{"challenge": "...", "core_target": "...", "key_message": "...", "direction": "..."}"""


@dataclass
class SummaryResult:
    ok: bool = False
    reason: str = ''
    fields: Dict[str, str] = field(default_factory=dict)
    used_api: bool = False


def _src(overview: Dict[str, Any]) -> Dict[str, str]:
    goal = (overview or {}).get('goal') or {}
    strat = (overview or {}).get('strategy') or {}
    return {
        'challenge': (goal.get('challenge') or '').strip(),
        'core_target': (goal.get('core_target') or '').strip(),
        'key_message': (goal.get('key_message') or '').strip(),
        'direction': (strat.get('direction') or '').strip(),
    }


def payload_text(overview: Dict[str, Any]) -> str:
    """전송 대상 미리보기 — 화면에 이대로 보여 준다"""
    src = _src(overview)
    lines = [f'[전송 대상 · Claude API ({MODEL})]',
             '캠페인 개요 원문 4개 항목만 전송합니다. 원본 문서는 전송하지 않습니다.', '']
    labels = {'challenge': '당면 과제', 'core_target': '핵심 타겟',
              'key_message': '메인 카피', 'direction': '전략 방향'}
    for key, label in labels.items():
        value = src.get(key) or '(비어 있음)'
        lines.append(f'- {label}: {value}')
    return '\n'.join(lines)


def available(project_root: Optional[Path] = None):
    """(사용 가능 여부, 사유) — revise.py 의 키 관리 재사용"""
    try:
        from utils.report import revise as R
    except Exception as e:
        return False, f'API 어댑터 로딩 실패: {e}'
    return R.api_available(project_root)


_NARRATIVE = re.compile(r'(습니다|입니다|합니다|한다|이다|였다)\s*$')


def _clean(value: Any) -> str:
    text = re.sub(r'\s+', ' ', str(value or '')).strip()
    if not text:
        return ''
    # 서술형 어미가 남으면 문체 규칙 위반 — 채택하지 않는다
    if _NARRATIVE.search(text):
        return ''
    return text[:200]


def summarize(overview: Dict[str, Any],
              project_root: Optional[Path] = None) -> SummaryResult:
    """
    개요를 2~3줄로 압축한다. 실패 시 ok=False 로 돌려주고 호출부는 원문을 유지한다.
    """
    src = _src(overview)
    if not any(src.values()):
        return SummaryResult(False, '요약할 원문이 없음')

    ok, reason = available(project_root)
    if not ok:
        return SummaryResult(False, reason)

    try:
        from utils.report import revise as R
        import anthropic
        client = anthropic.Anthropic(api_key=R.load_api_key(project_root),
                                     timeout=TIMEOUT_SEC, max_retries=1)
        message = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            output_config={'effort': 'low'},
            messages=[{'role': 'user',
                       'content': json.dumps(src, ensure_ascii=False)}],
        )
        raw = ''.join(b.text for b in message.content if getattr(b, 'text', ''))
    except Exception as e:
        return SummaryResult(False, f'API 호출 실패: {type(e).__name__}')

    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not match:
        return SummaryResult(False, '응답 형식 오류')
    try:
        data = json.loads(match.group(0))
    except Exception:
        return SummaryResult(False, '응답 파싱 실패')

    fields = {k: _clean(data.get(k)) for k in src}
    # 원문이 비었던 항목을 채워 넣지 않는다 (없는 사실 생성 차단)
    fields = {k: v for k, v in fields.items() if v and src.get(k)}
    if not fields:
        return SummaryResult(False, '채택할 요약 없음')
    return SummaryResult(True, '', fields, used_api=True)
