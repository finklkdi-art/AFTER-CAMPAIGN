# -*- coding: utf-8 -*-
"""
웹 UI 디자인 테마 — 'AFTER CAMPAIGN' 컨셉 C (Refined SaaS)

2026.09.07 전면 개편 (4차)
  컨셉 B(에디토리얼 · 네오브루탈)를 폐기하고 하이엔드 SaaS 언어로 재설계했다.
  개편 지시: "Apple / Linear / Notion 급으로, 요소가 서로 침범하지 않게,
  여백을 넉넉히, 글자를 키워 가독성을 높일 것."

왜 바꿨나 — 네오브루탈의 세 가지 장치가 화면을 시끄럽게 만들고 있었다.
  · `2px` 잉크 보더 + 블러 0 하드 섀도 → 모든 요소가 같은 목소리로 외침.
    위계가 안 생기니 어디를 봐야 할지 알 수 없다.
  · Black Han Sans 헤드 → 낱자 획이 굵어 한글 라벨이 뭉개져 보인다.
    스텝 라벨이 "너무 두껍다"는 피드백의 진짜 원인이 웨이트가 아니라 서체였다.
  · 앰버·라임 채움 알림 → 안내 한 건 한 건이 경고판처럼 보였다.

설계 언어 — Refined / Quiet Confidence
  · 웜 니어화이트 바닥 + 순백 카드. 면은 색이 아니라 **고도(elevation)**로 나눈다.
  · 보더는 `1px` 저대비(잉크 8%). 그림자는 넓고 옅게 두 겹.
  · 액센트는 코발트 **하나**. 넓게 칠하지 않고 점·선·작은 면에만 쓴다.
  · 서체는 Pretendard **한 종**. 위계는 크기·웨이트·색으로만 만든다.
  · 본문 17px / 행간 1.7. 한국어 가독성을 위해 기존보다 키웠다.
  · 모션 140 / 220 / 360ms, 표준 이징 하나. 이모지 금지.

호환 유지
  공개 함수(inject/inject_right_drawer/header/steps/grade/table/remark/note/
  seal/spacer)와 `charts.py` 가 참조하는 색 상수 이름
  (BRAND/BRAND_LIGHT/GREY_*/TEXT/TEXT_HI/TEXT_SOFT/TEXT_DIM)은 이름을 유지하고
  값만 컨셉 C로 매핑했다. 호출부 20여 곳을 건드리지 않기 위함이다.

🔴 적용 범위 — 이 모듈은 **웹 화면에만** 적용된다. 산출물 PPTX 디자인은
   utils/report/theme.py 가 전담하며 두 시스템은 물리적으로 분리한다.

🔴 폰트 — Pretendard 를 CDN 으로 받는다. 구 '외부 요청 금지' 조항은
   claude.md 1.0 개정으로 폐기됐고(외부 호스팅·외부 API 전면 허용), 폰트는
   사용자 데이터를 싣지 않는 정적 자산이라 1.5(최소 전송)와도 무관하다.
   CDN 이 죽어도 스택의 다음 서체로 조용히 강등된다.
"""

from typing import Optional, Sequence

import streamlit as st

# ─────────────────────────── 팔레트 (컨셉 C)
# 바닥은 순백이 아니라 웜 니어화이트다. 순백 페이지 위의 순백 카드는 구분이
# 안 되고, 화면 전체가 순백이면 장시간 작업에 눈이 부신다.
BG = '#FBFAF8'             # 페이지 바닥
SURFACE = '#FFFFFF'        # 카드 — 바닥보다 한 단 위
SURFACE_2 = '#F6F5F2'      # 인셋(입력·드롭존·코드) — 바닥보다 한 단 아래
SURFACE_3 = '#EEECE7'      # 더 깊은 인셋 · 트랙

INK = '#1A1917'            # 제목·본문. 순수 검정 대신 웜 잉크
FG_2 = '#56534D'           # 보조 텍스트
FG_3 = '#86827A'           # 캡션
FG_4 = '#ABA79E'           # 비활성

LINE = 'rgba(26,25,23,.08)'      # 기본 보더 — 있는 줄 모르게
LINE_2 = 'rgba(26,25,23,.14)'    # 강조 보더 · 구분선

BRAND = '#2B2BF5'          # 코발트 · 유일한 액센트 (브랜드 자산이라 유지)
BRAND_HOVER = '#2222D6'
BRAND_PRESS = '#1B1BAD'
BRAND_LIGHT = '#6E6EF9'    # 차트 2계열
BRAND_100 = '#D8D8FD'      # 약 보더
BRAND_WEAK = '#F1F1FF'     # 약 배경(틴트)

# 의미색 — 채도를 낮춰 '경고판'이 되지 않게 한다.
# 각 등급은 [글자색 · 배경 틴트 · 보더] 세 값을 한 벌로 갖는다.
OK, OK_BG, OK_BD = '#0E8A5F', '#F1FAF5', '#CDE9DC'
WARN, WARN_BG, WARN_BD = '#B26B00', '#FEFAF1', '#F0E3C6'
BAD, BAD_BG, BAD_BD = '#C2341D', '#FEF5F3', '#F5D7D0'

# 매체 구분 계열 (차트) — 코발트에서 시작해 명도·색상만 벌린다
CORAL = '#F0603C'
LIME = '#7BC94A'
VIOLET = '#8B7CF6'
AMBER = '#E8A33D'

# 그레이 램프 — 잉크 기반 웜 뉴트럴 (charts.py 가 이 이름들을 참조한다)
GREY_900 = INK
GREY_800 = '#33312C'
GREY_700 = FG_2
GREY_600 = FG_3
GREY_500 = '#9B978F'
GREY_400 = FG_4
GREY_300 = '#CFCBC2'       # 계획 막대 채움
GREY_200 = '#DEDBD4'       # 차트 축·도메인
GREY_150 = '#EFEDE8'       # 차트 그리드(옅게)
GREY_100 = SURFACE_2
GREY_50 = BG
WHITE = '#FFFFFF'

WARN_FILL = AMBER

# 드롭존 — 페이퍼보다 한 단 아래로 파인 면
DROP_BG = SURFACE_2
DROP_BD = '#D6D2CA'

# 하위 호환 별칭 — 기존 호출부가 이 이름으로 참조한다
PAPER = BG
PAPER_2 = SURFACE_2
TEXT = INK
TEXT_HI = INK
TEXT_SOFT = FG_2
TEXT_DIM = FG_3
BG_DEEP = BG
BG_MID = BG
BG_SOFT = BG
SURFACE_HI = SURFACE_2
LINE_SOFT = GREY_150
GOLD = BRAND
GOLD_HI = BRAND_HOVER

# ─────────────────────────── 지오메트리 · 모션
R_S, R_M, R_L, R_XL, R_2XL, R_3XL = '8px', '10px', '14px', '18px', '24px', '28px'
R_FULL = '999px'
EASE = 'cubic-bezier(.22,1,.36,1)'      # 부드럽게 안착하는 표준 이징
DUR_FAST, DUR_BASE, DUR_SLOW = '140ms', '220ms', '360ms'

