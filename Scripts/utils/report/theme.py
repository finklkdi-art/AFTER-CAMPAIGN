# -*- coding: utf-8 -*-
"""
결과보고서 디자인 시스템 — design-spec.md / theme.js 의 python-pptx 포팅

원본 스킬은 pptxgenjs 기준이라 웨이트를 bold:true 로 표현했으나,
본 포팅은 사용자 절대 규칙에 따라 bold 플래그를 일절 쓰지 않고
웨이트별 독립 패밀리명으로 폰트를 지정한다.

  스킬 표기                     ->  본 포팅 (Windows 등록명 = OTF name ID1)
  "Samsung SS Head KR"+bold    ->  "Samsung SS Head KR Bold"
  "Samsung SS Body KR"+bold    ->  "Samsung SS Body KR Bold"
  "Samsung SS Body KR"(비강조)  ->  "Samsung SS Body KR Light" (키메시지)
                                    "Samsung SS Body KR Regular" (본문/표)

또한 python-pptx 의 font.name 은 <a:latin> 만 설정하므로 한글이 테마 폰트로
새지 않도록 모든 런에 latin/ea/cs 세 typeface 를 동일하게 기록한다.
"""

from typing import List, Optional, Sequence

from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR, MSO_AUTO_SIZE
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn

EMU_PER_IN = 914400

# ───────────────────────── 컬러 시스템 (design-spec.md §1)
INK = '404040'
BLACK = '000000'
WHITE = 'FFFFFF'
BLUE_MAIN = '0666D6'
BLUE_EMPH = '4472C4'
BLUE_SOFT = '5B9BD5'
BLUE_SKY = '0096FF'
BLUE_LIGHT = '18A2FF'
CYAN_ACCENT = '5FDDFB'
TBL_HEAD = 'E1F3FF'
HILITE = 'FEF5BE'
TOTAL_ROW = '767171'
MUTED = '808080'
FOOT = '7F7F7F'
LINE = '747474'
LINE_SOFT = 'BFBFBF'
LINE_CARD = 'D9D9D9'
GRAY_BAR = 'EBEBEB'
NEG = 'D96D77'
BG_CARD = 'F2F2F2'
DARK_NAVY = '1B2A4A'
DARK_APPX = '15161A'

# 2026.09.09 추가 — 레퍼런스 실측에서 빠져 있던 토큰
PANEL = 'F8F9FD'        # 전폭 콘텐츠 패널 (흰 카드를 띄우는 지면)
TBL_LABEL = 'F2F2F2'    # 표 좌측 구분열
CONCLUSION = '1457C9'   # 하단 전폭 결론 밴드 (흰 글자)
FLAG_A = '7CC7EE'       # 셰브런 플래그 그라디언트 시작
FLAG_B = '2C7BD6'       # 셰브런 플래그 그라디언트 끝
BASELINE_BAR = 'DDE7F2'  # 제안값(비교 기준) 막대 — 결과 막대와 명도로만 대비
GRIDLINE = 'EDEDED'     # 차트 가로 격자선 (세로선은 쓰지 않음)

# ───────────────────────── 폰트 (bold 플래그 금지 — 이름으로 웨이트 선택)
HEAD_BOLD = 'Samsung SS Head KR Bold'
HEAD_MED = 'Samsung SS Head KR Medium'
HEAD_REG = 'Samsung SS Head KR Regular'
HEAD_LIGHT = 'Samsung SS Head KR Light'
BODY_BOLD = 'Samsung SS Body KR Bold'
BODY_REG = 'Samsung SS Body KR Regular'
BODY_LIGHT = 'Samsung SS Body KR Light'

ALLOWED_FONTS = {HEAD_BOLD, HEAD_MED, HEAD_REG, HEAD_LIGHT,
                 BODY_BOLD, BODY_REG, BODY_LIGHT}

# ───────────────────────── 공통 지오메트리
#
# 2026.09.09 개정 — 레퍼런스 4개 덱 265슬라이드의 PPTX 좌표 실측값으로 교체함.
# 근거·편차는 `.claude/skills/report-design-system/reference/design-system.md`.
# 아래 값은 전부 4개 덱의 최빈값(mode)이며 단위는 inch.
SLIDE_W = 13.333
SLIDE_H = 7.5

