# -*- coding: utf-8 -*-
"""
웹 UI 디자인 테마 — 'AFTER CAMPAIGN' 컨셉 B (광고 트렌디 · '성적표')

2026.09.07 전면 개편 (3차)
  토스+삼성블루 테마를 폐기하고, 확정 방향인 컨셉 B로 재설계했다.
  규격의 단일 소스는 프로젝트 루트의 design.md / design-system.css 이며,
  이 파일은 그 토큰·컴포넌트를 Streamlit 화면에 이식한 것이다.

설계 언어 — 에디토리얼 / 네오브루탈
  · 크림 페이퍼 + 잉크(near-black) + 소수의 강한 액센트(코발트·코랄·라임).
  · 두꺼운 2px 잉크 보더 + 하드 오프셋 섀도(블러 0)로 종이 위에 얹힌 느낌.
  · 큰 타이포가 주인공. 헤드라인은 Black Han Sans, 숫자는 Bricolage.
  · 강조색은 기능에 묶는다: 코발트=실집행/확정, 코랄=액션·경고, 라임=긍정.
  · 모션은 120 / 200 / 320ms. 이모지 금지. 아이콘은 Lucide 인라인 SVG.
  · UI 카피는 해요체. 숫자는 tabular-nums.

호환 유지
  공개 함수 시그니처(inject/inject_right_drawer/header/steps/grade/table/
  remark/note/seal/spacer)와 charts.py 가 참조하는 색 상수 이름
  (BRAND/BRAND_LIGHT/GREY_*/TEXT/TEXT_HI/TEXT_SOFT/TEXT_DIM)은 유지하고
  값만 컨셉 B로 매핑했다. 호출부 20여 곳을 건드리지 않기 위함이다.

🔴 적용 범위 — 이 모듈은 **웹 화면에만** 적용된다. 산출물 PPTX 디자인은
   utils/report/theme.py 가 전담하며 두 시스템은 물리적으로 분리한다.

🔴 폰트 — Google Fonts 등 외부 웹폰트 CDN 금지(claude.md 1 = 외부 요청 금지).
   @font-face 는 local() 만 쓰므로 네트워크 요청이 없다. 컨셉 B 서체가
   미설치면 스택의 다음 폰트로 조용히 강등된다. 서체를 확실히 렌더하려면
   Black Han Sans / Bricolage Grotesque / Gothic A1 을 base64 data: URI 로
   임베드할 것(단일 소스, 네트워크 없음).
"""

from typing import Optional, Sequence

import streamlit as st

# ─────────────────────────── 팔레트 (컨셉 B)
INK = '#17140F'            # 본문·제목·보더 기본. 순수 검정 대신 웜 잉크
PAPER = '#F3EEE4'          # 페이지 바닥(크림)
PAPER_2 = '#F8F4EC'        # 입력/드롭존 등 살짝 밝은 면

BRAND = '#2B2BF5'          # 코발트 · 주 강조 · 실집행 · 확정
BRAND_HOVER = '#2222D6'
BRAND_PRESS = '#1A1AA6'
BRAND_LIGHT = '#6A6AF8'    # 보조 강조 (차트 2계열)
BRAND_100 = '#D5D5FE'      # 약 보더
BRAND_WEAK = '#ECECFF'     # 약 배경

CORAL = '#FF5A38'          # 액션(CTA) · 경고·아쉬움
LIME = '#C6F24E'           # 긍정·하이라이트 (항상 잉크 텍스트)
VIOLET = '#8B7CF6'         # 보조 계열 (매체 구분)
AMBER = '#FFB84D'          # 보조 계열 · 주의

# 그레이 램프 — 잉크 기반 웜 뉴트럴 (charts.py 가 이 이름들을 참조한다)
GREY_900 = INK
GREY_800 = '#2E2A24'
GREY_700 = '#4D4842'       # 보조 텍스트
GREY_600 = '#6E695F'       # 캡션
GREY_500 = '#8A8578'
GREY_400 = '#A7A192'       # 비활성 텍스트
GREY_300 = '#DAD3C4'       # 계획 막대 채움 / 옅은 면
GREY_200 = '#CFC7B6'       # 차트 축·도메인
GREY_150 = '#E4DED0'       # 차트 그리드(옅게)
GREY_100 = '#EDE7DA'
GREY_50 = '#F3EEE4'        # 페이지 바닥(=PAPER)
WHITE = '#FFFFFF'

OK = '#2E7D32'             # 가독용 그린 텍스트(등급 배지는 라임 사용)
WARN = '#B45309'
WARN_FILL = AMBER
BAD = '#C4321F'

# 하위 호환 별칭 — charts.py 등 기존 호출부가 이 이름으로 참조한다
TEXT = INK
TEXT_HI = INK
TEXT_SOFT = GREY_700
TEXT_DIM = GREY_600
BG_DEEP = PAPER
BG_MID = PAPER
BG_SOFT = PAPER
SURFACE = PAPER
SURFACE_HI = PAPER_2
LINE = INK
LINE_SOFT = GREY_150
GOLD = BRAND
GOLD_HI = BRAND_HOVER