BORDER = f'1px solid {LINE}'
# 그림자는 두 겹 — 가까운 한 겹으로 형태를, 먼 한 겹으로 깊이를 만든다
SHADOW_1 = '0 1px 2px rgba(26,25,23,.05)'
SHADOW_2 = ('0 1px 3px rgba(26,25,23,.05), '
            '0 8px 20px -8px rgba(26,25,23,.10)')
SHADOW_3 = ('0 2px 6px rgba(26,25,23,.06), '
            '0 20px 44px -14px rgba(26,25,23,.16)')
RING = 'rgba(43,43,245,.16)'

# ─────────────────────────── 폰트
# Pretendard 한 종으로 통일한다. 하이엔드 SaaS 는 서체를 섞지 않는다 —
# 위계는 크기·웨이트·색으로 만든다. dynamic-subset 은 쓰인 글자만 받아
# 초기 로딩이 가볍다.
FONT_FACES = """
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard-dynamic-subset.css');
"""

SANS_KR = ('Pretendard, "Pretendard Variable", -apple-system, '
           'BlinkMacSystemFont, system-ui, "Segoe UI", "Noto Sans KR", '
           '"Malgun Gothic", "맑은 고딕", sans-serif')
HEAD_KR = SANS_KR          # 서체 통일 — 별도 헤드 패밀리를 쓰지 않는다
DISP = SANS_KR             # 숫자는 서체가 아니라 tabular-nums 로 정렬한다

BASE_PX = 17


def _tokens() -> str:
    """CSS 커스텀 프로퍼티 — 모든 규칙이 이 변수만 참조한다."""
    return f"""
  :root {{
    --ax-bg:{BG}; --ax-surface:{SURFACE}; --ax-surface-2:{SURFACE_2}; --ax-surface-3:{SURFACE_3};
    --ax-ink:{INK}; --ax-fg:{INK}; --ax-fg-2:{FG_2}; --ax-fg-3:{FG_3}; --ax-fg-disabled:{FG_4};
    --ax-line:{LINE}; --ax-line-2:{LINE_2};
    --ax-brand:{BRAND}; --ax-brand-hover:{BRAND_HOVER}; --ax-brand-press:{BRAND_PRESS};
    --ax-brand-light:{BRAND_LIGHT}; --ax-brand-100:{BRAND_100}; --ax-brand-weak:{BRAND_WEAK};
    --ax-ok:{OK}; --ax-ok-bg:{OK_BG}; --ax-ok-bd:{OK_BD};
    --ax-warn:{WARN}; --ax-warn-bg:{WARN_BG}; --ax-warn-bd:{WARN_BD};
    --ax-bad:{BAD}; --ax-bad-bg:{BAD_BG}; --ax-bad-bd:{BAD_BD};
    --ax-coral:{CORAL}; --ax-lime:{LIME}; --ax-violet:{VIOLET}; --ax-amber:{AMBER};
    --ax-drop:{DROP_BG}; --ax-drop-bd:{DROP_BD};
    --ax-r-s:{R_S}; --ax-r-m:{R_M}; --ax-r-l:{R_L}; --ax-r-xl:{R_XL}; --ax-r-2xl:{R_2XL}; --ax-r-full:{R_FULL};
    --ax-bd:{BORDER};
    --ax-sh-1:{SHADOW_1}; --ax-sh-2:{SHADOW_2}; --ax-sh-3:{SHADOW_3};
    --ax-ring:{RING};
    --ax-ease:{EASE}; --ax-dur:{DUR_BASE}; --ax-dur-fast:{DUR_FAST}; --ax-dur-slow:{DUR_SLOW};
    --ax-body:{SANS_KR}; --ax-head:{HEAD_KR}; --ax-disp:{DISP};
    /* 간격 스케일 — 여백을 눈대중하지 않는다 */
    --ax-s1:4px; --ax-s2:8px; --ax-s3:12px; --ax-s4:16px; --ax-s5:24px;
    --ax-s6:32px; --ax-s7:48px; --ax-s8:64px; --ax-s9:96px;
  }}
"""