TAG_POS = (0.49, 0.30, 6.0, 0.32)        # L3a 캠페인 태그 · 16pt Head Medium
RULE_POS = (0.55, 0.69, 2.46)            # L3 헤더 괘선 (x, y, 최대폭) · 1px
FLAG_POS = (0.55, 0.77, 0.22, 0.23)      # L3 셰브런 플래그 (■ 사각에서 교체)
SEC_POS = (0.70, 0.75, 11.0, 0.30)       # L3b 섹션 라벨 · 16pt Head Medium
#   괘선(0.69) → 플래그·라벨(0.75~0.77) 사이 0.06~0.08in 을 띄운다.
#   실측 R03 = 괘선 0.68 / 플래그 0.80, R04 = 괘선 0.69 / 플래그 0.74 의 중간값.
#   같은 y 에 두면 라벨 글자가 괘선 위에 얹혀 두 줄이 붙어 읽힌다.
KEY_POS = (0.99, 1.24, 11.36, 1.30)      # L4 키메시지 — 중심 6.667 = 캔버스 중심
CONTENT_Y = 2.56                         # 전폭 콘텐츠 패널 상단
FOOT_POS = (0.38, 7.02, 12.06)           # L8 각주 (x, y, w)
FOOT_Y = FOOT_POS[1]                     # 하위 호환

# 타이포 스케일 — 실측에 존재하는 크기만. 중간값(13·15·17·22)을 만들지 말 것.
SZ_COVER = 36
SZ_SECTION = 28
SZ_KEY = 24                              # 키메시지 · 본문 12pt 대비 2.0 : 1
SZ_KEY_SUB = 18
SZ_TAG = 16
SZ_CARD_TITLE = 14
SZ_BODY = 12
SZ_LABEL = 11                            # 대괄호 소제목
SZ_TABLE = 10
SZ_CHART = 9
SZ_FOOT = 8

# 표 행 높이 사다리 — 행이 넘치면 행을 지우지 말고 이 단계로 낮춘다 (CLAUDE.md 3.1)
ROW_H_LADDER = (0.403, 0.37, 0.311, 0.234, 0.144)


def row_height_for(n_rows: int, *, top: float = CONTENT_Y + 0.45,
                   bottom: float = FOOT_Y - 0.06) -> float:
    """
    행 수에 맞는 행 높이를 사다리에서 고른다.

    실측 근거 — 8행 이하 0.403/0.37 · 12행 0.311 · 17행 0.234 · 30행 0.144.
    사다리의 가장 큰 값부터 시도해 세로 공간에 들어가는 첫 값을 쓴다.
    다 안 들어가면 마지막 값(0.144)을 쓰되, 그래도 넘치면 호출부가
    페이지를 나눠야 한다 — 여기서 행을 버리지 않는다.
    """
    avail = max(bottom - top, 0.5)
    for h in ROW_H_LADDER:
        if h * max(n_rows, 1) <= avail:
            return h
    return ROW_H_LADDER[-1]


# ═════════════════════════ 저수준 유틸

def _rgb(hex6: str) -> RGBColor:
    return RGBColor.from_string(hex6)


def set_run_font(run, face: str, size: float, color: str) -> None:
    """
    런에 폰트를 적용한다.

    - latin / ea / cs 세 typeface 를 동일하게 기록 (한글 폰트 누수 방지)
    - bold 속성은 절대 만들지 않으며, 있던 것도 제거한다
    """
    if face not in ALLOWED_FONTS:
        raise ValueError(f'허용되지 않은 폰트: {face}')
    run.font.size = Pt(size)
    run.font.color.rgb = _rgb(color)

    rPr = run._r.get_or_add_rPr()
    rPr.attrib.pop('b', None)            # 굵게 플래그 원천 차단
    rPr.attrib.pop('i', None)
    for tag in ('a:latin', 'a:ea', 'a:cs'):
        for el in rPr.findall(qn(tag)):
            rPr.remove(el)
    for tag in ('a:latin', 'a:ea', 'a:cs'):
        el = rPr.makeelement(qn(tag), {'typeface': face})
        rPr.append(el)