# ─────────────────────────── 지오메트리 · 모션 (컨셉 B)
R_S, R_M, R_L, R_XL, R_2XL, R_3XL = '10px', '14px', '18px', '22px', '22px', '24px'
R_FULL = '999px'
EASE = 'cubic-bezier(.22,.61,.36,1)'
DUR_FAST, DUR_BASE, DUR_SLOW = '120ms', '200ms', '320ms'

# 두꺼운 잉크 보더 + 하드 오프셋 섀도(블러 0) — 컨셉 B 의 핵심
BORDER = f'2px solid {INK}'
SHADOW_1 = f'4px 4px 0 {INK}'
SHADOW_2 = f'6px 6px 0 {INK}'
SHADOW_3 = f'8px 8px 0 {INK}'
RING = 'rgba(43,43,245,.20)'   # 포커스 링(코발트)

# ─────────────────────────── 폰트 (local() 만 — 네트워크 요청 없음)
FONT_FACES = """
@font-face{font-family:'AX Head';src:local('Black Han Sans');font-weight:400;font-display:swap}
@font-face{font-family:'AX Disp';src:local('Bricolage Grotesque');font-weight:500 800;font-display:swap}
@font-face{font-family:'AX Body';src:local('Gothic A1');font-weight:400 900;font-display:swap}
"""

SANS_KR = ('"AX Body", "Gothic A1", "Pretendard", "Noto Sans KR", '
           '"Malgun Gothic", "맑은 고딕", -apple-system, system-ui, sans-serif')
HEAD_KR = ('"AX Head", "AX Body", "Gothic A1", "Black Han Sans", '
           '"Malgun Gothic", "맑은 고딕", -apple-system, system-ui, sans-serif')
DISP = ('"AX Disp", "Bricolage Grotesque", ui-monospace, '
        '"Malgun Gothic", system-ui, monospace')

BASE_PX = 16


def _tokens() -> str:
    """CSS 커스텀 프로퍼티 — 모든 규칙이 이 변수만 참조한다."""
    return f"""
  :root {{
    --ax-ink:{INK}; --ax-paper:{PAPER}; --ax-paper-2:{PAPER_2};
    --ax-brand:{BRAND}; --ax-brand-hover:{BRAND_HOVER}; --ax-brand-press:{BRAND_PRESS};
    --ax-brand-weak:{BRAND_WEAK}; --ax-brand-100:{BRAND_100}; --ax-brand-light:{BRAND_LIGHT};
    --ax-coral:{CORAL}; --ax-lime:{LIME}; --ax-violet:{VIOLET}; --ax-amber:{AMBER};
    --ax-fg:{INK}; --ax-fg-2:{GREY_700}; --ax-fg-3:{GREY_600}; --ax-fg-disabled:{GREY_400};
    --ax-line:{INK}; --ax-line-10:rgba(23,20,15,.10); --ax-line-30:rgba(23,20,15,.30);
    --ax-ok:{OK}; --ax-warn:{WARN}; --ax-warn-fill:{WARN_FILL}; --ax-bad:{BAD};
    --ax-r-s:{R_S}; --ax-r-m:{R_M}; --ax-r-l:{R_L}; --ax-r-xl:{R_XL}; --ax-r-2xl:{R_2XL}; --ax-r-full:{R_FULL};
    --ax-bd:{BORDER}; --ax-bd-dash:3px dashed {INK};
    --ax-sh-1:{SHADOW_1}; --ax-sh-2:{SHADOW_2}; --ax-sh-3:{SHADOW_3};
    --ax-ring:{RING};
    --ax-ease:{EASE}; --ax-dur:{DUR_BASE}; --ax-dur-fast:{DUR_FAST}; --ax-dur-slow:{DUR_SLOW};
    --ax-body:{SANS_KR}; --ax-head:{HEAD_KR}; --ax-disp:{DISP};
  }}
"""