# ─────────────────────────── 작업 화면 CSS (var(--ax-*) 만 참조 — plain 문자열)
_BASE_CSS = """
  /* ══════════ 캔버스 ══════════
     바닥색은 html/body 에도 건다. `.stApp` 한 곳에만 걸면 앱 높이가 뷰포트보다
     짧을 때 아래·옆으로 브라우저 기본 회색이 비쳐 순간 화면이 깨져 보인다. */
  html, body, .stApp { background: var(--ax-bg); }
  .stApp { min-height: 100vh; }
  .block-container {
      padding-top: 30px !important; padding-bottom: 128px !important;
      max-width: 1080px;
  }
  header[data-testid="stHeader"] { background: transparent; height: 0; }
  #MainMenu, footer, [data-testid="stToolbar"] { visibility: hidden; }
  [data-testid="stDecoration"] { display: none; }

  /* ══════════ 타이포그래피 ══════════
     한국어는 어절이 붙어 있어 임의 지점에서 끊기면 의미 전달이 급격히
     나빠진다. keep-all 로 어절을 지키고, 절 경계는 `.kbr` 로 잡는다. */
  html, body, .stApp { font-size: 17px; }
  html, body, .stApp, .stMarkdown, p, span, div, label, li, td, th, input, textarea, button {
      font-family: var(--ax-body);
      -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale;
      color: var(--ax-fg); letter-spacing: -.011em;
      word-break: keep-all; overflow-wrap: break-word;
  }
  .stApp p, .stApp li, .stApp span, .stApp div, .stApp label, .stApp td, .stApp th,
  .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5 {
      word-break: keep-all !important; overflow-wrap: break-word !important;
  }
  .kbr { display: inline-block; }
  .stApp p { text-wrap: pretty; }

  /* Streamlit 이 emotion 클래스로 제목에 자기 서체(Source Sans)와 스케일을
     못박아 둔다. 맨 엘리먼트 선택자로는 특이도에서 밀리므로 `.stApp` 을
     앞에 붙여 확실히 이긴다. 이 한 줄이 빠지면 제목만 딴 서체로 뜬다. */
  .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5 {
      font-family: var(--ax-head) !important; color: var(--ax-fg);
      letter-spacing: -.026em; margin: 0;
  }
  .stApp h1 { font-size: 2.25rem; line-height: 1.22; font-weight: 800; }
  .stApp h2 { font-size: 1.75rem; line-height: 1.28; font-weight: 750; }
  .stApp h3 { font-size: 1.3125rem; line-height: 1.36; font-weight: 700; }
  .stApp h4 { font-size: 1.0625rem; line-height: 1.45; font-weight: 700; }
  .stApp h5 { font-size: .9375rem; line-height: 1.5; font-weight: 700; color: var(--ax-fg-2); }

  /* Streamlit 이 markdown 제목에 붙이는 기본 여백을 우리 스케일로 되잡는다 */
  .stMarkdown h3 { margin: 40px 0 10px; }
  .stMarkdown h4 { margin: 32px 0 8px; }
  .stMarkdown h5, .stMarkdown h6 { margin: 28px 0 8px; }
  .stMarkdown h3:first-child, .stMarkdown h4:first-child { margin-top: 4px; }

  .stMarkdown p, .stMarkdown li { font-size: 1rem; line-height: 1.7; color: var(--ax-fg-2); }
  [data-testid="stCaptionContainer"] p, .stCaption, small {
      font-size: .875rem !important; line-height: 1.65 !important;
      color: var(--ax-fg-3) !important; letter-spacing: -.006em;
  }
  .ax-lead {
      font-size: 1.0625rem; line-height: 1.72; color: var(--ax-fg-2);
      font-weight: 450; margin: 0 0 4px; max-width: 62ch;
  }
  .ax-lead.sm { font-size: .9375rem; margin-top: 12px; color: var(--ax-fg-3); }

  a { color: var(--ax-brand); text-decoration: none; font-weight: 600; }
  a:hover { text-decoration: underline; text-underline-offset: 3px; }
  hr, [data-testid="stDivider"] hr {
      border: 0; border-top: 1px solid var(--ax-line); margin: 52px 0 !important; }

  /* 숫자는 자릿수 고정 — 표·지표가 세로로 정렬돼야 비교가 된다 */
  .ax-num, td.num, [data-testid="stMetricValue"], .rc-steps .bul {
      font-variant-numeric: tabular-nums; font-feature-settings: "tnum" 1;
  }

  /* 중첩 span 이 부모 타이포를 깨지 않게 */
  [class^="rc-"] span, [class*=" rc-"] span,
  [class^="ax-"] span, [class*=" ax-"] span,
  [class^="af-"] span, [class*=" af-"] span,
  h1 span, h2 span, h3 span, h4 span, h5 span {
      font-size: inherit; font-weight: inherit; line-height: inherit; letter-spacing: inherit;
  }

  /* ══════════ 상단 바 ══════════ */
  .ax-topline { display: none; }
  .st-key-ax_logo_btn button {
      background: transparent !important; border: 0 !important;
      padding: 0 !important; min-height: 0 !important; height: auto !important;
      width: auto !important; box-shadow: none !important;
      color: var(--ax-ink) !important; text-align: left;
      transition: opacity var(--ax-dur-fast) var(--ax-ease);
  }
  .st-key-ax_logo_btn button * {
      font-family: var(--ax-head) !important;
      font-size: 1.25rem !important; font-weight: 800 !important;
      line-height: 1.2 !important; letter-spacing: -.03em !important;
  }
  .st-key-ax_logo_btn button p span { color: var(--ax-brand) !important; }
  .st-key-ax_logo_btn button:hover { opacity: .62; background: transparent !important;
      box-shadow: none !important; transform: none !important; }
  .st-key-ax_logo_btn button:hover p, .st-key-ax_logo_btn button:hover p span {
      color: inherit !important; }
  .st-key-ax_logo_btn button:active { transform: none !important; }

  .ax-topmeta { display: flex; align-items: center; justify-content: flex-end;
      gap: 8px; flex-wrap: wrap; min-height: 32px; }
  .ax-chip { display: inline-flex; align-items: center; padding: 5px 12px;
      border-radius: var(--ax-r-full); background: var(--ax-surface);
      color: var(--ax-fg-2); border: 1px solid var(--ax-line-2);
      font-size: .8125rem; font-weight: 600; letter-spacing: -.004em; white-space: nowrap; }
  .ax-chip.strong { background: var(--ax-brand-weak); color: var(--ax-brand-press);
      border-color: var(--ax-brand-100); max-width: 24rem;
      overflow: hidden; text-overflow: ellipsis; display: inline-block; }

  /* 상단 바와 본문 사이 — 얇은 경계선 하나로 띠를 만든다 */
  .ax-topsep { height: 1px; background: var(--ax-line); margin: 22px 0 0; }

  /* ══════════ 진행 단계 (스텝퍼) ══════════
     번호 디스크 + 라벨 + 채워지는 연결선. 지난 단계는 채우고, 현재는
     링으로 세우고, 남은 단계는 물러나게 한다. */
  /* 폭을 묶어 둔다 — 1080px 를 꽉 채우면 연결선만 길어져 세 단계가 한 덩어리로
     안 읽히고 화면 위에 흩어진 것처럼 보인다. */
  .rc-steps { display: flex; align-items: center; gap: 0; margin: 26px 0 48px;
      padding: 0; max-width: 660px; }
  .rc-steps .st { display: flex; align-items: center; gap: 10px; flex: 0 0 auto; }
  .rc-steps .bul {
      width: 26px; height: 26px; border-radius: var(--ax-r-full);
      display: inline-flex; align-items: center; justify-content: center;
      font-size: .8125rem; font-weight: 700; flex: 0 0 auto;
      background: var(--ax-surface); color: var(--ax-fg-disabled);
      border: 1px solid var(--ax-line-2); box-shadow: var(--ax-sh-1);
      transition: all var(--ax-dur) var(--ax-ease);
  }
  .rc-steps .lb { font-size: 1rem; font-weight: 600; color: var(--ax-fg-disabled);
      white-space: nowrap; letter-spacing: -.014em;
      transition: color var(--ax-dur) var(--ax-ease); }
  .rc-steps .bar { flex: 1 1 auto; height: 1px; background: var(--ax-line-2);
      margin: 0 18px; min-width: 24px; }

  .rc-steps .on .bul { background: var(--ax-brand); border-color: var(--ax-brand);
      color: #fff; box-shadow: 0 0 0 4px var(--ax-ring); }
  .rc-steps .on .lb { color: var(--ax-ink); font-weight: 700; }
  .rc-steps .done .bul { background: var(--ax-brand-weak); border-color: var(--ax-brand-100);
      color: var(--ax-brand); }
  .rc-steps .done .lb { color: var(--ax-fg-2); }

  /* ══════════ 본문 제목 ══════════ */
  .ax-h { font-size: 1.75rem; font-weight: 750; letter-spacing: -.028em;
      line-height: 1.28; margin: 0 0 10px; color: var(--ax-fg); }
  .ax-hsub { font-size: 1.0625rem; line-height: 1.7; color: var(--ax-fg-2);
      font-weight: 450; margin: 0 0 8px; max-width: 62ch; }

  /* ══════════ 섹션 카드 ══════════
     긴 화면을 카드로 끊어 요소끼리 영역을 침범하지 않게 한다. */
  .ax-sec { background: var(--ax-surface); border: var(--ax-bd);
      border-radius: var(--ax-r-2xl); box-shadow: var(--ax-sh-1);
      padding: 32px 34px; margin: 0 0 24px; }
  .ax-sec-h { font-size: 1.125rem; font-weight: 700; letter-spacing: -.02em;
      color: var(--ax-fg); margin: 0 0 6px; }
  .ax-sec-s { font-size: .9375rem; line-height: 1.65; color: var(--ax-fg-3);
      margin: 0 0 20px; }
  .ax-kicker { font-size: .75rem; font-weight: 700; letter-spacing: .09em;
      text-transform: uppercase; color: var(--ax-fg-3); margin: 0 0 10px; }

  /* ══════════ 표 ══════════ */
  table.rc-table { width: 100%; border-collapse: separate; border-spacing: 0;
      font-size: .9375rem; background: var(--ax-surface);
      border: var(--ax-bd); border-radius: var(--ax-r-l); overflow: hidden;
      margin: 8px 0 12px; box-shadow: var(--ax-sh-1); }
  table.rc-table th, table.rc-table td {
      border-bottom: 1px solid var(--ax-line); padding: 13px 18px;
      color: var(--ax-fg-2); text-align: left; line-height: 1.6; }
  table.rc-table tr:last-child td { border-bottom: 0; }
  table.rc-table th { color: var(--ax-fg-3); font-size: .8125rem; font-weight: 650;
      letter-spacing: .01em; background: var(--ax-surface-2); }
  table.rc-table td { color: var(--ax-fg); font-weight: 450; }
  table.rc-table td.num { text-align: right; font-variant-numeric: tabular-nums; }
  table.rc-table tbody tr { transition: background var(--ax-dur-fast) var(--ax-ease); }
  table.rc-table tbody tr:hover { background: var(--ax-surface-2); }
  table.rc-table tr.total td { background: var(--ax-brand-weak);
      font-weight: 700; color: var(--ax-brand-press); }

  /* ══════════ 달성률 등급 배지 ══════════ */
  .rc-grade { display: inline-flex; align-items: center; min-width: 3.6rem;
      justify-content: center; padding: 4px 12px; border-radius: var(--ax-r-full);
      font-size: .8125rem; font-weight: 650; border: 1px solid transparent; }
  .g-su, .g-woo { background: var(--ax-ok-bg); color: var(--ax-ok); border-color: var(--ax-ok-bd); }
  .g-mi, .g-yang { background: var(--ax-warn-bg); color: var(--ax-warn); border-color: var(--ax-warn-bd); }
  .g-ga { background: var(--ax-bad-bg); color: var(--ax-bad); border-color: var(--ax-bad-bd); }
  .g-na { background: var(--ax-surface-2); color: var(--ax-fg-3); border-color: var(--ax-line-2); }

  /* ══════════ 인사이트 / Lesson Learned ══════════ */
  .rc-remark { background: var(--ax-surface); color: var(--ax-fg-2);
      border: var(--ax-bd); border-left: 3px solid var(--ax-brand);
      border-radius: var(--ax-r-l); box-shadow: var(--ax-sh-1);
      padding: 22px 26px; margin: 16px 0 20px; line-height: 1.75; font-size: .9375rem; }
  .rc-remark .h { font-size: 1.0625rem; font-weight: 700; color: var(--ax-ink);
      letter-spacing: -.018em; margin-bottom: 10px; }

  /* ══════════ 한 줄 안내 ══════════
     색을 넓게 칠하지 않는다. 옅은 틴트 + 점 하나로 등급만 알린다.
     한 화면에 안내가 열 건씩 뜨는데 전부 채우면 급한 건이 묻힌다. */
  .rc-note { display: flex; gap: 11px; align-items: flex-start;
      border: 1px solid var(--ax-line-2); border-radius: var(--ax-r-m);
      padding: 13px 17px; margin: 10px 0; font-size: .9375rem; font-weight: 450;
      color: var(--ax-fg-2); line-height: 1.65; background: var(--ax-surface); }
  .rc-note::before { content: ""; flex: 0 0 auto; width: 7px; height: 7px;
      margin-top: 9px; border-radius: var(--ax-r-full); background: var(--ax-fg-disabled); }
  .rc-note.info { background: var(--ax-surface-2); border-color: var(--ax-line); }
  .rc-note.warn { background: var(--ax-warn-bg); border-color: var(--ax-warn-bd); }
  .rc-note.warn::before { background: var(--ax-warn); }
  .rc-note.ok { background: var(--ax-ok-bg); border-color: var(--ax-ok-bd); }
  .rc-note.ok::before { background: var(--ax-ok); }
  .rc-note.err { background: var(--ax-bad-bg); border-color: var(--ax-bad-bd);
      color: var(--ax-ink); font-weight: 500; }
  .rc-note.err::before { background: var(--ax-bad); }

  /* ══════════ 완료 배지 ══════════ */
  .rc-seal { display: inline-flex; align-items: center; gap: 8px;
      padding: 8px 16px; border-radius: var(--ax-r-full);
      background: var(--ax-ok-bg); color: var(--ax-ok);
      border: 1px solid var(--ax-ok-bd); font-size: .9375rem; font-weight: 650; }
  .rc-seal::before { content: "✓"; font-weight: 800; }

  /* ══════════ 상단 메타 카드 (header()) ══════════ */
  .rc-card { margin: 0 0 28px; }
  .rc-topbar { display: flex; align-items: baseline; gap: 14px;
      padding: 0 0 18px; border-bottom: 1px solid var(--ax-line); }
  .rc-title { font-size: 1.5rem; font-weight: 750; letter-spacing: -.026em;
      color: var(--ax-fg); margin: 0; white-space: nowrap; }
  .rc-title .dot { color: var(--ax-brand); }
  .rc-sub { font-size: .9375rem; color: var(--ax-fg-3); font-weight: 500; margin: 0;
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .rc-meta { display: flex; flex-wrap: wrap; gap: 14px; margin-top: 20px; }
  .rc-meta > div { flex: 1 1 170px; background: var(--ax-surface); border: var(--ax-bd);
      border-radius: var(--ax-r-l); box-shadow: var(--ax-sh-1); padding: 16px 18px; }
  .rc-meta .k { font-size: .75rem; font-weight: 650; color: var(--ax-fg-3);
      letter-spacing: .03em; margin-bottom: 5px; }
  .rc-meta .v { font-size: 1rem; font-weight: 650; color: var(--ax-fg);
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

  /* ══════════════ Streamlit 위젯 ══════════════ */

  /* ── 버튼 — secondary(기본) = 흰 면 + 얇은 보더, primary = 코발트 채움 ── */
  .stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
      border-radius: var(--ax-r-m); border: 1px solid var(--ax-line-2);
      background: var(--ax-surface); color: var(--ax-ink);
      font-family: var(--ax-body); font-weight: 600; font-size: .9375rem;
      letter-spacing: -.012em; padding: 11px 20px; min-height: 44px;
      box-shadow: var(--ax-sh-1);
      transition: background var(--ax-dur-fast) var(--ax-ease),
                  border-color var(--ax-dur-fast) var(--ax-ease),
                  box-shadow var(--ax-dur-fast) var(--ax-ease),
                  transform var(--ax-dur-fast) var(--ax-ease); }
  .stButton > button:hover, .stDownloadButton > button:hover, .stFormSubmitButton > button:hover {
      background: var(--ax-surface-2); color: var(--ax-ink);
      border-color: var(--ax-line-2); box-shadow: var(--ax-sh-2); }
  .stButton > button:active { transform: translateY(1px); box-shadow: var(--ax-sh-1); }
  .stButton > button:focus-visible, .stDownloadButton > button:focus-visible {
      outline: none; box-shadow: 0 0 0 3px var(--ax-ring); border-color: var(--ax-brand); }

  /* 코발트 채움 버튼 = 흰 글씨 + 볼드 (자식까지 지정 — Streamlit 이 라벨을
     <p>/<div> 로 감싸므로 버튼 자신만으로는 색이 먹지 않는다 · claude.md 5) */
  .stButton > button[kind="primary"], .stButton > button[kind="primary"] *,
  .stDownloadButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] *,
  .stFormSubmitButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] *,
  .st-key-ax_final_export button, .st-key-ax_final_export button *,
  .st-key-ax_final_dl button, .st-key-ax_final_dl button * {
      color: #FFFFFF !important; font-weight: 700 !important; }
  .stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"],
  .stFormSubmitButton > button[kind="primary"] {
      background: var(--ax-brand); border: 1px solid var(--ax-brand);
      border-radius: var(--ax-r-m); font-size: 1rem; padding: 14px 26px;
      min-height: 50px; box-shadow: 0 1px 2px rgba(43,43,245,.24),
                                   0 8px 20px -8px rgba(43,43,245,.44); }
  .stButton > button[kind="primary"]:hover, .stDownloadButton > button[kind="primary"]:hover,
  .stFormSubmitButton > button[kind="primary"]:hover {
      background: var(--ax-brand-hover); border-color: var(--ax-brand-hover);
      box-shadow: 0 2px 4px rgba(43,43,245,.26),
                  0 14px 30px -10px rgba(43,43,245,.52); }
  .stButton > button[kind="primary"]:active {
      background: var(--ax-brand-press); transform: translateY(1px);
      box-shadow: 0 1px 2px rgba(43,43,245,.3); }
  .stButton > button:disabled, .stButton > button:disabled:hover,
  .stDownloadButton > button:disabled {
      opacity: .38; box-shadow: none; transform: none; cursor: not-allowed; }
  .stButton > button[kind="primary"]:disabled { background: var(--ax-brand); opacity: .34; }

  /* ── 업로드 드롭존 ──
     Streamlit 기본형은 [Upload] 버튼과 "50MB per file • PDF, XLSX…" 영문
     기술 문구가 가로로 붙어 있어 사내 개발 도구처럼 보인다. 세로 중앙 정렬로
     다시 세우고 문구를 한국어로 갈아 끼운다. 원문 span 은 지우고 ::before/
     ::after 로 대체하는데, Streamlit 이 이 문자열을 바꿀 API 를 주지 않아서다. */
  [data-testid="stFileUploaderDropzone"] {
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      gap: 18px; text-align: center;
      border: 1.5px dashed var(--ax-drop-bd); background: var(--ax-drop);
      border-radius: var(--ax-r-xl); padding: 44px 30px;
      transition: border-color var(--ax-dur) var(--ax-ease),
                  background var(--ax-dur) var(--ax-ease); }
  [data-testid="stFileUploaderDropzone"]:hover,
  [data-testid="stFileUploaderDropzone"]:focus-visible {
      border-color: var(--ax-brand); background: var(--ax-brand-weak); outline: none; }

  /* 안내문이 위, 버튼이 아래 — DOM 순서(버튼 먼저)를 order 로 뒤집는다 */
  [data-testid="stFileUploaderDropzoneInstructions"] { order: 1; margin: 0; }
  [data-testid="stFileUploaderDropzone"] > span { order: 2; }

  [data-testid="stFileUploaderDropzoneInstructions"] span { display: none !important; }
  [data-testid="stFileUploaderDropzoneInstructions"] > div::before {
      content: "여기로 끌어다 놓으세요"; display: block;
      font-size: 1.0625rem; font-weight: 600; color: var(--ax-fg-2);
      letter-spacing: -.018em; margin-bottom: 7px; }
  [data-testid="stFileUploaderDropzoneInstructions"] > div::after {
      content: "PDF · PPTX · XLSX · DOCX · 이미지 · 파일당 50MB"; display: block;
      font-size: .8125rem; font-weight: 450; color: var(--ax-fg-3);
      letter-spacing: -.004em; }

  [data-testid="stFileUploaderDropzone"] button {
      background: var(--ax-surface); border: 1px solid var(--ax-line-2);
      border-radius: var(--ax-r-m); color: var(--ax-ink) !important;
      font-weight: 600; box-shadow: var(--ax-sh-1); min-height: 42px; }
  [data-testid="stFileUploaderDropzone"] button:hover {
      background: var(--ax-surface-2); border-color: var(--ax-brand-100); }
  [data-testid="stFileUploaderDropzone"] button [data-testid="stMarkdownContainer"] p { display: none; }
  [data-testid="stFileUploaderDropzone"] button [data-testid="stMarkdownContainer"]::after {
      content: "파일 선택"; font-size: .9375rem; font-weight: 600; color: var(--ax-ink); }

  [data-testid="stFileUploaderFile"] { background: var(--ax-surface);
      border: var(--ax-bd); border-radius: var(--ax-r-m); padding: 10px 14px; margin-top: 8px; }

  /* ── '또는' 구분선 — 주 동선과 보조 동선을 시각적으로 갈라 준다 ── */
  .ax-alt-sep { display: flex; align-items: center; gap: 16px;
      margin: 0 0 22px; color: var(--ax-fg-3);
      font-size: .8125rem; font-weight: 550; letter-spacing: .02em; }
  .ax-alt-sep::before, .ax-alt-sep::after {
      content: ""; flex: 1 1 auto; height: 1px; background: var(--ax-line); }

  /* ── 입력 ── */
  .stTextInput input, .stTextArea textarea, .stNumberInput input,
  .stDateInput input, div[data-baseweb="select"] > div {
      background: var(--ax-surface) !important; color: var(--ax-ink) !important;
      border: 1px solid var(--ax-line-2) !important;
      border-radius: var(--ax-r-m) !important; font-size: 1rem !important;
      font-family: var(--ax-body) !important; font-weight: 450 !important;
      min-height: 46px; box-shadow: var(--ax-sh-1);
      transition: border-color var(--ax-dur-fast) var(--ax-ease),
                  box-shadow var(--ax-dur-fast) var(--ax-ease); }
  .stTextArea textarea { line-height: 1.68 !important; padding: 12px 14px !important; }
  .stTextInput input:hover, .stTextArea textarea:hover { border-color: var(--ax-line-2) !important; }
  .stTextInput input:focus, .stTextArea textarea:focus, .stNumberInput input:focus,
  div[data-baseweb="select"] > div:focus-within {
      border-color: var(--ax-brand) !important;
      box-shadow: 0 0 0 3px var(--ax-ring) !important; }
  .stTextInput input::placeholder, .stTextArea textarea::placeholder {
      color: var(--ax-fg-disabled) !important; }
  .stTextInput label, .stTextArea label, .stSelectbox label, .stMultiSelect label,
  .stToggle label, .stNumberInput label, .stRadio label, .stCheckbox label,
  .stSlider label, .stDateInput label {
      color: var(--ax-fg-2) !important; font-family: var(--ax-body) !important;
      font-size: .875rem !important; font-weight: 600 !important;
      letter-spacing: -.008em !important; margin-bottom: 6px !important; }
  div[data-baseweb="popover"] li:hover { background: var(--ax-brand-weak) !important; }

  /* 토글 · 체크박스 on = 코발트 */
  [data-testid="stToggle"] div[aria-checked="true"],
  div[data-baseweb="checkbox"] span[data-checked="true"] {
      background-color: var(--ax-brand) !important; border-color: var(--ax-brand) !important; }

  /* ── 확장 패널 (본문 은닉 금지 · claude.md 5 — 보조 용도로만) ── */
  div[data-testid="stExpander"] { border: var(--ax-bd); border-radius: var(--ax-r-l);
      background: var(--ax-surface); overflow: hidden; margin: 12px 0;
      box-shadow: var(--ax-sh-1); }
  div[data-testid="stExpander"] summary { font-size: .9375rem; font-weight: 600;
      color: var(--ax-fg-2); padding: 15px 20px; }

  /* ── 진행바 · 지표 ── */
  .stProgress > div > div > div { background-color: var(--ax-brand);
      border-radius: var(--ax-r-full); }
  .stProgress > div > div { background-color: var(--ax-surface-3);
      border: 0; border-radius: var(--ax-r-full); height: 6px; }
  [data-testid="stMetric"] { background: var(--ax-surface); border: var(--ax-bd);
      border-radius: var(--ax-r-l); box-shadow: var(--ax-sh-1); padding: 20px 22px; }
  [data-testid="stMetricValue"] { color: var(--ax-fg); font-size: 1.75rem;
      font-weight: 700; letter-spacing: -.032em; }
  [data-testid="stMetricLabel"] { color: var(--ax-fg-3); font-size: .8125rem;
      font-weight: 600; letter-spacing: .01em; }
  [data-testid="stMetricDelta"] { font-size: .8125rem; font-weight: 600; }

  /* ── 알림류 (st.error / warning / success / info) ──
     호출부가 45곳이라 전부 T.note 로 바꾸는 대신, 네이티브 알림이 `.rc-note`
     와 **똑같이** 보이도록 맞춘다. 어느 API 로 쓰든 같은 역할이면 같은 모양이
     나와야 제품이 하나로 읽힌다.

     두 가지를 고친다.
     1) 이중 상자 — Streamlit 은 자기 색 상자를 안에 하나 더 그린다. 바깥
        상자(우리 카드)를 지우고 안쪽 하나만 남긴다.
     2) 등급별 색 — 우리 카드가 전부 같은 회색이라 error 와 success 가
        구분되지 않았다. 심각도는 `stAlertContent*` 자식으로만 알 수 있어
        `:has()` 로 집는다. */
  div[data-testid="stAlert"] { background: transparent; border: 0;
      box-shadow: none; padding: 0; margin: 10px 0; }
  div[data-testid="stAlertContainer"] {
      border: 1px solid var(--ax-line-2); border-radius: var(--ax-r-m);
      background: var(--ax-surface); color: var(--ax-fg-2) !important;
      padding: 13px 17px; font-size: .9375rem; line-height: 1.65;
      font-weight: 450; box-shadow: none; }
  div[data-testid="stAlertContainer"] p,
  div[data-testid="stAlertContainer"] span,
  div[data-testid="stAlertContainer"] li {
      color: inherit !important; font-size: .9375rem; line-height: 1.65; }
  div[data-testid="stAlertContainer"] svg { color: inherit; opacity: .75; }

  div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) {
      background: var(--ax-bad-bg); border-color: var(--ax-bad-bd);
      color: var(--ax-ink) !important; font-weight: 500; }
  div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) {
      background: var(--ax-warn-bg); border-color: var(--ax-warn-bd); }
  div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) {
      background: var(--ax-ok-bg); border-color: var(--ax-ok-bd); }
  div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) {
      background: var(--ax-surface-2); border-color: var(--ax-line); }

  /* ── 탭 ── */
  button[data-baseweb="tab"] { font-size: .9375rem; font-weight: 600;
      color: var(--ax-fg-3); }
  button[data-baseweb="tab"][aria-selected="true"] { color: var(--ax-ink); }
  div[data-baseweb="tab-highlight"] { background-color: var(--ax-brand); height: 2px; }
  div[data-baseweb="tab-border"] { background-color: var(--ax-line); }

  /* ── 데이터프레임 · 코드 ── */
  [data-testid="stDataFrame"] { border: var(--ax-bd); border-radius: var(--ax-r-l);
      overflow: hidden; box-shadow: var(--ax-sh-1); }
  .stCode, pre { background: var(--ax-surface-2) !important; border: var(--ax-bd);
      border-radius: var(--ax-r-m); font-size: .875rem !important; }

  /* ── 다이얼로그 ── */
  div[data-testid="stDialog"] div[role="dialog"] {
      border-radius: var(--ax-r-2xl); border: var(--ax-bd);
      box-shadow: var(--ax-sh-3); padding: 8px; }

  /* ── 사이드바 전면 제거 (상단 바 체제) ── */
  section[data-testid="stSidebar"], [data-testid="stSidebarCollapseButton"],
  [data-testid="collapsedControl"], [data-testid="stSidebarCollapsedControl"] {
      display: none !important; }

  /* ══════════ 슬라이드 썸네일 ══════════
     슬라이드 카드(.sp-slide)는 내부가 전부 절대좌표 px 이라 폭만 줄이면
     내용이 삐져나온다. 화면이 좁아지면 카드째 축소해 비율을 지킨다.
     `overflow:hidden` 은 zoom 을 모르는 브라우저에서도 옆 칸을 침범하지
     않게 막는 안전장치다 (태블릿 폭에서 실제로 잘려 나갔다). */
  .ax-thumb { padding: 10px; border-radius: var(--ax-r-l);
      border: 1px solid transparent; background: transparent;
      overflow: hidden;
      transition: background var(--ax-dur-fast) var(--ax-ease),
                  border-color var(--ax-dur-fast) var(--ax-ease),
                  box-shadow var(--ax-dur-fast) var(--ax-ease); }
  .ax-thumb .sp-slide { max-width: 100%; }
  @media (max-width: 1100px) { .ax-thumb .sp-slide { zoom: .84; } }
  @media (max-width: 900px)  { .ax-thumb .sp-slide { zoom: .70; } }
  @media (max-width: 760px)  { .ax-thumb .sp-slide { zoom: .60; } }
  @media (max-width: 640px)  { .ax-thumb .sp-slide { zoom: 1; } }
  .ax-thumb:hover { background: var(--ax-surface); box-shadow: var(--ax-sh-1); }
  .ax-thumb.on { border-color: var(--ax-brand-100); background: var(--ax-surface);
      box-shadow: var(--ax-sh-2); }
  .ax-thumb-cap { font-size: .8125rem; font-weight: 600; color: var(--ax-fg-3);
      margin-top: 9px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .ax-thumb.on .ax-thumb-cap { color: var(--ax-brand-press); }

  /* ══════════ 올린 파일 칩 ══════════ */
  .ax-files { display: flex; flex-wrap: wrap; gap: 9px; margin: 10px 0 4px; }
  .ax-file { display: inline-flex; align-items: center; gap: 10px;
      padding: 9px 15px; border-radius: var(--ax-r-full); background: var(--ax-surface);
      border: 1px solid var(--ax-line-2); box-shadow: var(--ax-sh-1);
      font-size: .875rem; font-weight: 550; color: var(--ax-fg-2); max-width: 100%; }
  .ax-file .sz { color: var(--ax-fg-3); font-size: .8125rem;
      font-variant-numeric: tabular-nums; flex: 0 0 auto; }

  /* ══════════ 최종 추출 버튼 — 화면에서 가장 강한 한 곳 ══════════ */
  .st-key-ax_final_export button, .st-key-ax_final_dl button {
      background: var(--ax-brand) !important; color: #fff !important;
      border: 1px solid var(--ax-brand) !important; border-radius: var(--ax-r-l) !important;
      min-height: 58px !important; font-size: 1.0625rem !important;
      box-shadow: 0 2px 4px rgba(43,43,245,.26),
                  0 14px 32px -10px rgba(43,43,245,.5) !important; }
  .st-key-ax_final_export button:hover, .st-key-ax_final_dl button:hover {
      background: var(--ax-brand-hover) !important;
      box-shadow: 0 3px 6px rgba(43,43,245,.3),
                  0 20px 44px -12px rgba(43,43,245,.56) !important; }

  /* ══════════ 문안 수정 패널 ══════════ */
  .af-panel { background: var(--ax-surface); border: var(--ax-bd);
      border-radius: var(--ax-r-2xl); box-shadow: var(--ax-sh-2);
      padding: 26px; position: sticky; top: 18px; }
  .af-drawer-title { font-size: 1.0625rem; font-weight: 700; letter-spacing: -.02em;
      color: var(--ax-fg); border-bottom: 1px solid var(--ax-line);
      padding-bottom: 14px; margin-bottom: 6px; }
  .af-chip { display: inline-block; margin: 4px 6px 4px 0; padding: 7px 14px;
      border: 1px solid var(--ax-line-2); border-radius: var(--ax-r-full);
      font-size: .8125rem; font-weight: 550; color: var(--ax-fg-2);
      line-height: 1.5; background: var(--ax-surface); }
  .af-chip:hover { color: var(--ax-brand); border-color: var(--ax-brand-100); }
  .af-sub { font-size: .8125rem; font-weight: 650; letter-spacing: .04em;
      text-transform: uppercase; color: var(--ax-fg-3); margin: 26px 0 10px; }
  .af-empty { border: 1px dashed var(--ax-line-2); border-radius: var(--ax-r-l);
      padding: 20px; margin: 12px 0 14px; font-size: .9375rem; font-weight: 450;
      color: var(--ax-fg-3); line-height: 1.7; background: var(--ax-surface-2); }

  /* ══════════ 위젯 간 세로 리듬 ══════════
     Streamlit 기본 간격은 촘촘해서 요소가 서로 붙어 보인다. 넉넉히 벌린다. */
  [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"] { margin-bottom: 2px; }
  [data-testid="stHorizontalBlock"] { gap: 22px; }
  .stButton, .stDownloadButton { margin-top: 4px; }
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
  html, body, .stApp { background: var(--ax-bg); }
  .stApp { min-height: 100vh; }
  .block-container { padding-top: 0 !important; padding-bottom: 40px !important;
      max-width: 1000px; }
  header[data-testid="stHeader"] { background: transparent; height: 0; }
  #MainMenu, footer, [data-testid="stToolbar"] { visibility: hidden; }
  [data-testid="stDecoration"] { display: none; }

  html, body, .stApp { font-size: 17px; }
  html, body, .stApp, .stMarkdown, p, span, div, label, button,
  .stApp h1, .stApp h2, .stApp h3, .stApp h4 {
      font-family: var(--ax-body);
      -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale;
      color: var(--ax-fg); letter-spacing: -.011em;
      word-break: keep-all; overflow-wrap: break-word; }
  .stApp p, .stApp li, .stApp span, .stApp div, .stApp label,
  .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5 {
      word-break: keep-all !important; overflow-wrap: break-word !important; }
  .kbr { display: inline-block; }
  [class^="after-"] span, [class*=" after-"] span, h1 span, h2 span, h3 span, h4 span {
      font-size: inherit; font-weight: inherit; line-height: inherit; letter-spacing: inherit; }

  /* 등장 — 한 번의 잘 짜인 리빌. 요소마다 흩뿌리지 않는다. */
  @keyframes afterRise {
      from { opacity: 0; transform: translateY(14px); }
      to   { opacity: 1; transform: none; } }
  .fade { animation: afterRise var(--ax-dur-slow) var(--ax-ease) both; }
  .d1 { animation-delay: .04s; } .d2 { animation-delay: .12s; }
  .d3 { animation-delay: .20s; } .d4 { animation-delay: .28s; }
  .d5 { animation-delay: .36s; }
  @media (prefers-reduced-motion: reduce) { .fade { animation: none; } }

  .after-hero { text-align: center; padding: 0; min-height: 46vh;
      display: flex; flex-direction: column; align-items: center; justify-content: center; }
  .after-hero > * { margin-left: auto; margin-right: auto; }

  .after-badge { display: inline-flex; align-items: center; margin-bottom: 30px;
      padding: 7px 16px; border: 1px solid var(--ax-line-2); border-radius: var(--ax-r-full);
      background: var(--ax-surface); box-shadow: var(--ax-sh-1);
      color: var(--ax-fg-2); font-size: .8125rem; font-weight: 600;
      letter-spacing: .06em; }

  .after-title { font-size: clamp(3.2rem, 8.4vw, 5.6rem); line-height: 1.02;
      letter-spacing: -.045em; font-weight: 800; color: var(--ax-fg);
      margin: 0 0 1.5rem; }
  .after-title .accent { color: var(--ax-brand); }

  .stApp .after-lead { max-width: 620px; margin: 0 auto;
      font-size: 1.3125rem; line-height: 1.62; font-weight: 450;
      color: var(--ax-fg-2); letter-spacing: -.018em; }

  /* CTA — 코발트 채움, 흰 글씨 볼드 (claude.md 5) */
  div[data-testid="stButton"] button[kind="primary"],
  div[data-testid="stButton"] button[kind="primary"] * {
      color: #FFFFFF !important; font-weight: 700 !important; }
  div[data-testid="stButton"] button[kind="primary"] {
      width: 100%; background: var(--ax-brand);
      border: 1px solid var(--ax-brand); border-radius: var(--ax-r-l);
      padding: 18px 26px; font-size: 1.0625rem; min-height: 58px;
      letter-spacing: -.012em;
      box-shadow: 0 2px 4px rgba(43,43,245,.24),
                  0 16px 34px -12px rgba(43,43,245,.5);
      transition: background var(--ax-dur-fast) var(--ax-ease),
                  box-shadow var(--ax-dur) var(--ax-ease),
                  transform var(--ax-dur-fast) var(--ax-ease); }
  div[data-testid="stButton"] button[kind="primary"]:hover {
      background: var(--ax-brand-hover);
      box-shadow: 0 3px 8px rgba(43,43,245,.28),
                  0 22px 46px -14px rgba(43,43,245,.58);
      transform: translateY(-1px); }
  div[data-testid="stButton"] button[kind="primary"]:active {
      background: var(--ax-brand-press); transform: translateY(0);
      box-shadow: 0 1px 3px rgba(43,43,245,.3); }

  .after-notice { text-align: center; font-size: .8125rem; font-weight: 400;
      color: var(--ax-fg-3); margin: 1.6rem 0 0; letter-spacing: -.004em;
      line-height: 1.7; }
"""