def add_text(slide, x, y, w, h, runs, *, align=PP_ALIGN.LEFT,
             anchor=MSO_ANCHOR.TOP, wrap=True, line_spacing=None,
             shrink_to_fit=True):
    """
    텍스트박스 추가. runs = [(text, face, size, color), ...] 또는
    줄바꿈은 [[run,...], [run,...]] (단락 리스트).

    Returns: shape
    """
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = wrap
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    if shrink_to_fit:
        # 텍스트가 박스보다 길면 **넘쳐 흐르지 않고 줄어들게** 한다.
        #
        # 이 문서의 모든 박스는 고정 좌표로 놓인다. 기본값(자동 맞춤 없음)
        # 에서는 긴 문안이 박스 밖으로 그대로 흘러 아래 영역(본문 표·각주)
        # 위에 겹쳐 찍힌다. 미리보기는 2줄로 잘라 보여 주는데 실제 PPT 는
        # 겹쳐 나오는, 눈에 띄지 않는 불일치가 생긴다.
        #
        # normAutofit 은 **넘칠 때만** 동작한다 — 지금처럼 잘 맞는 문안에는
        # 아무 영향이 없어서, 기존 슬라이드 모양은 그대로 유지된다.
        try:
            tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
        except Exception:
            pass

    paragraphs = runs if runs and isinstance(runs[0], list) else [runs]
    for pi, para_runs in enumerate(paragraphs):
        p = tf.paragraphs[0] if pi == 0 else tf.add_paragraph()
        p.alignment = align
        if line_spacing:
            p.line_spacing = line_spacing
        for text, face, size, color in para_runs:
            r = p.add_run()
            r.text = text
            set_run_font(r, face, size, color)
    return box


def add_rect(slide, x, y, w, h, fill: Optional[str],
             line_color: Optional[str] = None, line_pt: float = 0.75):
    """단색 사각형 (line_color=None 이면 테두리 없음)"""
    sh = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.shadow.inherit = False
    if fill is None:
        sh.fill.background()
    else:
        sh.fill.solid()
        sh.fill.fore_color.rgb = _rgb(fill)
    if line_color is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = _rgb(line_color)
        sh.line.width = Pt(line_pt)
    return sh


def set_slide_background(slide, hex6: str) -> None:
    """슬라이드 단색 배경"""
    from pptx.oxml.ns import qn as _qn
    bg = slide.background
    bg.fill.solid()
    bg.fill.fore_color.rgb = _rgb(hex6)


# ═════════════════════════ 레벨별 컴포넌트 (theme.js 포팅)