# ─────────────────────────── 작업 화면 CSS (var(--ax-*) 만 참조 — plain 문자열)
_BASE_CSS = """
  /* ── 캔버스 ── */
  .stApp { background: var(--ax-paper); }
  .block-container { padding-top: 1.6rem; padding-bottom: 5rem; max-width: 1180px; }
  header[data-testid="stHeader"] { background: transparent; }
  #MainMenu, footer { visibility: hidden; }

  html, body, .stApp { font-size: 16px; }
  html, body, .stApp, .stMarkdown, p, span, div, label, li {
      font-family: var(--ax-body); color: var(--ax-fg); letter-spacing: -.005em;
      word-break: keep-all; overflow-wrap: anywhere;
  }
  .stApp p, .stApp li, .stApp span, .stApp div, .stApp label,
  .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5 {
      word-break: keep-all !important; overflow-wrap: anywhere !important;
  }
  .kbr { display: inline-block; }
  .ax-lead { font-size: .96rem; color: var(--ax-fg-2); margin: 0 0 14px; line-height: 1.6; font-weight: 600; }
  .ax-lead.sm { font-size: .86rem; margin-top: 8px; }
  .stMarkdown, label { font-size: 16px; line-height: 1.6; }
  [class^="rc-"] span, [class*=" rc-"] span,
  [class^="ax-"] span, [class*=" ax-"] span,
  h1 span, h2 span, h3 span, h4 span, h5 span {
      font-size: inherit; font-weight: inherit; line-height: inherit; letter-spacing: inherit;
  }
  h1, h2, h3, h4, h5 { font-family: var(--ax-head); color: var(--ax-fg); font-weight: 400; letter-spacing: -.01em; }
  h1 { font-size: 1.9rem; line-height: 1.05; }
  h2 { font-size: 1.55rem; line-height: 1.1; }
  h3 { font-size: 1.3rem; line-height: 1.15; }
  h4, h5 { font-size: 1.08rem; line-height: 1.35; }
  a { color: var(--ax-brand); text-decoration: none; font-weight: 700; }
  a:hover { text-decoration: underline; text-underline-offset: 3px; }
  hr { border: 0; border-top: 2px solid var(--ax-line-10); margin: 1.4rem 0; }
  /* 숫자는 자릿수 고정 */
  .ax-num, td.num, [data-testid="stMetricValue"] {
      font-family: var(--ax-disp); font-variant-numeric: tabular-nums; font-feature-settings: "tnum" 1;
  }

  /* ── 상단 바 ── */
  .rc-card { margin: 0 0 22px; }
  .rc-topbar { display: flex; align-items: baseline; gap: 12px; padding: 0 0 14px; border-bottom: var(--ax-bd); }
  .rc-title { font-family: var(--ax-head); font-size: 1.55rem; letter-spacing: -.01em; color: var(--ax-fg); margin: 0; white-space: nowrap; }
  .rc-title .dot { color: var(--ax-brand); }
  .rc-sub { font-size: .9rem; color: var(--ax-fg-3); font-weight: 700; margin: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .rc-meta { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 16px; }
  .rc-meta > div { flex: 1 1 160px; background: var(--ax-paper); border: var(--ax-bd); border-radius: var(--ax-r-m); box-shadow: var(--ax-sh-1); padding: 12px 15px; }
  .rc-meta .k { font-size: .74rem; font-weight: 800; color: var(--ax-fg-3); margin-bottom: 3px; }
  .rc-meta .v { font-size: 1rem; font-weight: 800; color: var(--ax-fg); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

  /* ── 진행 단계 (스텝퍼) ── */
  .rc-steps { display: flex; align-items: center; gap: 0; margin: 4px 0 28px; }
  .rc-steps .st { display: flex; align-items: center; gap: 9px; flex: 0 0 auto; opacity: .4; }
  .rc-steps .bul { width: 28px; height: 28px; border-radius: var(--ax-r-full); display: inline-flex; align-items: center; justify-content: center;
      font-family: var(--ax-disp); font-size: .82rem; font-weight: 800; flex: 0 0 auto; background: var(--ax-paper-2); color: var(--ax-fg); border: var(--ax-bd); }
  .rc-steps .lb { font-family: var(--ax-head); font-size: .98rem; color: var(--ax-fg); white-space: nowrap; }
  .rc-steps .bar { flex: 1 1 auto; height: 2px; background: var(--ax-line-30); margin: 0 14px; min-width: 18px; }
  .rc-steps .on { opacity: 1; }
  .rc-steps .on .bul { background: var(--ax-brand); border-color: var(--ax-ink); color: #fff; }
  .rc-steps .done { opacity: 1; }
  .rc-steps .done .bul { background: var(--ax-lime); border-color: var(--ax-ink); color: var(--ax-ink); }

  /* ── 표 ── */
  table.rc-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: .95rem; background: var(--ax-paper);
      border: var(--ax-bd); border-radius: var(--ax-r-m); overflow: hidden; margin: 4px 0 10px; box-shadow: var(--ax-sh-1); }
  table.rc-table th, table.rc-table td { border-bottom: 2px solid var(--ax-line-10); padding: 12px 15px; color: var(--ax-fg); text-align: left; }
  table.rc-table tr:last-child td { border-bottom: 0; }
  table.rc-table th { font-family: var(--ax-head); color: var(--ax-fg); font-size: .86rem; }
  table.rc-table td.num { text-align: right; font-family: var(--ax-disp); font-variant-numeric: tabular-nums; }
  table.rc-table tr.total td { background: var(--ax-lime); font-weight: 800; color: var(--ax-ink); }

  /* ── 달성률 등급 배지 (색 + 라벨 병기) ── */
  .rc-grade { display: inline-flex; align-items: center; min-width: 3.4rem; justify-content: center; padding: 4px 11px;
      border: var(--ax-bd); border-radius: var(--ax-r-s); font-size: .82rem; font-weight: 800; }
  .g-su, .g-woo { background: var(--ax-lime); color: var(--ax-ink); }
  .g-mi, .g-yang { background: var(--ax-amber); color: var(--ax-ink); }
  .g-ga { background: var(--ax-coral); color: #fff; }
  .g-na { background: var(--ax-paper-2); color: var(--ax-fg-3); }

  /* ── 인사이트 / Lesson Learned ── */
  .rc-remark { background: var(--ax-brand); color: #fff; border: var(--ax-bd); border-radius: var(--ax-r-xl);
      box-shadow: var(--ax-sh-2); padding: 18px 22px; margin: 12px 0 16px; line-height: 1.7; }
  .rc-remark .h { font-family: var(--ax-head); font-size: 1.2rem; color: #fff; margin-bottom: 8px; }

  /* ── 한 줄 안내 ── */
  .rc-note { display: flex; gap: 10px; align-items: flex-start; border: var(--ax-bd); border-radius: var(--ax-r-m);
      padding: 13px 16px; margin: 8px 0; font-size: .93rem; font-weight: 700; color: var(--ax-ink); line-height: 1.55; background: var(--ax-amber); }
  .rc-note::before { content: ""; flex: 0 0 auto; width: 8px; height: 8px; margin-top: 8px; border-radius: var(--ax-r-full); background: var(--ax-ink); }
  .rc-note.ok { background: var(--ax-lime); }
  .rc-note.err { background: var(--ax-coral); color: #fff; }
  .rc-note.err::before { background: #fff; }

  /* ── 완료 배지 ── */
  .rc-seal { display: inline-flex; align-items: center; gap: 8px; padding: 9px 17px; border-radius: var(--ax-r-full);
      background: var(--ax-lime); color: var(--ax-ink); border: var(--ax-bd); box-shadow: var(--ax-sh-1); font-family: var(--ax-head); font-size: .96rem; }
  .rc-seal::before { content: "✓"; font-weight: 800; }

  /* ═══ Streamlit 위젯 ═══ */

  /* 버튼 — secondary(기본) = 페이퍼 + 잉크 보더, primary = 코랄 채움 */
  .stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
      border-radius: var(--ax-r-m); border: var(--ax-bd); background: var(--ax-paper); color: var(--ax-ink);
      font-family: var(--ax-body); font-weight: 700; font-size: .97rem; padding: 11px 18px; min-height: 46px; box-shadow: none;
      transition: box-shadow var(--ax-dur) var(--ax-ease), transform var(--ax-dur) var(--ax-ease); }
  .stButton > button:hover, .stDownloadButton > button:hover, .stFormSubmitButton > button:hover {
      background: var(--ax-paper); color: var(--ax-ink); box-shadow: var(--ax-sh-1); }
  .stButton > button:active { transform: translate(2px,2px); box-shadow: none; }
  .stButton > button:focus:not(:active), .stDownloadButton > button:focus:not(:active) {
      color: var(--ax-ink); box-shadow: 0 0 0 3px var(--ax-ring); }

  /* 코랄 채움 버튼 = 흰 글씨 + 볼드 (자식까지 지정 — Streamlit 이 라벨을 <p>/<div> 로 감싼다) */
  .stButton > button[kind="primary"], .stButton > button[kind="primary"] *,
  .stDownloadButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] *,
  .stFormSubmitButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] *,
  .st-key-ax_final_export button, .st-key-ax_final_export button *,
  .st-key-ax_final_dl button, .st-key-ax_final_dl button * {
      color: #FFFFFF !important; font-weight: 700 !important; }
  .stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
      background: var(--ax-coral); border: var(--ax-bd); border-radius: var(--ax-r-l);
      font-family: var(--ax-head); font-size: 1.06rem; padding: 15px 26px; min-height: 54px; box-shadow: var(--ax-sh-2); }
  .stButton > button[kind="primary"]:hover, .stDownloadButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primary"]:hover {
      background: var(--ax-coral); box-shadow: var(--ax-sh-3); }
  .stButton > button[kind="primary"]:active { transform: translate(3px,3px); box-shadow: var(--ax-sh-1); }
  .stButton > button:disabled, .stButton > button:disabled:hover, .stDownloadButton > button:disabled { opacity: .3; box-shadow: none; transform: none; }
  .stButton > button[kind="primary"]:disabled { background: var(--ax-coral); opacity: .3; }

  /* 업로드 드롭존 — 대시 잉크 보더 + 페이퍼2 */
  [data-testid="stFileUploaderDropzone"] { border: var(--ax-bd-dash); background: var(--ax-paper-2); border-radius: var(--ax-r-xl); padding: 34px 24px;
      transition: box-shadow var(--ax-dur) var(--ax-ease); }
  [data-testid="stFileUploaderDropzone"]:hover { box-shadow: var(--ax-sh-1); }
  [data-testid="stFileUploaderDropzone"] * { color: var(--ax-fg-2); font-weight: 700; }
  [data-testid="stFileUploaderDropzone"] button { background: var(--ax-paper); border: var(--ax-bd); border-radius: var(--ax-r-m); color: var(--ax-ink); font-weight: 700; }
  [data-testid="stFileUploaderFile"] { background: var(--ax-paper); border: var(--ax-bd); border-radius: var(--ax-r-m); padding: 9px 12px; margin-top: 6px; }

  /* 입력 — 페이퍼2 + 2px 잉크 보더, 포커스 코발트 */
  .stTextInput input, .stTextArea textarea, .stNumberInput input, .stDateInput input, div[data-baseweb="select"] > div {
      background: var(--ax-paper-2) !important; color: var(--ax-ink) !important; border: var(--ax-bd) !important;
      border-radius: var(--ax-r-m) !important; font-size: .98rem !important; font-family: var(--ax-body) !important; font-weight: 600; min-height: 48px;
      transition: border-color var(--ax-dur) var(--ax-ease), box-shadow var(--ax-dur) var(--ax-ease); }
  .stTextInput input:focus, .stTextArea textarea:focus, .stNumberInput input:focus, div[data-baseweb="select"] > div:focus-within {
      background: var(--ax-paper-2) !important; border-color: var(--ax-brand) !important; box-shadow: 0 0 0 3px var(--ax-ring) !important; }
  .stTextInput input::placeholder, .stTextArea textarea::placeholder { color: var(--ax-fg-disabled) !important; }
  .stTextInput label, .stTextArea label, .stSelectbox label, .stMultiSelect label, .stToggle label,
  .stNumberInput label, .stRadio label, .stCheckbox label, .stSlider label, .stDateInput label {
      color: var(--ax-fg) !important; font-family: var(--ax-head) !important; font-size: .9rem !important; font-weight: 400 !important; }
  div[data-baseweb="popover"] li:hover { background: var(--ax-brand-weak) !important; }

  /* 토글 · 체크박스 on = 코발트 */
  [data-testid="stToggle"] div[aria-checked="true"], div[data-baseweb="checkbox"] span[data-checked="true"] {
      background-color: var(--ax-brand) !important; border-color: var(--ax-ink) !important; }

  /* 확장 패널 */
  div[data-testid="stExpander"] { border: var(--ax-bd); border-radius: var(--ax-r-m); background: var(--ax-paper); overflow: hidden; margin: 8px 0; box-shadow: var(--ax-sh-1); }
  div[data-testid="stExpander"] summary { font-family: var(--ax-head); font-size: .98rem; color: var(--ax-fg); padding: 13px 16px; }

  /* 진행바 · 지표 */
  .stProgress > div > div > div { background-color: var(--ax-brand); border-radius: var(--ax-r-full); }
  .stProgress > div > div { background-color: var(--ax-paper-2); border: var(--ax-bd); border-radius: var(--ax-r-full); }
  [data-testid="stMetric"] { background: var(--ax-paper); border: var(--ax-bd); border-radius: var(--ax-r-l); box-shadow: var(--ax-sh-1); padding: 16px 18px; }
  [data-testid="stMetricValue"] { color: var(--ax-fg); font-family: var(--ax-disp); font-size: 1.55rem; font-weight: 800; letter-spacing: -.03em; }
  [data-testid="stMetricLabel"] { color: var(--ax-fg-3); font-family: var(--ax-head); font-size: .86rem; }
  [data-testid="stMetricDelta"] { font-size: .84rem; font-weight: 700; }

  /* 알림류 */
  div[data-testid="stAlert"] { background: var(--ax-paper); border: var(--ax-bd); border-radius: var(--ax-r-m); color: var(--ax-fg); box-shadow: var(--ax-sh-1); }

  /* 탭 — 코발트 언더라인 */
  button[data-baseweb="tab"] { font-family: var(--ax-head); font-size: .98rem; color: var(--ax-fg-3); }
  button[data-baseweb="tab"][aria-selected="true"] { color: var(--ax-fg); }
  div[data-baseweb="tab-highlight"] { background-color: var(--ax-brand); height: 3px; }
  div[data-baseweb="tab-border"] { background-color: var(--ax-line-10); }

  /* 데이터프레임 · 코드 */
  [data-testid="stDataFrame"] { border: var(--ax-bd); border-radius: var(--ax-r-m); overflow: hidden; }
  .stCode, pre { background: var(--ax-paper-2) !important; border: var(--ax-bd); border-radius: var(--ax-r-m); }

  /* 사이드바 전면 제거 (상단 바 체제) */
  section[data-testid="stSidebar"], [data-testid="stSidebarCollapseButton"],
  [data-testid="collapsedControl"], [data-testid="stSidebarCollapsedControl"] { display: none !important; }

  /* 상단 바 로고 · 칩 */
  .ax-topline { height: 2px; background: var(--ax-line); margin: 2px 0 22px; }
  .st-key-ax_logo_btn button { background: transparent !important; border: 0 !important; padding: 4px 0 !important; min-height: 0 !important;
      font-family: var(--ax-disp); font-weight: 800; font-size: 1.2rem; letter-spacing: -.02em; color: var(--ax-ink) !important; text-align: left; width: auto !important;
      box-shadow: none !important; }
  .st-key-ax_logo_btn button:hover { background: transparent !important; color: var(--ax-brand) !important; box-shadow: none !important; transform: none !important; }
  .ax-topmeta { display: flex; align-items: center; justify-content: flex-end; gap: 8px; flex-wrap: wrap; min-height: 38px; }
  .ax-chip { display: inline-block; padding: 6px 13px; border-radius: var(--ax-r-full); background: var(--ax-paper); color: var(--ax-fg-2); border: var(--ax-bd); font-size: .83rem; font-weight: 700; white-space: nowrap; }
  .ax-chip.strong { background: var(--ax-brand); color: #fff; max-width: 22rem; overflow: hidden; text-overflow: ellipsis; }
  .ax-topact { height: 0; }

  /* 본문 제목 */
  .ax-h { font-family: var(--ax-head); font-size: 1.75rem; letter-spacing: -.01em; margin: 6px 0 6px; color: var(--ax-fg); }
  .ax-hsub { font-size: .96rem; color: var(--ax-fg-3); font-weight: 600; margin: 0 0 18px; max-width: 46rem; }

  /* 슬라이드 썸네일 */
  .ax-thumb { padding: 8px; border-radius: var(--ax-r-m); border: 2px solid transparent; background: transparent; transition: box-shadow var(--ax-dur-fast) var(--ax-ease); }
  .ax-thumb:hover { background: var(--ax-paper-2); }
  .ax-thumb.on { border: var(--ax-bd); box-shadow: var(--ax-sh-1); background: var(--ax-paper-2); }
  .ax-thumb-cap { font-family: var(--ax-head); font-size: .84rem; color: var(--ax-fg-2); margin-top: 7px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .ax-thumb.on .ax-thumb-cap { color: var(--ax-brand-press); }

  /* 올린 파일 칩 */
  .ax-files { display: flex; flex-wrap: wrap; gap: 8px; margin: 4px 0 6px; }
  .ax-file { display: inline-flex; align-items: center; gap: 8px; padding: 8px 14px; border-radius: var(--ax-r-full); background: var(--ax-paper); border: var(--ax-bd); font-size: .86rem; font-weight: 700; color: var(--ax-fg-2); max-width: 100%; }
  .ax-file .sz { color: var(--ax-fg-3); font-family: var(--ax-disp); font-size: .8rem; font-variant-numeric: tabular-nums; flex: 0 0 auto; }

  /* 최종 추출 버튼 — 화면에서 가장 강한 한 곳 */
  .st-key-ax_final_export button, .st-key-ax_final_dl button {
      background: var(--ax-coral) !important; color: #fff !important; border: var(--ax-bd) !important; border-radius: var(--ax-r-l) !important;
      min-height: 62px !important; font-family: var(--ax-head) !important; font-size: 1.2rem !important; box-shadow: var(--ax-sh-2) !important; }
  .st-key-ax_final_export button:hover, .st-key-ax_final_dl button:hover { background: var(--ax-coral) !important; box-shadow: var(--ax-sh-3) !important; }

  /* 문안 수정 패널 */
  .af-panel { background: var(--ax-paper-2); border: var(--ax-bd); border-radius: var(--ax-r-xl); box-shadow: var(--ax-sh-2); padding: 20px; position: sticky; top: 12px; }
  .af-drawer-title { font-family: var(--ax-head); font-size: 1.2rem; color: var(--ax-fg); border-bottom: var(--ax-bd); padding-bottom: 12px; margin-bottom: 8px; }
  .af-chip { display: inline-block; margin: 3px 5px 3px 0; padding: 6px 12px; border: var(--ax-bd); border-radius: var(--ax-r-full); font-size: .8rem; font-weight: 700; color: var(--ax-fg-2); line-height: 1.4; background: var(--ax-paper); }
  .af-chip:hover { color: var(--ax-brand); }
  .af-sub { font-family: var(--ax-head); font-size: .86rem; color: var(--ax-fg-3); margin: 14px 0 6px; }
  .af-empty { border: var(--ax-bd-dash); border-radius: var(--ax-r-m); padding: 15px 16px; margin: 8px 0 12px; font-size: .89rem; font-weight: 600; color: var(--ax-fg-3); line-height: 1.7; }
"""