LANDING_CSS = f"<style>{FONT_FACES}{_tokens()}{_LANDING_BASE}</style>"

HERO_HTML = """
<div class="after-hero">
  <div class="after-badge fade d1">비즈니스 3본부 AX</div>
  <h1 class="after-title fade d2">AFTER <span class="accent">CAMPAIGN</span></h1>
  <p class="after-lead fade d3">
    <span class="kbr">흩어진 캠페인 자료를 올리면,</span><br>
    <span class="kbr">결과 리포트를 대신 만들어 드려요.</span>
  </p>
</div>
"""

# ═══════════════════════════ 컴포넌트

def _esc(s) -> str:
    """HTML 이스케이프 — 캠페인명·매체명이 그대로 마크업에 들어가므로 필수"""
    return (str(s if s is not None else '')
            .replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


# 실제로 렌더를 망가뜨리는 것만 막는다. `.` `-` `(` 처럼 인라인에서 무해한
# 문자까지 escape 하면 화면에 역슬래시가 비쳐 더 지저분해진다.
#   $ → LaTeX 수식   _ * → 강조   ` → 코드   ~ → 취소선   [ ] → 링크
_MD_SPECIALS = '`*_$~[]'


def safe_md(text) -> str:
    """
    동적 문자열을 Streamlit 마크다운에 넣기 전에 무해화한다.

    실제로 터진 화면: 엑셀 잠금 파일(`~$…xlsx`)을 열다 난 예외 메시지를
    `st.caption(f'· {w}')` 로 그대로 흘렸더니, 경로 속 `_` 가 이탤릭으로,
    `$` 가 LaTeX 수식으로 해석되면서 파일 경로가 기울어진 수학 기호 덩어리로
    렌더됐다. 사용자에겐 그냥 '깨진 화면'이다.

    파서 경고·예외 문구처럼 **내용을 우리가 통제하지 못하는 문자열**은 전부
    이걸 통과시킬 것.
    """
    s = str(text if text is not None else '')
    return ''.join('\\' + c if c in _MD_SPECIALS else c for c in s)


def strip_paths(text) -> str:
    """
    메시지에서 절대 경로를 파일명만 남기고 지운다.

    `C:\\Users\\CHEIL\\Desktop\\AX3BB\\Input\\...\\a.xlsx` 같은 서버 내부
    경로는 AE 에게 아무 정보도 주지 못하면서 화면만 잡아먹고, 호스팅 환경에서는
    서버 디렉터리 구조까지 드러낸다. 파일명만 남긴다.
    """
    import re
    s = str(text if text is not None else '')
    # Windows(C:\a\b\c.xlsx) · POSIX(/a/b/c.xlsx) 경로를 파일명으로 축약.
    #
    # 폴더명에 공백이 흔해서(`(에어컨) 2025 …`) 세그먼트 안의 공백은 허용해야
    # 한다. 다만 구분자 **바로 앞뒤**의 공백은 허용하지 않는다 — 그러지 않으면
    # 평범한 문장의 ' / ' 구분자까지 경로로 보고 삼켜 버린다(실제로 체크리스트
    # 문구의 ' / ' 가 사라졌다). 그래서 세그먼트는 공백이 아닌 문자로 시작하고
    # 끝나야 하며, 드라이브 문자나 선행 구분자가 있어야 경로로 인정한다.
    # 경로로 인정하는 조건을 좁게 잡는다. 아래 셋을 모두 만족해야 한다.
    #   ① 낱말 경계에서 시작 (앞이 공백·따옴표·괄호이거나 문장 처음)
    #   ② 드라이브 문자(C:) 또는 선행 구분자로 시작하는 '절대 경로'
    #   ③ 마지막 조각에 확장자가 붙어 있음
    # 이 셋이 없으면 'A/B 테스트', '노출/클릭' 같은 평범한 표현까지 경로로
    # 오인해 문장을 잘라먹는다 (실제로 그랬다).
    seg = r"[^\\/'\"\n\s](?:[^\\/'\"\n]*[^\\/'\"\n\s])?"
    pattern = (r"(?:^|(?<=[\s'\"(\[]))"          # ①
               r"(?:[A-Za-z]:)?[\\/]"            # ②
               rf"(?:{seg}[\\/])*"
               rf"({seg}\.[A-Za-z0-9]{{1,6}})")  # ③
    s = re.sub(pattern, r'\1', s)
    return re.sub(r'[ \t]{2,}', ' ', s).strip()


def josa(word: str, pair: str = '을/를') -> str:
    """
    앞 낱말의 받침에 맞는 조사를 붙여 준다.

    화면에 '데일리리포트을 못 읽었어요' 처럼 조사가 어긋난 문장이 떠 있었다.
    한 글자 차이지만 이런 게 제품을 대번에 아마추어처럼 보이게 한다.
    조사를 문자열에 박아 두지 말고 이 함수를 쓸 것.

    Args:
        word: 조사 앞에 오는 낱말
        pair: '받침있음/받침없음' 형식 — 을/를, 이/가, 은/는, 과/와, 으로/로

    Returns:
        `word` + 알맞은 조사
    """
    with_batchim, without = (pair.split('/') + [''])[:2]
    ch = (word or '').strip()
    if not ch:
        return word or ''
    last = ch[-1]
    if not ('가' <= last <= '힣'):
        # 한글이 아니면(영문·숫자·기호) 받침 판정이 불가능하다. 받침 없는 쪽을
        # 쓰는 편이 어색함이 덜하다.
        return f'{ch}{without}'
    has_batchim = (ord(last) - 0xAC00) % 28 != 0
    # '으로/로' 는 ㄹ 받침이 예외 — '서울로'지 '서울으로'가 아니다
    if pair.startswith('으로') and (ord(last) - 0xAC00) % 28 == 8:
        has_batchim = False
    return f'{ch}{with_batchim if has_batchim else without}'


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


def section(title: str, sub: str = '', kicker: str = '') -> None:
    """
    섹션 머리 — 긴 화면을 의미 단위로 끊는다.

    카드로 감싸지 않고 머리만 찍는 이유: Streamlit 위젯을 임의의 div 안에
    넣을 수 없어서(마크다운은 형제로 렌더된다) 감싸는 척만 하면 오히려
    경계가 어긋난다. 여백과 타이포로 묶는 편이 정직하고 튼튼하다.
    """
    st.markdown(
        (f'<p class="ax-kicker">{_esc(kicker)}</p>' if kicker else '')
        + f'<div class="ax-sec-h">{_esc(title)}</div>'
        + (f'<p class="ax-sec-s">{_esc(sub)}</p>' if sub else ''),
        unsafe_allow_html=True)


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
    """
    한 줄 안내 — level: info | ok | warn | err

    네 등급 모두 옅은 틴트 + 점 색으로만 구분한다. 면을 꽉 채우는 알림은
    한 화면에 여러 건이 뜨는 순간 서로를 죽인다.
    """
    cls = {'ok': 'ok', 'error': 'err', 'err': 'err',
           'info': 'info'}.get(level, 'warn')
    # 여기서는 safe_md 를 쓰지 않는다. HTML 블록 안의 텍스트에는 Streamlit 이
    # 마크다운을 돌리지 않아서, escape 한 역슬래시가 그대로 화면에 보인다
    # (`\[권고\]` 처럼). 마크다운 무해화가 필요한 곳은 st.caption/st.markdown
    # 처럼 **평문을 마크다운으로 렌더하는** 자리다.
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
