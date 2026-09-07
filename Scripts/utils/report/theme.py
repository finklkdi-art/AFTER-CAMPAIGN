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
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
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

# ───────────────────────── 공통 지오메트리 (design-spec.md §3)
SLIDE_W = 13.333
SLIDE_H = 7.5
TAG_POS = (0.49, 0.28, 6.0, 0.32)        # L3a 캠페인 태그
SEC_SQ = (0.52, 0.72, 0.09, 0.09)        # ■ 액센트
SEC_POS = (0.70, 0.63, 11.0, 0.30)       # L3b 섹션 라벨
KEY_POS = (0.63, 1.22, 12.06, 1.25)      # L4 키메시지
CONTENT_Y = 2.60
FOOT_Y = 7.02


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
             anchor=MSO_ANCHOR.TOP, wrap=True, line_spacing=None):
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

def add_header(slide, campaign_tag: str, section_label: str) -> None:
    """L3a 캠페인 태그 + L3b ■ 섹션 라벨"""
    add_text(slide, *TAG_POS, [(campaign_tag, BODY_BOLD, 12, BLACK)])
    add_rect(slide, *SEC_SQ, BLUE_MAIN)
    add_text(slide, *SEC_POS, [(section_label, BODY_REG, 12, BLACK)])


def add_key_message(slide, parts: Sequence[dict], hilites=None) -> None:
    """
    L4 키메시지. parts = [{'text', 'emph'?, 'color'?, 'break'?}]
    비강조 = Body Light / 강조 = Body Bold + BLUE_EMPH (bold 플래그 아님)
    hilites = [(x, w)] 형광펜 사각형 (텍스트 뒤 z-order)
    """
    for hx, hw in (hilites or []):
        add_rect(slide, hx, 1.64, hw, 0.20, HILITE)

    paragraphs: List[List[tuple]] = [[]]
    for p in parts:
        face = BODY_BOLD if p.get('emph') else BODY_LIGHT
        color = p.get('color') or (BLUE_EMPH if p.get('emph') else INK)
        paragraphs[-1].append((p['text'], face, 20, color))
        if p.get('break'):
            paragraphs.append([])
    if not paragraphs[-1]:
        paragraphs.pop()

    add_text(slide, *KEY_POS, paragraphs,
             align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)


def add_block_label(slide, text: str, x: float, y: float, w: float = 6.0) -> None:
    """L5 블록라벨 — '[ ... ]'"""
    add_text(slide, x, y, w, 0.28, [(f'[ {text} ]', BODY_BOLD, 11, BLACK)])


def add_footnote(slide, notes, y: float = FOOT_Y) -> None:
    """L8 각주/출처 — '* ' 접두"""
    arr = notes if isinstance(notes, (list, tuple)) else [notes]
    paragraphs = [[((n if str(n).startswith('*') else f'* {n}'),
                    BODY_REG, 8, FOOT)] for n in arr]
    add_text(slide, 0.63, y, 12.06, 0.40, paragraphs)


def add_divider(slide, text: str, *, appendix: bool = False,
                font_size: int = 30) -> None:
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


def add_styled_table(slide, header: Sequence[str], rows: Sequence[Sequence],
                     *, x: float, y: float, w: float,
                     col_w: Optional[Sequence[float]] = None,
                     font_size: float = 9, row_h: float = 0.24,
                     total_row: bool = False):
    """
    표준 표. 셀 값: 문자열 또는 {'t', 'right'?, 'hilite'?}
    - 헤더행 E1F3FF (bold 아님 — 원본 관례)
    - Total행 767171 + 흰 글씨
    - 강조 셀 FEF5BE
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

    def put(r, c, value, *, fill, color, right=False):
        cell = table.cell(r, c)
        cell.margin_left = cell.margin_right = Emu(27432)   # 0.03in
        cell.margin_top = cell.margin_bottom = 0
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        cell.fill.solid()
        cell.fill.fore_color.rgb = _rgb(fill)
        _cell_border(cell)
        tf = cell.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.RIGHT if right else PP_ALIGN.CENTER
        run = p.add_run()
        run.text = str(value)
        set_run_font(run, BODY_REG, font_size, color)

    for c, h in enumerate(header):
        put(0, c, h, fill=TBL_HEAD, color=BLACK)

    for ri, row in enumerate(rows, start=1):
        is_total = total_row and ri == n_rows - 1
        # 헤더보다 셀이 많은 행(파서가 만든 들쭉날쭉한 표)이 들어와도
        # 슬라이드를 잃지 않는다. 넘치는 칸은 그리지 않는다.
        for c, cell_val in enumerate(row[:n_cols]):
            spec = cell_val if isinstance(cell_val, dict) else {'t': cell_val}
            fill = TOTAL_ROW if is_total else (HILITE if spec.get('hilite') else WHITE)
            color = WHITE if is_total else BLACK
            put(ri, c, spec.get('t', ''), fill=fill, color=color,
                right=bool(spec.get('right')))
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
