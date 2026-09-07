# -*- coding: utf-8 -*-
"""
Stage 1.5 — Part 1 캠페인 개요(기획 의도) 거시 검증

제안서·미디어브리프에서 그물망으로 훑어 온 '실행 前 의도'를 AE 가 확인하고
고친다. 원문이 길어 그대로는 장표에 안 실리므로 AI 압축 요약을 붙였다.

원칙
  - AI 가 먼저 제안하고 AE 는 확인·수정만 한다 (빈 칸 채우기 강요 금지).
  - 소스가 없으면 비워 두고 넘긴다 — 장표는 삭제되지 않고 작성 가이드가 깔린다.
  - API 전송 전 무엇이 나가는지 보여 주고 실행 확인을 받는다 (claude.md 1.2).
"""

from typing import Any, Dict, List

import streamlit as st

from models.campaign_knowledge import CampaignKnowledge

from dashboard import state, theme_css as T

_P = 'ax_ov'

_FIELDS = (
    ('challenge', '당면 과제', '이 캠페인을 왜 진행했는지'),
    ('core_target', '핵심 타겟', '누구를 대상으로 했는지'),
    ('key_message', '메인 카피 · 메시지', '어떤 메시지를 전달했는지'),
)

_CONF = {'high': '충분히 찾았어요', 'medium': '일부만 찾았어요',
         'low': '조금밖에 못 찾았어요', 'none': '못 찾았어요'}


def _blank() -> Dict[str, Any]:
    return {
        'goal': {'challenge': '', 'core_target': '', 'key_message': ''},
        'strategy': {'direction': '', 'channels': []},
        'roadmap': {'period': '', 'phases': []},
        'sources': [], 'confidence': 'none', 'edited_by_ae': False,
    }


def _phases_text(phases: List[Dict[str, str]]) -> str:
    return '\n'.join(
        f"{p.get('name','')} | {p.get('period','')} | {p.get('purpose','')}"
        for p in phases)


def _parse_phases(text: str) -> List[Dict[str, str]]:
    out = []
    for line in (text or '').splitlines():
        if not line.strip():
            continue
        parts = [x.strip() for x in line.split('|')]
        name = parts[0] if parts else ''
        if not name:
            continue
        out.append({
            'name': name,
            'period': parts[1] if len(parts) > 1 else '',
            'purpose': parts[2] if len(parts) > 2 else '',
        })
    return out


def _apply(knowledge: CampaignKnowledge) -> bool:
    """화면 값을 knowledge.overview 에 반영. 바뀐 게 있으면 True."""
    ov = getattr(knowledge, 'overview', None) or _blank()
    changed = False

    for key, _label, _hint in _FIELDS:
        new = (st.session_state.get(f'{_P}_{key}') or '').strip()
        if new != (ov['goal'].get(key) or ''):
            ov['goal'][key] = new
            changed = True

    direction = (st.session_state.get(f'{_P}_direction') or '').strip()
    if direction != (ov['strategy'].get('direction') or ''):
        ov['strategy']['direction'] = direction
        changed = True

    raw = (st.session_state.get(f'{_P}_channels') or '').strip()
    chans = [c.strip() for c in raw.replace('\n', ',').split(',') if c.strip()]
    if chans != (ov['strategy'].get('channels') or []):
        ov['strategy']['channels'] = chans
        changed = True

    period = (st.session_state.get(f'{_P}_period') or '').strip()
    if period != (ov['roadmap'].get('period') or ''):
        ov['roadmap']['period'] = period
        changed = True

    phases = _parse_phases(st.session_state.get(f'{_P}_phases') or '')
    if phases != (ov['roadmap'].get('phases') or []):
        ov['roadmap']['phases'] = phases
        changed = True

    if changed:
        ov['edited_by_ae'] = True
    knowledge.overview = ov
    return changed


