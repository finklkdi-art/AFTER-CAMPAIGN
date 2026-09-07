# -*- coding: utf-8 -*-
"""
AFTER — Campaign intelligence, after the campaign.

외부 호스팅(Streamlit Community Cloud 등) 배포용 진입점.

    streamlit run web_main.py        # 로컬 확인
    # 배포: 이 파일을 메인 모듈로 지정, 키는 플랫폼 Secrets 에 등록

2026.09 배포 아키텍처 개편 — '100% 로컬 구동' 조항 해제. URL 로 즉시 체험하는
무료 호스팅 구조로 전환한다. 인증 게이트는 두지 않으며(진입 마찰 제거), 대신
세션 격리 + 완전 휘발성(Zero Retention) 으로 접속자 간 데이터 노출을 막는다.
API 키는 .env 대신 st.secrets 를 우선 사용한다.

`app.py`(1인 1PC 로컬 전용) 와 병렬로 존재하는 별도 진입점이며,
코어 엔진(`utils/` `models/` `ingest/` `data_scanning.py`)은 수정하지 않는다.
이 파일이 책임지는 것은 다음 넷뿐이다.

  1. 브랜드 대문(Landing) 렌더 및 `ax_entered` 라우팅
  2. 세션 격리 — 접속자마다 독립 샌드박스 루트를 만들어 하위 모듈에 주입
  3. 휘발성 보장 — 산출 PPTX 즉시 파기, 세션 TTL 만료 시 샌드박스 전체 파기
  4. 글로벌 셸(상단 바 · 이탈 방지) 배치

테마는 AFTER 라이트 · 삼성 블루로 통일되어 있으며, 화면별로 배타 주입한다.
  · 대문      → `T.LANDING_CSS`  (중앙 정렬 히어로)
  · 작업 화면 → `T.inject()`     (상단 바 · 3단계 진행 · 썸네일 · 수정 패널)
Streamlit 은 상호작용마다 스크립트를 재실행하므로, 분기 안에서만 주입하면
화면 전환 시 반대편 CSS 는 DOM 에서 자동으로 사라진다.

2026.09.07 — 좌측 사이드바를 제거했다. 세션 정보와 파기 버튼은 상단 바로
옮겼고(`dashboard/shell.py`), 문안 수정은 3단계 본문의 2단 레이아웃에서 한다.

외부 API(Claude·Gemini)는 챗봇·요약·이미지 품질을 위해 허용된다(claude.md 1 개정).
인증은 진입 마찰 제거를 위해 두지 않는다.
"""

import json
import shutil
import sys
import time
import uuid
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).parent
SCRIPTS_DIR = PROJECT_ROOT / 'Scripts'

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from dashboard import (                                      # noqa: E402
    state, theme_css as T, shell, step1_upload, step2_macro, step3_preview,
)

# ── 이 파일 전용 세션 키 (state.py 를 수정하지 않기 위해 분리) ──
KEY_ENTERED = 'ax_entered'        # False=대문 / True=작업 화면
KEY_TOKEN = 'ax_session_token'    # 샌드박스 식별자
KEY_BORN = 'ax_session_born'      # 세션 생성 시각 (TTL 계산)

# 단계 이름은 AE 가 '지금 뭘 하는지' 로 읽히게 둔다 (기능명이 아니라 행동).
STEPS = ['자료 올리기', '내용 확인하기', '리포트 받기']

# 운영 중 바뀔 값은 코드가 아니라 Config 에 둔다 (claude.md 1.1)
CONFIG_PATH = PROJECT_ROOT / 'Config' / 'web_deploy.json'
DEFAULT_CONFIG = {
    'session_ttl_minutes': 60,
    'purge_pptx_after_download': True,
    'link_input_folder': True,
}

CONFIG = dict(DEFAULT_CONFIG)


# ═══════════════════════════════════════════════════ 배포 설정

def load_config() -> dict:
    """배포 설정을 읽는다. 파일이 없거나 깨져도 기본값으로 계속 진행한다."""
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            cfg.update({k: v for k, v in loaded.items() if k in DEFAULT_CONFIG})
    except FileNotFoundError:
        pass
    except Exception as e:
        st.warning(f'배포 설정을 읽지 못해 기본값으로 진행해요: {e}')
    return cfg


# ═══════════════════════════════════════════════════ 세션 격리

SESSIONS_DIR = PROJECT_ROOT / 'Output' / 'Temp' / 'Sessions'