def add_chevron_flag(slide, x: float, y: float,
                     w: float = FLAG_POS[2], h: float = FLAG_POS[3]):
    """
    L3 셰브런 플래그 — 섹션 라벨 앞의 방향 표식.

    레퍼런스 R01·R03·R04 가 **동일한 원본 이미지**(266×245px, 동일 crop)를
    공유하는 사내 공용 자산이다. 우리는 그 이미지를 배포할 수 없으므로
    같은 실루엣(오른쪽을 향한 갈매기)을 CHEVRON 도형 + 좌→우 그라디언트로
    재현한다. 종전의 ■ 정사각(SEC_SQ)은 레퍼런스에 존재하지 않아 폐기했다.
    """
    sh = slide.shapes.add_shape(
        MSO_SHAPE.CHEVRON, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.shadow.inherit = False
    sh.line.fill.background()
    try:
        sh.fill.gradient()
        stops = sh.fill.gradient_stops
        stops[0].color.rgb = _rgb(FLAG_A)
        stops[1].color.rgb = _rgb(FLAG_B)
        sh.fill.gradient_angle = 0.0
    except Exception:                    # 그라디언트 미지원 시 단색 폴백
        sh.fill.solid()
        sh.fill.fore_color.rgb = _rgb(FLAG_B)
    return sh


def add_header(slide, campaign_tag: str, section_label: str,
               page_function: Optional[str] = None) -> None:
    """
    L3 페이지 헤더 — 4개 덱 전부에 존재하는 유일한 필수 컴포넌트.

    구성 (실측)
        y 0.30  캠페인 태그      16pt Head Medium
                page_function 이 있으면 "태그 ｜ 기능명" 으로 잇고
                기능명만 Head Regular 로 낮춘다 (R01 s6 관례)
        y 0.69  헤더 괘선        1px 검정 · 폭은 태그 글자수에 hug
        y 0.74  셰브런 플래그 + 섹션 라벨 16pt Head Medium
    """
    runs = [(campaign_tag, HEAD_MED, SZ_TAG, BLACK)]
    if page_function:
        runs.append((' ｜ ', HEAD_LIGHT, SZ_TAG, BLACK))
        runs.append((page_function, HEAD_REG, SZ_TAG, BLACK))
    add_text(slide, *TAG_POS, runs)

    # 괘선은 태그 텍스트 폭을 따라간다. 한글은 16pt 에서 약 0.22in/자,
    # 라틴·기호는 그 절반으로 잡아 근사한다 (실측 폭 1.48 ~ 2.46in).
    label = campaign_tag + (f' ｜ {page_function}' if page_function else '')
    est = sum(0.22 if ord(ch) > 0x2000 else 0.11 for ch in label)
    rx, ry, rmax = RULE_POS
    add_rect(slide, rx, ry, min(max(est, 1.0), rmax), 0.01, BLACK)

    add_chevron_flag(slide, FLAG_POS[0], FLAG_POS[1])
    add_text(slide, *SEC_POS, [(section_label, HEAD_MED, SZ_TAG, BLACK)],
             anchor=MSO_ANCHOR.MIDDLE)


def add_key_message(slide, parts: Sequence[dict], hilites=None,
                    kicker: Optional[str] = None,
                    sub: Optional[str] = None) -> None:
    """
    L4 키메시지 — 페이지의 결론을 먼저 말하는 한 문장.

    2026.09.09 개정 — 레퍼런스 실측에 맞춰 3단 구조로 바꿨다.
        kicker   18pt Head Light  #404040   (기간·범위 등 맥락)
        MAIN     24pt Head Bold   #000000   ← parts 가 여기 들어간다
        sub      18pt Head Light  #404040   (보조 수치)
    전 줄 중앙 정렬. 종전 20pt Body 계열에서 24pt Head 계열로 올린 이유는
    본문 12pt 대비 2.0 : 1 비율이 4개 덱 공통이기 때문 (24/12).

    parts = [{'text', 'emph'?, 'color'?, 'break'?}]
        emph=False → Head Light  (같은 줄 안의 비강조 어절)
        emph=True  → Head Bold   (강조 어절)
        color 를 주면 그 색으로 (액센트 강조는 BLUE_SKY 사용)
    hilites = [(x, w)] 형광펜 사각형 (텍스트 뒤 z-order)
    """
    for hx, hw in (hilites or []):
        add_rect(slide, hx, 1.64, hw, 0.20, HILITE)

    paragraphs: List[List[tuple]] = []
    if kicker:
        paragraphs.append([(kicker, HEAD_LIGHT, SZ_KEY_SUB, INK)])

    main: List[List[tuple]] = [[]]
    for p in parts:
        face = HEAD_BOLD if p.get('emph') else HEAD_LIGHT
        color = p.get('color') or BLACK
        main[-1].append((p['text'], face, SZ_KEY, color))
        if p.get('break'):
            main.append([])
    if not main[-1]:
        main.pop()
    paragraphs.extend(main)

    if sub:
        paragraphs.append([(sub, HEAD_LIGHT, SZ_KEY_SUB, INK)])

    add_text(slide, *KEY_POS, paragraphs,
             align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)


def add_block_label(slide, text: str, x: float, y: float, w: float = 6.0) -> None:
    """
    L5 블록라벨 — '[ ... ]'. 표·차트·이미지 그룹 등 **데이터 블록** 위에만 붙는다.
    문장에는 쓰지 않는다. 실측 11pt Head Regular (Body Bold 아님).
    블록 상단에서 0.29in 위에 놓는 것이 레퍼런스 관례.
    """
    add_text(slide, x, y, w, 0.28, [(f'[ {text} ]', HEAD_REG, SZ_LABEL, BLACK)])


def add_footnote(slide, notes, y: float = FOOT_Y) -> None:
    """
    L8 각주/출처 — '* ' 접두. 실측 8pt **Body KR Light** (Regular 아님),
    x 0.38 좌측 정렬. 출처·산식·제외 조건을 여기 명시한다.
    """
    arr = notes if isinstance(notes, (list, tuple)) else [notes]
    paragraphs = [[((n if str(n).startswith('*') else f'* {n}'),
                    BODY_LIGHT, SZ_FOOT, FOOT)] for n in arr]
    fx, _fy, fw = FOOT_POS
    add_text(slide, fx, y, fw, 0.40, paragraphs)


def add_content_panel(slide, y: float = CONTENT_Y, fill: str = PANEL):
    """
    전폭 콘텐츠 패널 — x 0 · w 13.33, y 에서 하단까지. 흰 카드를 띄우는 지면.
    4개 덱 전부가 y 2.52 ~ 2.76 에서 이 패널을 깐다. 그림자 없이
    명도차만으로 카드를 분리하는 것이 이 시스템의 깊이 표현이다.
    """
    return add_rect(slide, 0, y, SLIDE_W, SLIDE_H - y, fill)


def add_conclusion_band(slide, lines: Sequence[str], *, y: float = 4.50,
                        notch: bool = True):
    """
    하단 전폭 결론 밴드 (R03 P04 원형) — 근거를 위에 쌓고 결론을 여기서 선언한다.

    x 0 · y 4.50 · 13.33 × 3.00in · #1457C9 · 흰 20~24pt Head Bold.
    상변 중앙에 아래를 향한 삼각 노치. **페이지당 1회**, 장(章)당 1회 이내.
    """
    band = add_rect(slide, 0, y, SLIDE_W, SLIDE_H - y, CONCLUSION)
    if notch:
        tri = slide.shapes.add_shape(
            MSO_SHAPE.ISOSCELES_TRIANGLE,
            Inches(SLIDE_W / 2 - 0.70), Inches(y), Inches(1.40), Inches(0.60))
        tri.rotation = 180
        tri.shadow.inherit = False
        tri.line.fill.background()
        tri.fill.solid()
        tri.fill.fore_color.rgb = _rgb(WHITE)
    add_text(slide, 0, y + 0.85, SLIDE_W, SLIDE_H - y - 1.2,
             [[(t, HEAD_BOLD, SZ_KEY_SUB + 2, WHITE)] for t in lines],
             align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.4)
    return band


def add_kpi_tile(slide, x: float, y: float, w: float, h: float, *,
                 label: str, value: str, caption: str = '',
                 negative: bool = False):
    """
    KPI 타일 — 제안 대비 달성률 한 칸. 실측 1.31~1.49 × 1.56~1.73in.
    숫자 24~28pt Head Bold · 달성 #0096FF / 미달 #D96D77.
    """
    add_rect(slide, x, y, w, h, WHITE, LINE_CARD, 0.5)
    add_text(slide, x, y + 0.14, w, 0.24, [(label, HEAD_LIGHT, SZ_LABEL, FOOT)],
             align=PP_ALIGN.CENTER)
    add_text(slide, x, y + 0.40, w, 0.55,
             [(value, HEAD_BOLD, SZ_KEY, NEG if negative else BLUE_SKY)],
             align=PP_ALIGN.CENTER)
    if caption:
        add_text(slide, x, y + h - 0.34, w, 0.24,
                 [(caption, HEAD_LIGHT, SZ_TABLE, INK)], align=PP_ALIGN.CENTER)


def add_divider(slide, text: str, *, appendix: bool = False,
                font_size: int = SZ_SECTION) -> None:
    """L2 간지 / E.O.D — 다크 배경 정중앙"""
    set_slide_background(slide, DARK_APPX if appendix else DARK_NAVY)
    add_text(slide, 0, 3.2, SLIDE_W, 1.1, [(text, HEAD_BOLD, font_size, WHITE)],
             align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)


# ═════════════════════════ 표 (design-spec.md §4)

def _cell_border(cell, color: str = LINE, pt: float = 0.5) -> None:
    """python-pptx 미지원 셀 테두리를 XML 로 지정"""
    tcPr = cell._tc.get_or_add_tcPr()
    w = str(int(Pt(pt)))
    for tag in ('a:lnL', 'a:lnR', 'a:lnT', 'a:lnB'):
        for el in tcPr.findall(qn(tag)):
            tcPr.remove(el)
    for tag in ('a:lnL', 'a:lnR', 'a:lnT', 'a:lnB'):
        ln = tcPr.makeelement(qn(tag), {'w': w, 'cap': 'flat'})
        fill = ln.makeelement(qn('a:solidFill'), {})
        clr = fill.makeelement(qn('a:srgbClr'), {'val': color})
        fill.append(clr)
        ln.append(fill)
        tcPr.append(ln)


def _cell_hatch(cell, color: str = 'E4E4E4') -> None:
    """
    결측 셀 45° 사선 해칭.

    빈칸이나 0 을 쓰면 '값이 0' 과 '측정되지 않음' 이 구별되지 않는다.
    레퍼런스(R04 s7)는 측정 불가 칸을 전부 사선으로 채워 이를 구분한다.
    python-pptx 에 패턴 채우기 API 가 없어 XML 로 직접 넣는다.
    """
    tcPr = cell._tc.get_or_add_tcPr()
    for tag in ('a:solidFill', 'a:noFill', 'a:pattFill'):
        for el in tcPr.findall(qn(tag)):
            tcPr.remove(el)
    patt = tcPr.makeelement(qn('a:pattFill'), {'prst': 'ltUpDiag'})
    fg = patt.makeelement(qn('a:fgClr'), {})
    fg.append(fg.makeelement(qn('a:srgbClr'), {'val': color}))
    bg = patt.makeelement(qn('a:bgClr'), {})
    bg.append(bg.makeelement(qn('a:srgbClr'), {'val': WHITE}))
    patt.append(fg)
    patt.append(bg)
    tcPr.append(patt)


def add_styled_table(slide, header: Sequence[str], rows: Sequence[Sequence],
                     *, x: float, y: float, w: float,
                     col_w: Optional[Sequence[float]] = None,
                     font_size: float = 9, row_h: float = 0.24,
                     total_row: bool = False, label_col: bool = False):
    """
    표준 표. 셀 값: 문자열 또는 {'t', 'right'?, 'hilite'?, 'na'?}

    실측 규격
      - 헤더행 #E1F3FF + 검정 **Head Medium** (Body Regular 아님 · 2026.09.09 교정)
      - 본문 Body Regular · 중앙 정렬 (이 시스템의 표는 우측 정렬을 쓰지 않음)
      - 강조 셀 #FEF5BE + Body Bold — 페이지당 하나의 강조 장치로만
      - Total행 #767171 + 흰 Head Medium · 최하단 1행만
      - label_col=True 면 0열을 #F2F2F2 구분열로 (병합 대신 색으로 구분)
      - {'na': True} 셀은 45° 사선 해칭 — 빈칸·0 과 '측정 안 됨'을 구분한다
    """
    n_rows = len(rows) + 1
    n_cols = len(header)
    gf = slide.shapes.add_table(n_rows, n_cols, Inches(x), Inches(y),
                                Inches(w), Inches(row_h * n_rows))
    table = gf.table
    # 기본 표 스타일(밴딩/헤더 강조) 제거 — 색은 전부 명시적으로
    table.first_row = False
    table.horz_banding = False

    if col_w:
        # 🔴 col_w 길이를 표의 실제 열 수에 맞춘다.
        #
        # 호출부는 기본 col_w 로 9칸짜리 비율을 넘긴다(renderer). 헤더가 그보다
        # 좁은 표(예: 4열)에 그대로 적용하면 `table.columns[4]` 에서
        # IndexError 가 나며 **그 슬라이드가 통째로 날아간다.**
        # 열 수가 다른 표를 넣는 건 정상 입력이므로 여기서 맞춰 준다.
        widths = list(col_w)[:n_cols]
        if len(widths) < n_cols:                # 모자라면 남는 칸은 균등 분배
            widths += [1.0] * (n_cols - len(widths))
        total = sum(widths) or float(n_cols)
        for i, cw in enumerate(widths):
            table.columns[i].width = Emu(int(w * EMU_PER_IN * cw / total))
    for r in range(n_rows):
        table.rows[r].height = Emu(int(row_h * EMU_PER_IN))

    def put(r, c, value, *, fill, color, right=False,
            face=BODY_REG, na=False):
        cell = table.cell(r, c)
        cell.margin_left = cell.margin_right = Emu(27432)   # 0.03in
        cell.margin_top = cell.margin_bottom = 0
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        cell.fill.solid()
        cell.fill.fore_color.rgb = _rgb(fill)
        if na:
            _cell_hatch(cell)
        _cell_border(cell)
        tf = cell.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.RIGHT if right else PP_ALIGN.CENTER
        run = p.add_run()
        run.text = str(value)
        set_run_font(run, face, font_size, color)

    for c, h in enumerate(header):
        put(0, c, h, fill=TBL_HEAD, color=BLACK, face=HEAD_MED)

    for ri, row in enumerate(rows, start=1):
        is_total = total_row and ri == n_rows - 1
        # 헤더보다 셀이 많은 행(파서가 만든 들쭉날쭉한 표)이 들어와도
        # 슬라이드를 잃지 않는다. 넘치는 칸은 그리지 않는다.
        for c, cell_val in enumerate(row[:n_cols]):
            spec = cell_val if isinstance(cell_val, dict) else {'t': cell_val}
            is_na = bool(spec.get('na'))
            is_label = label_col and c == 0 and not is_total
            if is_total:
                fill, color, face = TOTAL_ROW, WHITE, HEAD_MED
            elif spec.get('hilite'):
                fill, color, face = HILITE, BLACK, BODY_BOLD
            elif is_label:
                fill, color, face = TBL_LABEL, BLACK, HEAD_MED
            else:
                fill, color, face = WHITE, BLACK, BODY_REG
            put(ri, c, spec.get('t', ''), fill=fill, color=color, face=face,
                right=bool(spec.get('right')), na=is_na)
    return gf


# ═════════════════════════ 차트 (design-spec.md §5)

def _patch_chart_fonts(chart, size: float = 9) -> None:
    """
    차트 XML 전체의 rPr/defRPr 에 Body Regular + latin/ea/cs 를 강제하고
    bold 속성을 제거한다. (python-pptx 가 못 미치는 축·레이블·범례 포함)
    """
    root = chart._chartSpace
    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    for el in root.iter():
        tag = el.tag
        if tag == f'{{{ns_a}}}rPr' or tag == f'{{{ns_a}}}defRPr':
            el.attrib.pop('b', None)
            el.attrib.pop('i', None)
            if 'sz' not in el.attrib:
                el.set('sz', str(int(size * 100)))
            for t in ('latin', 'ea', 'cs'):
                for old in el.findall(qn(f'a:{t}')):
                    el.remove(old)
            for t in ('latin', 'ea', 'cs'):
                el.append(el.makeelement(qn(f'a:{t}'), {'typeface': BODY_REG}))


def _hide_value_axis(chart) -> None:
    """값 축 삭제 (valAxisHidden)"""
    xml = chart._chartSpace
    for valAx in xml.iter(qn('c:valAx')):
        delete = valAx.find(qn('c:delete'))
        if delete is None:
            delete = valAx.makeelement(qn('c:delete'), {})
            valAx.insert(1, delete)
        delete.set('val', '1')


def _strip_gridlines(chart) -> None:
    for tag in ('c:majorGridlines', 'c:minorGridlines'):
        for ax in list(chart._chartSpace.iter(qn('c:valAx'))) + \
                  list(chart._chartSpace.iter(qn('c:catAx'))):
            for gl in ax.findall(qn(tag)):
                ax.remove(gl)


def _cat_label_skip(chart, every: int) -> None:
    """카테고리 축 레이블 간격 (일자 축 겹침 방지)"""
    for catAx in chart._chartSpace.iter(qn('c:catAx')):
        el = catAx.find(qn('c:tickLblSkip'))
        if el is None:
            el = catAx.makeelement(qn('c:tickLblSkip'), {})
            catAx.append(el)
        el.set('val', str(max(1, every)))


def add_line_chart(slide, categories, series, *, x, y, w, h,
                   label_skip: int = 7):
    """
    추이 라인차트. series = [{'name', 'values', 'color'?, 'width'?}]
    자사 기본 0096FF 2.25pt, 마커 없음, 값축 숨김, 격자 제거.
    """
    from pptx.chart.data import CategoryChartData
    from pptx.enum.chart import XL_CHART_TYPE

    data = CategoryChartData()
    data.categories = list(categories)
    for s in series:
        data.add_series(s['name'], s['values'])

    gf = slide.shapes.add_chart(XL_CHART_TYPE.LINE, Inches(x), Inches(y),
                                Inches(w), Inches(h), data)
    chart = gf.chart
    chart.has_legend = len(series) > 1
    if chart.has_legend:
        from pptx.enum.chart import XL_LEGEND_POSITION
        chart.legend.position = XL_LEGEND_POSITION.BOTTOM
        chart.legend.include_in_layout = False
    chart.has_title = False

    palette = [BLUE_SKY, NEG, GRAY_BAR, BLUE_LIGHT]
    for i, plot_s in enumerate(chart.series):
        color = series[i].get('color') or palette[i % len(palette)]
        plot_s.format.line.color.rgb = _rgb(color)
        plot_s.format.line.width = Pt(series[i].get('width', 2.25))
        try:
            plot_s.smooth = False
        except Exception:
            pass
        try:                                     # 마커 제거 (구버전 호환 가드)
            from pptx.enum.chart import XL_MARKER_STYLE
            plot_s.marker.style = XL_MARKER_STYLE.NONE
        except Exception:
            pass

    _hide_value_axis(chart)
    _strip_gridlines(chart)
    _cat_label_skip(chart, label_skip)
    _patch_chart_fonts(chart)
    return gf


def add_achievement_chart(slide, items, *, x, y, w, h):
    """
    제안 대비 달성율 차트 (theme.js addAchievementChart 포팅)

    지표별 스케일 차이를 없애기 위해 제안=100 으로 정규화하고,
    달성 막대 위 % 레이블은 텍스트박스로 배치 (Body Bold 14, BLUE_MAIN).
    items = [{'label': '노출', 'pct': 123}, ...]
    """
    from pptx.chart.data import CategoryChartData
    from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION

    data = CategoryChartData()
    data.categories = [i['label'] for i in items]
    data.add_series('제안', [100] * len(items))
    data.add_series('달성', [i['pct'] for i in items])

    gf = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED,
                                Inches(x), Inches(y), Inches(w), Inches(h), data)
    chart = gf.chart
    chart.has_title = False
    chart.has_legend = True
    chart.legend.position = XL_LEGEND_POSITION.BOTTOM
    chart.legend.include_in_layout = False
    plot = chart.plots[0]
    plot.gap_width = 80
    plot.has_data_labels = False

    fills = [GRAY_BAR, BLUE_MAIN]
    for i, s in enumerate(chart.series):
        s.format.fill.solid()
        s.format.fill.fore_color.rgb = _rgb(fills[i])
        s.format.line.fill.background()

    _hide_value_axis(chart)
    _strip_gridlines(chart)
    _patch_chart_fonts(chart)

    # % 레이블 — 막대 상단 근사 좌표 (theme.js 로직 이식)
    max_v = max([100] + [i['pct'] for i in items])
    plot_h = h - 0.65
    slot_w = w / len(items)
    for i, it in enumerate(items):
        bar_top = y + plot_h * (1 - it['pct'] / max_v) - 0.32
        add_text(slide,
                 x + slot_w * i + slot_w * 0.5 - 0.35,
                 max(y - 0.05, bar_top),
                 slot_w * 0.7, 0.3,
                 [(f"{it['pct']}%", BODY_BOLD, 14, BLUE_MAIN)],
                 align=PP_ALIGN.CENTER)
    return gf


# ═════════════════════════ 이미지 / 플레이스홀더

def add_image_placeholder(slide, x, y, w, h, label: str = '소재 이미지') -> None:
    add_rect(slide, x, y, w, h, BG_CARD, LINE_CARD, 0.75)
    add_text(slide, x, y, w, h, [(label, BODY_REG, 9, MUTED)],
             align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
