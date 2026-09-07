# -*- coding: utf-8 -*-
"""
글로벌 셸 — 상단 바 · 텍스트 로고 · 이탈 방지 · 세션 칩

2026.09.07 신설. 좌측 사이드바를 없애면서 화면 폭을 온전히 콘텐츠에 쓴다.

  ┌──────────────────────────────────────────────────────────┐
  │ AFTER CAMPAIGN                              [캠페인명]     │
  ├──────────────────────────────────────────────────────────┤
  │ ① 자료 올리기 ──── ② 내용 확인 ──── ③ 리포트 받기          │

상단 바에서 덜어낸 것 (2026.09.07 2차)
  '00분 후 자동 파기' 칩과 [종료] 버튼을 걷어냈다. 남은 시간을 초 단위로
  세어 보여 주는 것은 안심이 아니라 압박이고, [종료]는 로고와 출구가 겹쳐
  둘 중 무엇을 눌러야 하는지 되레 헷갈렸다. 파기 기능 자체는 사라지지 않고
  로고 → 확인 다이얼로그 동선에 합쳐졌다.

이탈 방지
  좌상단 로고는 대문으로 가는 유일한 출구이며, 누르면 곧바로 이동하지 않고
  `st.dialog` 확인을 거친다. 파싱 결과와 AE 가 입력한 거시 검증 값은 전부
  세션 메모리에만 있어서(claude.md 4) 대문으로 나가면 되돌릴 수 없다.
  `step1_upload.py` 가 이미 쓰는 것과 같은 다이얼로그 패턴이다.
"""

from typing import Callable, Sequence

import streamlit as st

from dashboard import state, theme_css as T

SITE_NAME = 'AFTER CAMPAIGN'
ORG_NAME = '비즈니스 3본부 AX'

# 버튼 라벨은 Streamlit 마크다운을 타므로 `:blue[…]` 로 두 번째 낱말만 강조할 수
# 있다. 실제 색은 Streamlit 기본 파랑이 아니라 theme_css 의 코발트로 덮는다.
LOGO_LABEL = 'AFTER :blue[CAMPAIGN]'


def _esc(s) -> str:
    return (str(s if s is not None else '')
            .replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


# ═══════════════════════════ 이탈 방지 다이얼로그

@st.dialog('대문으로 돌아갈까요?')
def _confirm_home(on_confirm: Callable[[], None]) -> None:
    """
    작업 소실을 알리고 확인을 받는다.

    `on_confirm` 은 진입점마다 다르다 (app.py 는 단계 초기화, web_main.py 는
    세션 파기 후 대문 라우팅). 셸이 호출부의 상태 키를 몰라도 되도록 콜백으로 받는다.
    """
    st.markdown('<span class="kbr">올린 자료와 확인하신 값이 모두 사라져요.</span>',
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

def topbar(on_home: Callable[[], None], *, campaign: str = '') -> None:
    """
    상단 바를 그린다 — 워드마크와 현재 캠페인명, 그 둘뿐이다.

    2026.09.07 정리. [종료] 버튼과 '00분 후 자동 파기' 칩을 걷어냈다.
    출구가 로고 하나로 모이면서 파기도 그 동선에 붙는다 — 대문으로 나가는
    확인을 통과하면 호출부(`on_home`)가 샌드박스를 통째로 지우므로,
    즉시 전량 삭제 수단은 그대로 남아 있다 (claude.md 1.2).

    Args:
        on_home: 대문 이동 확정 시 실행할 콜백 (다이얼로그 통과 후)
        campaign: 우측에 표시할 현재 캠페인명
    """
    cols = st.columns([3, 7])

    with cols[0]:
        # 로고는 버튼이다 — 링크가 아니라 버튼이라야 이탈 방지 다이얼로그를
        # 띄울 수 있다. 텍스트 로고로 보이게 하는 CSS 는 위젯 key 로 붙는
        # `.st-key-ax_logo_btn` 을 잡는다 (theme_css).
        if st.button(LOGO_LABEL, key='ax_logo_btn'):
            _confirm_home(on_home)

    with cols[1]:
        chip = (f'<span class="ax-chip strong">{_esc(campaign)}</span>'
                if campaign else '')
        st.markdown(f'<div class="ax-topmeta">{chip}</div>',
                    unsafe_allow_html=True)

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
