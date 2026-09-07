# -*- coding: utf-8 -*-
"""
글로벌 셸 — 상단 바 · 텍스트 로고 · 이탈 방지 · 세션 칩

2026.09.07 신설. 좌측 사이드바를 없애면서 사이드바가 지고 있던 두 가지
(세션 정보 / 파기 버튼)를 상단 바로 옮겼다. 화면 폭을 온전히 콘텐츠에
쓰기 위한 정리이며, 기능은 하나도 줄이지 않는다.

  ┌──────────────────────────────────────────────────────────┐
  │ AFTER CAMPAIGN        [캠페인명] [42분 후 파기] [종료]      │
  ├──────────────────────────────────────────────────────────┤
  │ ① 자료 올리기 ──── ② 내용 확인 ──── ③ 리포트 받기          │

이탈 방지
  좌상단 로고는 대문으로 가는 유일한 출구이며, 누르면 곧바로 이동하지 않고
  `st.dialog` 확인을 거친다. 파싱 결과와 AE 가 입력한 거시 검증 값은 전부
  세션 메모리에만 있어서(claude.md 4) 대문으로 나가면 되돌릴 수 없다.
  `step1_upload.py` 가 이미 쓰는 것과 같은 다이얼로그 패턴이다.
"""

from typing import Callable, Optional, Sequence

import streamlit as st

from dashboard import state, theme_css as T

SITE_NAME = 'AFTER CAMPAIGN'
ORG_NAME = '비즈니스 3본부 AX'


def _esc(s) -> str:
    return (str(s if s is not None else '')
            .replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


# ═══════════════════════════ 이탈 방지 다이얼로그

@st.dialog('대문으로 돌아갈까요?')
def _confirm_home(on_confirm: Callable[[], None]) -> None:
    """
    작업 소실을 알리고 확인을 받는다.

    `on_confirm` 은 진입점마다 다르다 (app.py 는 단계 초기화, web_main.py 는
    대문 라우팅). 셸이 호출부의 상태 키를 몰라도 되도록 콜백으로 받는다.
    """
    st.markdown(
        '작업 중인 내용이 사라질 수 있어요.<br>'
        '올린 자료와 확인하신 값은 저장되지 않아요.',
        unsafe_allow_html=True)
    T.spacer(6)
    c1, c2 = st.columns(2)
    with c1:
        if st.button('아니요', width='stretch', key='ax_home_no'):
            st.rerun()
    with c2:
        if st.button('네, 이동할게요', type='primary', width='stretch',
                     key='ax_home_yes'):
            on_confirm()


# ═══════════════════════════ 상단 바

def topbar(on_home: Callable[[], None], *,
           campaign: str = '',
           session_note: str = '',
           on_destroy: Optional[Callable[[], None]] = None) -> None:
    """
    상단 바를 그린다.

    Args:
        on_home: 대문 이동 확정 시 실행할 콜백 (다이얼로그 통과 후)
        campaign: 우측에 표시할 현재 캠페인명
        session_note: 세션 만료 안내 등 한 줄 (서버 배포에서만 씀)
        on_destroy: [종료] 버튼 콜백. None 이면 버튼을 만들지 않는다.
    """
    cols = st.columns([3, 5, 2] if on_destroy else [3, 7])

    with cols[0]:
        # 로고는 버튼이다 — 링크가 아니라 버튼이라야 이탈 방지 다이얼로그를
        # 띄울 수 있다. 텍스트 로고로 보이게 하는 CSS 는 위젯 key 로 붙는
        # `.st-key-ax_logo_btn` 을 잡는다 (theme_css).
        if st.button(SITE_NAME, key='ax_logo_btn'):
            _confirm_home(on_home)

    with cols[1]:
        bits = []
        if campaign:
            bits.append(f'<span class="ax-chip strong">{_esc(campaign)}</span>')
        if session_note:
            bits.append(f'<span class="ax-chip">{_esc(session_note)}</span>')
        st.markdown(f'<div class="ax-topmeta">{"".join(bits)}</div>',
                    unsafe_allow_html=True)

    if on_destroy:
        with cols[2]:
            if st.button('종료', key='ax_destroy_btn', width='stretch'):
                on_destroy()

    st.markdown('<div class="ax-topline"></div>', unsafe_allow_html=True)


def steps(labels: Sequence[str], current: int) -> None:
    """진행 단계 — theme_css 의 stepper 를 그대로 쓴다."""
    T.steps(labels, current)


def page_title(title: str, sub: str = '') -> None:
    """
    본문 최상단 제목. 상단 바가 브랜드를 맡으므로 여기는 '지금 할 일'만 쓴다.
    """
    st.markdown(
        f'<h2 class="ax-h">{_esc(title)}</h2>'
        + (f'<p class="ax-hsub">{_esc(sub)}</p>' if sub else ''),
        unsafe_allow_html=True)