def inject() -> None:
    """작업 화면 테마 CSS 를 주입한다. 페이지당 1회 호출."""
    st.markdown(f"<style>{FONT_FACES}{_tokens()}{_BASE_CSS}</style>",
                unsafe_allow_html=True)


def inject_right_drawer() -> None:
    """
    (호환용) 문안 수정 패널 스타일은 inject() 가 함께 내보낸다.
    호출부를 건드리지 않기 위해 빈 채로 남긴다.
    """
    return


# ═══════════════════════════ 대문 (Landing)
# web_main.py 와 Scripts/test_dashboard.py 가 이 상수들을 가져다 쓴다.

_LANDING_BASE = """
  .stApp { background: var(--ax-paper); }
  .block-container { padding-top: 0 !important; max-width: 1100px; }
  header[data-testid="stHeader"] { background: transparent; }
  #MainMenu, footer { visibility: hidden; }

  html, body, .stApp { font-size: 16px; }
  html, body, .stApp, .stMarkdown, p, span, div, label {
      font-family: var(--ax-body); color: var(--ax-fg); letter-spacing: -.005em; word-break: keep-all; overflow-wrap: anywhere; }
  .stApp p, .stApp li, .stApp span, .stApp div, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5 {
      word-break: keep-all !important; overflow-wrap: anywhere !important; }
  .kbr { display: inline-block; }
  [class^="after-"] span, [class*=" after-"] span, h1 span, h2 span, h3 span, h4 span {
      font-size: inherit; font-weight: inherit; line-height: inherit; letter-spacing: inherit; }

  @keyframes afterFade { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }
  .fade { animation: afterFade var(--ax-dur-slow) var(--ax-ease) both; }
  .d1 { animation-delay: .02s; } .d2 { animation-delay: .08s; } .d3 { animation-delay: .14s; }
  .d4 { animation-delay: .20s; } .d5 { animation-delay: .26s; }

  .after-hero { text-align: center; padding: 0; min-height: 48vh; display: flex; flex-direction: column; align-items: center; justify-content: center; }
  .after-hero > * { margin-left: auto; margin-right: auto; }
  .after-badge { display: inline-block; margin-bottom: 22px; padding: 8px 16px; border: var(--ax-bd); border-radius: var(--ax-r-full);
      background: var(--ax-paper); color: var(--ax-ink); font-family: var(--ax-disp); font-size: .8rem; font-weight: 700; letter-spacing: .16em; text-transform: uppercase; }
  .after-title { font-family: var(--ax-head); font-size: clamp(3rem, 8vw, 5.6rem); line-height: .98; letter-spacing: -.02em; color: var(--ax-fg); margin: 0 0 1.1rem; }
  .after-title .accent { color: var(--ax-brand); }
  .stApp .after-lead { max-width: 660px; margin: 0 auto 1rem; font-size: 1.24rem; line-height: 1.6; font-weight: 700; color: var(--ax-fg); letter-spacing: -.01em; }
  .stApp .after-body { max-width: 640px; margin: 0 auto; font-size: 1rem; line-height: 1.75; font-weight: 600; color: var(--ax-fg-2); }

  div[data-testid="stButton"] button[kind="primary"], div[data-testid="stButton"] button[kind="primary"] * { color: #FFFFFF !important; font-weight: 700 !important; }
  div[data-testid="stButton"] button[kind="primary"] { width: 100%; background: var(--ax-coral); border: var(--ax-bd); border-radius: var(--ax-r-l);
      padding: 17px 24px; font-family: var(--ax-head); font-size: 1.2rem; min-height: 60px; box-shadow: var(--ax-sh-2);
      transition: box-shadow var(--ax-dur) var(--ax-ease), transform var(--ax-dur) var(--ax-ease); }
  div[data-testid="stButton"] button[kind="primary"]:hover { background: var(--ax-coral); box-shadow: var(--ax-sh-3); }
  div[data-testid="stButton"] button[kind="primary"]:active { transform: translate(3px,3px); box-shadow: var(--ax-sh-1); }

  .after-notice { text-align: center; font-size: .86rem; font-weight: 700; color: var(--ax-fg-3); margin: 1.3rem 0 4rem; }
"""

