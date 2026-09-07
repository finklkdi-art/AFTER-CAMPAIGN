# -*- coding: utf-8 -*-
"""
AFTER 대문 + Stage 1.5 UI 목업 — 파싱 없이 화면 조작감만 확인하는 독립 실행 스크립트

목적
  기획자가 브라우저에서 실제 상호작용 흐름(대문 → 교정 → 비교 → 경고 → 제출)을
  체험해 보고 UX 감을 잡기 위한 것이다. 실제 파서·모델·API 호출은 일절
  하지 않으며, 데이터는 전부 이 파일 안에 하드코딩되어 있다.

화면 구성
  ax_entered = False → [화면 1] AFTER 대문 (다크 블루)
  ax_entered = True  → [화면 2] 성적표 대시보드 (Stage 1.5 거시 검증)

  대문의 CSS·마크업은 실제 `web_main.py` 의 것을 그대로 가져다 쓴다
  (import 실패 시에만 축약본으로 대체). 목업과 실물이 어긋나면 테스트의
  의미가 없기 때문이다.

실행
  프로젝트 루트에서:
      streamlit run Scripts/test_dashboard.py

  다른 위치에서:
      streamlit run "C:/Users/CHEIL/desktop/ax3bb/Scripts/test_dashboard.py"

  브라우저가 자동으로 열리지 않으면 터미널에 뜨는 http://localhost:8501 을
  직접 여세요.
"""

import sys
from copy import deepcopy
from pathlib import Path

