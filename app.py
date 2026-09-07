# -*- coding: utf-8 -*-
"""
광고 캠페인 결과 리포트 자동화 솔루션 - 로컬 웹 진입점

실행:
    streamlit run app.py

로컬(localhost) 구동을 전제로 하며, 외부 전송은 Rule Book 1.4의
Claude API 예외(AE 가 버튼을 눌러 실행하는 문안 수정)에 한정한다.
설정은 .streamlit/config.toml 참조.

웹 화면 디자인 테마는 'AFTER 라이트 · 삼성 블루'(Scripts/dashboard/theme_css.py)
이며, 산출물 PPTX 디자인(utils/report/theme.py)과는 무관하다.
구 '성적표(갱지)' 테마와 그 은유(학적/성적)는 2026.09 개편에서 폐기했다.
"""

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).parent
SCRIPTS_DIR = PROJECT_ROOT / 'Scripts'

# Scripts 패키지를 import 가능하도록 등록
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from dashboard import (                                      # noqa: E402
    state, theme_css, shell, step1_upload, step2_macro, step3_preview,
)

STEPS = ['자료 올리기', '내용 확인하기', '리포트 받기']


def _reset_all() -> None:
    """1단계로 되돌린다 (이탈 방지 다이얼로그를 통과한 뒤에만 호출)."""
    for key in [k for k in st.session_state.keys() if str(k).startswith('ax_')]:
        del st.session_state[key]
    state.init_state()
    state.goto_step(1)
    st.rerun()


def render_shell() -> None:
    """상단 바 + 진행 단계. 로컬 진입점이라 세션 파기 버튼은 두지 않는다."""
    knowledge = state.get_knowledge()
    shell.topbar(
        _reset_all,
        campaign=(knowledge.campaign_name if knowledge else ''),
        session_note='로컬 전용',
    )
    shell.steps(STEPS, state.get_step())


def main() -> None:
    st.set_page_config(
        page_title='AFTER — 캠페인 결과 리포트 자동화',
        page_icon='📊',
        layout='wide',
        initial_sidebar_state='collapsed',
    )

    state.init_state()
    state.put(state.KEY_PROJECT_ROOT, PROJECT_ROOT)
    theme_css.inject()
    render_shell()

    step = state.get_step()
    if step == 1:
        step1_upload.render(PROJECT_ROOT)
    elif step == 2:
        step2_macro.render(PROJECT_ROOT)
    elif step == 3:
        step3_preview.render(PROJECT_ROOT)
    else:
        state.goto_step(1)
        st.rerun()


if __name__ == '__main__':
    main()