LANDING_CSS = f"<style>{FONT_FACES}{_tokens()}{_LANDING_BASE}</style>"

HERO_HTML = """
<div class="after-hero">
  <div class="after-badge fade d1">비즈니스 3본부 AX</div>
  <h1 class="after-title fade d1">AFTER <span class="accent">CAMPAIGN</span></h1>
  <p class="after-lead fade d2">
    <span class="kbr">흩어진 캠페인 자료를 올리면,</span>
    <span class="kbr">결과 리포트를 대신 만들어 드려요.</span>
  </p>
  <p class="after-body fade d3">
    <span class="kbr">제안서부터 온에어 소재까지 수개월치 기록을 한곳에 모아,</span><br>
    <span class="kbr">제안 목표와 실집행 실적을 대조하고</span>
    <span class="kbr">다음 캠페인 전략까지 정리해 드려요.</span>
  </p>
</div>
"""

# ═══════════════════════════ 컴포넌트

def _esc(s) -> str:
    """HTML 이스케이프 — 캠페인명·매체명이 그대로 마크업에 들어가므로 필수"""
    return (str(s if s is not None else '')
            .replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def _tighten(title: str) -> str:
    """
    'A F T E R' / '캠 페 인 성 적 표' 처럼 낱자를 띄운 제목을 붙여 준다.
    새 테마는 자간을 좁히므로 여기서 정규화한다. 모든 토큰이 한 글자일 때만 붙인다.
    """
    parts = title.split()
    if len(parts) > 1 and all(len(p) == 1 for p in parts):
        return ''.join(parts)
    return title


def header(title: str, subtitle: str = '', meta: Optional[Sequence] = None) -> None:
    """페이지 상단 바 — 제목 + 부제 + 메타 카드"""
    cells = ''.join(
        f'<div><div class="k">{_esc(k).replace(" ", "")}</div>'
        f'<div class="v">{_esc(v) or "—"}</div></div>'
        for k, v in (meta or []))
    st.markdown(
        f'<div class="rc-card">'
        f'<div class="rc-topbar">'
        f'<div class="rc-title">{_esc(_tighten(title))}<span class="dot">.</span></div>'
        f'<div class="rc-sub">{_esc(subtitle)}</div>'
        f'</div>'
        f'{f"<div class=rc-meta>{cells}</div>" if cells else ""}'
        f'</div>', unsafe_allow_html=True)


def steps(labels: Sequence[str], current: int) -> None:
    """진행 단계 — 1-based current. 완료 단계는 체크로 바뀐다."""
    out = []
    for i, label in enumerate(labels, 1):
        cls = 'on' if i == current else ('done' if i < current else 'todo')
        # '1. 파일 업로드' → 번호는 불릿이 표시하므로 라벨에서 뗀다
        text = label.split('.', 1)[-1].strip() if '.' in label[:3] else label
        bullet = '✓' if i < current else str(i)
        if i > 1:
            out.append('<div class="bar"></div>')
        out.append(f'<div class="st {cls}">'
                   f'<span class="bul">{bullet}</span>'
                   f'<span class="lb">{_esc(text)}</span></div>')
    st.markdown(f'<div class="rc-steps">{"".join(out)}</div>',
                unsafe_allow_html=True)


# 달성률 → 표기 등급. 경계값은 표기용이며 데이터를 바꾸지 않는다.
_GRADES = ((1.20, '초과 달성', 'g-su'), (1.00, '달성', 'g-woo'),
           (0.85, '근접', 'g-mi'), (0.70, '미달', 'g-yang'))


def grade(rate: Optional[float]) -> str:
    """
    달성률(1.0 = 100%)을 등급 배지 HTML 로.
    데이터가 없으면 '—' 로 두고 추측하지 않는다 (claude.md 3.3).
    """
    if rate is None:
        return '<span class="rc-grade g-na">—</span>'
    for cut, label, cls in _GRADES:
        if rate >= cut:
            return f'<span class="rc-grade {cls}">{label}</span>'
    return '<span class="rc-grade g-ga">부진</span>'


def table(header_row: Sequence[str], rows: Sequence[Sequence],
          *, total_row: bool = False) -> None:
    """표. 셀이 dict 면 {'t': 값, 'num': True, 'html': True}"""
    def cell(c, tag='td'):
        if isinstance(c, dict):
            text = c['t'] if c.get('html') else _esc(c.get('t'))
            klass = ' class="num"' if c.get('num') else ''
            return f'<{tag}{klass}>{text}</{tag}>'
        return f'<{tag}>{_esc(c)}</{tag}>'

    head = ''.join(cell(h, 'th') for h in header_row)
    body = []
    for i, r in enumerate(rows):
        last = total_row and i == len(rows) - 1
        body.append(f'<tr class="total">{"".join(cell(c) for c in r)}</tr>'
                    if last else f'<tr>{"".join(cell(c) for c in r)}</tr>')
    st.markdown(
        f'<table class="rc-table"><thead><tr>{head}</tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table>', unsafe_allow_html=True)


def remark(title: str, lines: Sequence[str]) -> None:
    """인사이트 / Lesson Learned 블록"""
    if not lines:
        return
    body = '<br>'.join(_esc(x) for x in lines)
    st.markdown(
        f'<div class="rc-remark"><div class="h">{_esc(title)}</div>'
        f'{body}</div>', unsafe_allow_html=True)


def note(text: str, level: str = 'warn') -> None:
    """한 줄 안내 — level: ok | warn | err"""
    cls = {'ok': 'ok', 'error': 'err', 'err': 'err'}.get(level, 'warn')
    st.markdown(f'<div class="rc-note {cls}">{_esc(text)}</div>',
                unsafe_allow_html=True)


def seal(lines: Sequence[str] = ('확인 완료',)) -> None:
    """완료 배지"""
    st.markdown(
        f'<div class="rc-seal">{" · ".join(_esc(x) for x in lines)}</div>',
        unsafe_allow_html=True)


def spacer(px: int) -> None:
    """수직 여백"""
    st.markdown(f'<div style="height:{px}px"></div>', unsafe_allow_html=True)