def issue_token() -> str:
    """
    세션 토큰을 발급하거나 복원한다.

    Streamlit 은 브라우저 새로고침 시 session_state 를 새로 만들기 때문에,
    토큰을 쿼리 파라미터에 실어 두어야 같은 샌드박스로 돌아올 수 있다.
    토큰은 uuid4 라 타임스탬프 방식과 달리 동시 접속자끼리 충돌하지 않는다.
    """
    token = st.session_state.get(KEY_TOKEN)
    if token:
        return token

    param = st.query_params.get('s')
    if isinstance(param, list):
        param = param[0] if param else None

    # 경로 조작 방지 — uuid4 hex 32자만 신뢰한다
    if isinstance(param, str) and len(param) == 32 and all(
            c in '0123456789abcdef' for c in param):
        token = param
    else:
        token = uuid.uuid4().hex
        st.query_params['s'] = token

    st.session_state[KEY_TOKEN] = token
    if KEY_BORN not in st.session_state:
        st.session_state[KEY_BORN] = time.time()
    return token


def sandbox_root(token: str) -> Path:
    """
    이 세션 전용 가짜 프로젝트 루트.

    하위 모듈(step1~3)의 디스크 쓰기는 전부 인자로 받은 `project_root` 에서
    파생되므로(업로드 작업 폴더 · 백업 스냅샷 · 산출 PPTX), 이 경로만 바꿔
    끼우면 모듈을 수정하지 않고도 접속자별로 완전히 격리된다.
    """
    root = SESSIONS_DIR / token
    try:
        (root / 'Output' / 'Temp').mkdir(parents=True, exist_ok=True)
    except OSError as e:
        st.error(f'세션 작업 폴더를 만들지 못했어요: {e}')
        st.stop()
    link_input(root)
    return root


def link_input(root: Path) -> None:
    """
    샌드박스 안에서도 `Input/` 캠페인 폴더를 고를 수 있도록 링크를 건다.

    Windows 에서 심볼릭 링크는 권한이 필요할 수 있다. 실패해도 조용히 넘어가며,
    그 경우 '캠페인 폴더 선택' 탭이 비어 보이고 업로드 경로만 쓰게 된다
    (서버 배포에서는 그쪽이 정상 동선이다).
    """
    if not CONFIG.get('link_input_folder', True):
        return
    link = root / 'Input'
    src = PROJECT_ROOT / 'Input'
    if not src.is_dir():
        return
    try:
        if link.exists():
            return
        link.symlink_to(src, target_is_directory=True)
    except (OSError, NotImplementedError):
        pass


def touch(root: Path) -> None:
    """세션 활동 시각을 갱신한다 (TTL 스윕의 기준)."""
    try:
        (root / '.alive').write_text(str(time.time()), encoding='utf-8')
    except OSError:
        pass


def sweep_expired(ttl_minutes: int) -> int:
    """
    TTL 이 지난 타 세션 샌드박스를 파기한다.

    매 재실행마다 돌지만 디렉터리 몇 개를 stat 하는 수준이라 부담이 없고,
    서버에 클라이언트 자산이 무기한 남는 것을 막는다 (claude.md 1).
    """
    if not SESSIONS_DIR.is_dir():
        return 0
    deadline = time.time() - max(ttl_minutes, 1) * 60
    mine = st.session_state.get(KEY_TOKEN)
    killed = 0
    for d in SESSIONS_DIR.iterdir():
        if not d.is_dir() or d.name == mine:
            continue
        try:
            alive = d / '.alive'
            seen = (float(alive.read_text(encoding='utf-8'))
                    if alive.is_file() else d.stat().st_mtime)
        except (OSError, ValueError):
            seen = 0.0
        if seen < deadline:
            shutil.rmtree(d, ignore_errors=True)
            killed += 1
    return killed


def purge_artifacts(root: Path) -> int:
    """
    샌드박스에 남은 산출 PPTX 를 파기한다.

    다운로드 버튼은 렌더 시점에 파일 바이트를 응답에 실어 보내므로,
    렌더가 끝난 직후 디스크 사본을 지워도 내려받기는 정상 동작한다.
    결과적으로 서버 하드디스크 잔존은 0 이 된다 (2026.09.05 결정).
    """
    if not root.is_dir():
        return 0
    n = 0
    for p in root.rglob('*.pptx'):
        try:
            p.unlink()
            n += 1
        except OSError:
            pass
    return n


def purge_uploads(root: Path) -> int:
    """
    업로드 원본을 파기한다 (완전 휘발성 — Zero Retention).

    3단계(리포트)에 이르면 파싱 결과는 이미 인메모리 knowledge/dataset 에 들어
    있어 원본 파일이 없어도 재렌더·부분 리렌더가 동작한다. 무료 서버에 클라이언트
    자산 원본이 남지 않도록 이 시점에 지운다. 세션 폴더 뼈대는 유지한다.
    """
    if not root.is_dir():
        return 0
    n = 0
    for sub in ('Output/Temp/Uploads', 'Output/Temp/Workspaces'):
        d = root / sub
        if d.is_dir():
            for p in d.rglob('*'):
                if p.is_file():
                    try:
                        p.unlink()
                        n += 1
                    except OSError:
                        pass
    return n