def _summary_gate(knowledge: CampaignKnowledge, project_root) -> None:
    """
    전송 전 확인 — 무엇이 나가는지 그대로 보여 주고 실행 확인을 받는다.
    (claude.md 1.2 최소 전송 원칙 · 자동 전송 금지)
    """
    try:
        from utils import overview_summary as S
    except Exception as e:
        st.warning(f'요약 기능을 불러오지 못했어요: {e}')
        state.put(f'{_P}_pending', False)
        return

    ok, reason = S.available(project_root)
    if not ok:
        T.note(f'Claude API 미사용 — {reason} · 원문을 그대로 쓸게요.', 'warn')
        state.put(f'{_P}_pending', False)
        return

    st.markdown('###### 이 내용만 전송돼요')
    st.code(S.payload_text(knowledge.overview), language=None)
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button('취소', key=f'{_P}_cancel', width='stretch'):
            state.put(f'{_P}_pending', False)
            st.rerun()
    with c2:
        if st.button('전송하고 요약', key=f'{_P}_send', type='primary',
                     width='stretch'):
            state.put(f'{_P}_pending', False)
            _summarize(knowledge, project_root)


def _summarize(knowledge: CampaignKnowledge, project_root) -> None:
    """Claude API 로 2~3줄 압축 요약 — 실패해도 원문을 유지한다"""
    from utils import overview_summary as S
    ov = knowledge.overview
    with st.spinner('기획 의도를 요약하는 중...'):
        result = S.summarize(ov, project_root=project_root)
    if not result.ok:
        T.note(f'요약하지 못했어요 — {result.reason} · 원문을 그대로 둘게요.', 'warn')
        return
    for key, value in (result.fields or {}).items():
        if value and key in ('challenge', 'core_target', 'key_message'):
            ov['goal'][key] = value
        elif value and key == 'direction':
            ov['strategy']['direction'] = value
    ov['edited_by_ae'] = True
    knowledge.overview = ov
    state.set_knowledge(knowledge)
    state.put(state.KEY_FLASH, 'AI 요약을 반영했어요. 문구를 확인해 주세요.')
    st.rerun()


def render(knowledge: CampaignKnowledge, project_root=None) -> None:
    ov = getattr(knowledge, 'overview', None) or _blank()
    goal = ov.get('goal') or {}
    strat = ov.get('strategy') or {}
    road = ov.get('roadmap') or {}
    conf = ov.get('confidence', 'none')

    st.markdown('### 캠페인 개요(기획 의도)를 확인해 주세요')
    st.markdown(
        '<p class="ax-lead">'
        '<span class="kbr">보고서 Part 1에 그대로 실리는 내용이에요.</span> '
        '<span class="kbr">제안서·미디어브리프에서 찾아 둔 초안이니</span> '
        '<span class="kbr">확인하고 고쳐 주세요.</span></p>',
        unsafe_allow_html=True)

    src = ', '.join(ov.get('sources') or []) or '찾은 문서 없음'
    st.caption(f'{_CONF.get(conf, conf)} · 출처: {src}')

    if conf == 'none':
        T.note('기획 의도를 담은 문서를 찾지 못했어요. 비워 두셔도 보고서에는 '
               '슬라이드가 남고 작성 가이드가 들어가요.', 'warn')

    st.markdown('###### 캠페인 목표')
    for key, label, hint in _FIELDS:
        st.text_area(f'{label} — {hint}', value=goal.get(key, '') or '',
                     key=f'{_P}_{key}', height=78)

    st.markdown('###### 캠페인 전략')
    st.text_area('미디어·크리에이티브 방향성',
                 value=strat.get('direction', '') or '',
                 key=f'{_P}_direction', height=90)
    st.text_input('핵심 채널 (쉼표로 구분)',
                  value=', '.join(strat.get('channels') or []),
                  key=f'{_P}_channels')

    st.markdown('###### 캠페인 로드맵')
    st.text_input('전체 기간', value=road.get('period', '') or '',
                  key=f'{_P}_period')
    st.text_area('Phase — 한 줄에 하나씩 `이름 | 기간 | 목적`',
                 value=_phases_text(road.get('phases') or []),
                 key=f'{_P}_phases', height=100)

    if state.get(f'{_P}_pending'):
        _summary_gate(knowledge, project_root)
        return

    c1, c2 = st.columns([1, 1.4])
    with c1:
        if st.button('AI로 2~3줄 요약', width='stretch'):
            _apply(knowledge)
            state.set_knowledge(knowledge)
            state.put(f'{_P}_pending', True)
            st.rerun()
    with c2:
        if st.button('개요 확정', type='primary', width='stretch'):
            changed = _apply(knowledge)
            state.set_knowledge(knowledge)
            state.put(state.KEY_FLASH,
                      '캠페인 개요를 확정했어요' + (' (수정 반영)' if changed else ''))
            st.rerun()