import pandas as pd
import streamlit as st

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
for _p in (str(_HERE), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# 실제 프로젝트의 '성적표' 테마가 옆에 있으면 그대로 얹고, 없어도 동작한다.
# (이 파일은 파서·데이터 계층 어떤 것도 임포트하지 않음)
try:
    from dashboard import theme_css as T           # 프로젝트 안에서 실행할 때
    HAS_THEME = True
except Exception:
    HAS_THEME = False

# 대문은 실물(web_main.py)의 CSS·마크업을 그대로 재사용해 목업의 충실도를 맞춘다.
try:
    from dashboard.theme_css import LANDING_CSS, HERO_HTML, PILLARS
    HAS_LANDING = True
except Exception:
    HAS_LANDING = False
    LANDING_CSS = """
<style>
  .stApp { background: linear-gradient(175deg,#0B1220 0%,#101A2C 55%,#141E33 100%); }
  .block-container { padding-top: 0 !important; max-width: 1180px; }
  header[data-testid="stHeader"] { background: transparent; }
  html, body, .stApp, .stMarkdown, p, span, div, label {
      font-family: 'Pretendard','Noto Sans KR','Malgun Gothic',system-ui,sans-serif;
      color: #C9D3E4; }
  @keyframes afterFade { from{opacity:0;transform:translateY(14px);} to{opacity:1;transform:none;} }
  .fade { animation: afterFade .9s ease-out both; }
  .d1{animation-delay:.05s;} .d2{animation-delay:.20s;} .d3{animation-delay:.35s;}
  .d4{animation-delay:.50s;} .d5{animation-delay:.65s;}
  .after-hero { text-align:center; padding:13vh 0 0; }
  .after-title { font-size:clamp(3.4rem,12vw,9rem); line-height:1.02;
      letter-spacing:.34em; text-indent:.34em; font-weight:200;
      color:#F2F5FA; margin:0 0 .6rem; }
  .after-tagline { font-style:italic; font-size:clamp(.95rem,1.7vw,1.22rem);
      letter-spacing:.1em; color:#C9A227; margin:0; }
  .after-rule { width:64px; height:1px; margin:2.6rem auto 2.2rem;
      background:rgba(201,162,39,.55); border:0; }
  .after-lead { max-width:720px; margin:0 auto 1.1rem; font-size:1.06rem;
      line-height:1.95; color:#DCE4F0; }
  .after-body { max-width:720px; margin:0 auto; font-size:.95rem;
      line-height:1.95; color:#94A2BA; }
  .after-card { background:rgba(255,255,255,.04);
      border:1px solid rgba(201,162,39,.22); border-radius:2px;
      padding:30px 26px 28px; min-height:238px;
      transition:transform .25s ease,border-color .25s ease; }
  .after-card:hover { transform:translateY(-3px); border-color:rgba(201,162,39,.62); }
  .after-card .ico { font-size:2.1rem; line-height:1; }
  .after-card .no { font-size:.68rem; letter-spacing:.2em;
      color:rgba(201,162,39,.75); margin:14px 0 6px; }
  .after-card h4 { font-size:1.04rem; font-weight:500; letter-spacing:.04em;
      color:#EDF1F8; margin:0 0 10px; }
  .after-card p { font-size:.85rem; line-height:1.75; color:#8B98AD; margin:0; }
  div[data-testid="stButton"] button[kind="primary"] {
      width:100%; background:transparent; color:#E8C55A;
      border:1px solid rgba(201,162,39,.75); border-radius:2px;
      padding:16px 22px; font-size:1rem; font-weight:500;
      letter-spacing:.12em; transition:background .25s ease,color .25s ease; }
  div[data-testid="stButton"] button[kind="primary"]:hover,
  div[data-testid="stButton"] button[kind="primary"]:focus:not(:active) {
      background:#C9A227; color:#0B1220; border-color:#C9A227; }
  .after-notice { text-align:center; font-size:.78rem; color:#6E7C93;
      letter-spacing:.03em; margin:1.5rem 0 4rem; }
</style>
"""
    HERO_HTML = """
<div class="after-hero">
  <h1 class="after-title fade d1">A F T E R</h1>
  <p class="after-tagline fade d2">Campaign intelligence, after the campaign.</p>
  <hr class="after-rule fade d3">
  <p class="after-lead fade d3">
    캠페인은 종료되었지만, 우리의 인사이트는 이제 시작됩니다.
  </p>
  <p class="after-body fade d4">
    AFTER는 단순한 성과 측정 도구가 아닙니다. 수개월간 흩어져 있던 기획과 실행의
    기록을 한눈에 아카이빙하고, 다음 캠페인의 성공을 위한 &lsquo;건설적인 차기
    전략 로드맵&rsquo;을 제시하는 지식 자산화 솔루션입니다.
  </p>
</div>
"""
    PILLARS = [
        ('📁', '01', 'Campaign Archiving',
         '제안서부터 온에어 소재까지, 수개월간 흩어져 있던 커뮤니케이션 '
         '히스토리를 기간 · 매체 · 소재 축으로 한데 모아 자산화함.'),
        ('🧠', '02', 'Fact-based Intelligence',
         '제안 목표와 실집행 실적을 교차 대조하여, 데이터와 맥락에 근거한 '
         'Lesson Learned 를 출처와 함께 도출함.'),
        ('🧭', '03', 'Strategic Roadmap',
         '도출된 인사이트를 바탕으로 차기 미디어 · 크리에이티브 운용의 '
         '최적화 방향성을 로드맵으로 제시함.'),
    ]


# ═══════════════════════════ Mock Campaign Knowledge
# 파서가 이미 뽑아 놓은 상태를 흉내낸다.
# 일부러 대소문자·오타·매체 누락을 심어 놓아 교정감을 확인할 수 있게 했다.

MOCK_KNOWLEDGE = {
    'campaign_name': 'Bespoke AI 무풍콤보 런칭',
    'product_name': 'bespoke ai 무풍콤보',        # 소문자 — 대문자로 고칠 대상
    'category': '에어컨',
    'advertiser': '삼성전자',
    'campaign_period': '2025.04.21 ~ 2025.07.19',
    'kpi_standard': '50% VTR',
    'creative_list': '가로형 영상 1건, 배너 2건',
    'kpi_rows': [
        {'지표': '노출 (Impression)', '단위': '회',
         '제안서 목표': '180,000,000', '포스트바이 실적': '187,592,431',
         '달성률': '104.2%'},
        {'지표': '조회 (View)',       '단위': '회',
         '제안서 목표': '90,000,000',  '포스트바이 실적': '93,215,880',
         '달성률': '103.6%'},
        {'지표': '클릭 (Click)',      '단위': '회',
         '제안서 목표': '2,500,000',   '포스트바이 실적': '2,187,443',
         '달성률': '87.5%'},
        {'지표': 'VTR',               '단위': '%',
         '제안서 목표': '50.0',        '포스트바이 실적': '49.7',
         '달성률': '99.4%'},
        {'지표': 'CPV',               '단위': '원',
         '제안서 목표': '5.30',        '포스트바이 실적': '5.11',
         '달성률': '103.6%'},
    ],
    'checklist_items': [
        ('warning', "제안서에 명시된 '카카오 비즈보드' 매체가 "
                    '포스트바이 리포트에서 발견되지 않음'),
        ('warning', "'클릭' 지표 달성률 87.5% — 목표 대비 하회. "
                    '원인 분석과 코멘트 필요'),
        ('info', '제안서 소재 리스트(가로형 1 · 배너 2)와 실집행 소재 표기가 '
                 '일치함'),
        ('error', '데일리리포트 3일치(6/12, 6/17, 6/21) 실적이 0으로 기록됨 — '
                  '집행 정지였는지 리포팅 누락인지 확인 필요'),
    ],
}


# ═══════════════════════════ 화면 1 — AFTER 대문

KEY_ENTERED = 'ax_entered'


def _spacer(px: int) -> None:
    st.markdown(f'<div style="height:{px}px"></div>', unsafe_allow_html=True)


def render_landing() -> None:
    """다크 블루 대문. 성적표 CSS 는 여기서 주입하지 않는다 (조건부 주입)."""
    st.markdown(LANDING_CSS, unsafe_allow_html=True)
    st.markdown(HERO_HTML, unsafe_allow_html=True)

    _spacer(56)

    for col, (ico, no, title, desc) in zip(st.columns(3, gap='medium'), PILLARS):
        with col:
            st.markdown(f"""
<div class="after-card fade d5">
  <div class="ico">{ico}</div>
  <div class="no">{no}</div>
  <h4>{title}</h4>
  <p>{desc}</p>
</div>
""", unsafe_allow_html=True)

    _spacer(64)

    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        if st.button('캠페인 지식화 시작하기 (Upload)  ➔',
                     type='primary', key='mock_cta'):
            st.session_state[KEY_ENTERED] = True
            st.rerun()

    st.markdown(
        '<p class="after-notice">※ 업로드된 자료는 세션 종료 시 '
        '서버에서 즉시 파기됩니다. &nbsp;·&nbsp; 본 화면은 UI 목업입니다.</p>',
        unsafe_allow_html=True)


# ═══════════════════════════ 화면 2 — 성적표 대시보드

def inject_light_theme_fallback() -> None:
    """프로젝트 테마가 없는 환경에서도 최소한의 결을 잡아 준다"""
    st.markdown(
        '<style>'
        '.block-container{max-width:1080px;padding-top:1.4rem;}'
        'h1,h2,h3{letter-spacing:.02em;}'
        '</style>', unsafe_allow_html=True)


def render_meta_form(k: dict) -> dict:
    st.subheader('1. 메타데이터 교정')
    st.caption('파서가 뽑은 초안입니다. 잘못된 표기를 직접 고치세요.')

    c1, c2 = st.columns(2)
    with c1:
        campaign_name = st.text_input(
            '캠페인명', value=k['campaign_name'],
            help='보고서 표지와 파일명에 그대로 쓰입니다.')
        product_name = st.text_input(
            '제품명', value=k['product_name'],
            help='소문자로 뽑혀 있음 — 브랜드 표기 규정에 맞춰 대소문자 교정')
        category = st.text_input('품목', value=k['category'])
    with c2:
        advertiser = st.text_input('광고주', value=k['advertiser'])
        campaign_period = st.text_input('집행 기간', value=k['campaign_period'])
        kpi_standard = st.text_input('KPI 기준', value=k['kpi_standard'])

    creative_list = st.text_area(
        '소재 리스트', value=k['creative_list'], height=68,
        help='쉼표로 구분. 형식은 자유입니다.')

    return {
        'campaign_name': campaign_name, 'product_name': product_name,
        'category': category, 'advertiser': advertiser,
        'campaign_period': campaign_period, 'kpi_standard': kpi_standard,
        'creative_list': creative_list,
    }


def render_kpi_table(rows: list) -> None:
    st.subheader('2. 제안서 vs 포스트바이 대조')
    st.caption('숫자 데이터는 표시만 되며 이 화면에서는 편집하지 않습니다.')
    df = pd.DataFrame(rows)
    st.dataframe(df, width='stretch', hide_index=True)


def render_checklist(items: list) -> None:
    st.subheader('3. Checklist — 사람이 확인할 항목')
    st.caption('최종 PPT 1페이지에 그대로 실릴 목록입니다.')
    for severity, message in items:
        if severity == 'error':
            st.error(f'❌ {message}')
        elif severity == 'warning':
            st.warning(f'⚠️ {message}')
        else:
            st.info(f'ℹ️ {message}')


def render_submit(original: dict, edited: dict) -> None:
    st.subheader('4. 제출')
    left, right = st.columns([1, 2])
    with left:
        submitted = st.button('수정 완료 · 리포트 만들기',
                              type='primary', width='stretch')
    with right:
        st.caption('이 화면은 목업이므로 실제로 저장되는 파일은 없습니다.')

    if not submitted:
        return

    diff = {k: (original[k], edited[k])
            for k in edited if original.get(k) != edited[k]}
    if diff:
        st.success(f'교정된 데이터가 저장되었습니다. — 변경 {len(diff)}건')
        with st.expander('변경 내역', expanded=True):
            for k, (before, after) in diff.items():
                st.markdown(f'**{k}**')
                st.code(f'- {before}\n+ {after}', language='diff')
    else:
        st.success('교정된 데이터가 저장되었습니다. (변경 없음)')


# ═══════════════════════════ 진입점

def render_dashboard() -> None:
    """Stage 1.5 거시 검증 화면 (목업)"""
    if HAS_THEME:
        T.inject()
        T.header('정 보 확 인 (목업)',
                 'Stage 1.5 UI 조작감 확인용 — 실제 데이터 아님',
                 meta=[('캠 페 인', MOCK_KNOWLEDGE['campaign_name']),
                       ('광 고 주', MOCK_KNOWLEDGE['advertiser']),
                       ('품    목', MOCK_KNOWLEDGE['category']),
                       ('기    간', MOCK_KNOWLEDGE['campaign_period'])])
    else:
        inject_light_theme_fallback()
        st.title('🧪 Stage 1.5 UI 목업')
        st.caption('실제 파서·저장 로직은 연결되지 않은 조작감 테스트 화면')

    top, back = st.columns([4, 1])
    with top:
        st.info('데이터는 전부 이 파일 내부에 하드코딩되어 있습니다. '
                'Ctrl+C 로 종료 후 스크립트 상단의 `MOCK_KNOWLEDGE` 딕셔너리를 '
                '바꿔 다른 상황도 만들어 볼 수 있습니다.')
    with back:
        _spacer(6)
        if st.button('← 대문으로', width='stretch', key='mock_back'):
            st.session_state[KEY_ENTERED] = False
            st.rerun()

    original = deepcopy(MOCK_KNOWLEDGE)
    edited = render_meta_form(MOCK_KNOWLEDGE)
    st.divider()
    render_kpi_table(MOCK_KNOWLEDGE['kpi_rows'])
    st.divider()
    render_checklist(MOCK_KNOWLEDGE['checklist_items'])
    st.divider()
    render_submit(original, edited)


# ═══════════════════════════ 진입점 (라우터)

def main() -> None:
    st.set_page_config(
        page_title='AFTER — UI 목업', page_icon='🧭', layout='wide',
        initial_sidebar_state='collapsed')

    if KEY_ENTERED not in st.session_state:
        st.session_state[KEY_ENTERED] = False

    # 테마 배타 주입 — 대문(다크)과 성적표(밝은 갱지)는 절대 겹치지 않는다
    if st.session_state[KEY_ENTERED]:
        render_dashboard()
    else:
        render_landing()


if __name__ == '__main__':
    main()