def destroy_session(root: Path) -> None:
    """샌드박스 전체를 즉시 파기하고 세션 상태를 비운다."""
    shutil.rmtree(root, ignore_errors=True)
    for key in [k for k in st.session_state.keys() if str(k).startswith('ax_')]:
        del st.session_state[key]
    try:
        st.query_params.clear()
    except Exception:
        pass


# ═══════════════════════════════════════════════════ 대문 — 라이트
# CSS·마크업의 단일 소스는 theme_css 다 (팔레트를 한곳에서만 정의)

def inject_landing_css() -> None:
    st.markdown(T.LANDING_CSS, unsafe_allow_html=True)


spacer = T.spacer


def render_landing() -> None:
    """브랜드 대문. 상단 바도 사이드바도 없이 이 화면만 그린다."""
    inject_landing_css()

    # 히어로는 한 덩어리로 내보낸다 — 쪼개면 Streamlit 이 래퍼 div 를 끼워
    # 넣어 중앙 정렬과 여백 리듬이 틀어진다.
    st.markdown(T.HERO_HTML, unsafe_allow_html=True)

    spacer(40)

    # 버튼은 히어로와 같은 축에 둔다. 가운데 칼럼을 좁게 잡아야 CTA 가
    # 배너처럼 퍼지지 않고 '누르는 것' 크기로 남는다.
    _, mid, _ = st.columns([1, 1.05, 1])
    with mid:
        if st.button('입장하기', type='primary', key='after_cta',
                     width='stretch'):
            st.session_state[KEY_ENTERED] = True
            state.init_state()
            st.rerun()

    # 각주다. 읽히되 주인공 자리를 뺏지 않도록 '*' 를 달아 작고 얇게 둔다.
    st.markdown(
        '<p class="after-notice">'
        '<span class="kbr">*올려주신 자료는 작업이 끝나면</span> '
        '<span class="kbr">서버에서 바로 지워져요.</span></p>',
        unsafe_allow_html=True)


# ═══════════════════════════════════════════════════ 작업 화면

def _leave(root: Path) -> None:
    """
    대문으로 돌아간다 (이탈 방지 다이얼로그를 통과한 뒤에만 호출).

    나가는 순간 샌드박스를 통째로 파기한다. 별도 [종료] 버튼을 없앤 뒤로
    이 동선이 '즉시 전량 삭제'를 맡는다 (claude.md 1.2). 다이얼로그가 이미
    자료가 사라진다고 알리고 확인을 받았으므로 여기서 다시 묻지 않는다.
    """
    destroy_session(root)
    st.session_state[KEY_ENTERED] = False
    st.rerun()


def render_workspace(root: Path) -> None:
    T.inject()

    knowledge = state.get_knowledge()

    shell.topbar(
        lambda: _leave(root),
        campaign=(knowledge.campaign_name if knowledge else ''),
    )
    shell.steps(STEPS, state.get_step())

    step = state.get_step()
    if step == 1:
        step1_upload.render(root)
    elif step == 2:
        step2_macro.render(root)
    elif step == 3:
        # 리포트 단계 진입 = 파싱 완료. 업로드 원본을 먼저 파기한다
        # (파싱 결과는 인메모리에 있어 재렌더에 지장 없음).
        if CONFIG.get('purge_uploads_after_report', True):
            purge_uploads(root)
        step3_preview.render(root)
        # 미리보기는 PPTX 가 아니라 SlideSpec 에서 직접 그리므로, 파일은
        # 최종 추출 때만 만들어지고 곧바로 지워도 된다. 내려받기 버튼에는
        # 렌더 시점에 바이트가 이미 실려 있어 다운로드는 정상 동작한다.
        if CONFIG.get('purge_pptx_after_download', True):
            purge_artifacts(root)
    else:
        state.goto_step(1)
        st.rerun()


# ═══════════════════════════════════════════════════ 진입점

def main() -> None:
    global CONFIG

    st.set_page_config(
        page_title='AFTER CAMPAIGN — 캠페인 결과 리포트 자동화',
        page_icon='📊',
        layout='wide',
        initial_sidebar_state='collapsed',   # 사이드바는 CSS 로 완전히 숨긴다
    )

    CONFIG = load_config()
    try:
        ttl = int(CONFIG.get('session_ttl_minutes') or 60)
    except (TypeError, ValueError):
        ttl = 60

    token = issue_token()
    root = sandbox_root(token)
    touch(root)
    sweep_expired(ttl)

    # .env 탐색(Claude API 키)은 실제 프로젝트 루트를 봐야 하므로 분리해 둔다.
    # 반면 디스크 쓰기 경로는 전부 샌드박스(root)로 간다.
    state.init_state()
    state.put(state.KEY_PROJECT_ROOT, PROJECT_ROOT)

    if not st.session_state.get(KEY_ENTERED, False):
        render_landing()
        return

    render_workspace(root)


if __name__ == '__main__':
    main()
