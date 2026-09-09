# -*- coding: utf-8 -*-
"""
Design Spec — `theme.py` 의 cm 단위 어댑터.

2026.09.09 통합 (사용자 지시)
  이 파일은 원래 표본 1종(시스템에어컨 1024)을 분석해 만든 **별개의**
  디자인 시스템이었다. 그 결과 저장소에 PPTX 디자인 규격이 둘 존재했고,
  `theme.py` 를 고쳐도 이 경로로 만든 덱은 그대로여서 변경이 반영되지 않은
  것처럼 보이는 함정이 있었다.

  이제 이 파일은 **상수를 스스로 갖지 않는다.** 좌표·색·폰트·크기는 전부
  `theme.py` 에서 끌어와 cm 로 환산해 노출할 뿐이다. 규격을 바꿀 일이 있으면
  `theme.py` 만 고치면 되고, 이 파일과 `test_ppt_render.py` 는 자동으로 따라온다.

  공개 API(Master · Body · Palette · Font · Size · apply_masters ·
  add_text_box · add_filled_rect · _set_run)는 호출부를 고치지 않도록
  그대로 유지했다.

단위 — `theme.py` 는 inch, 이 파일은 cm. `_cm()` 하나로만 환산한다.
"""
from __future__ import annotations

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Cm, Pt

from . import theme as T

IN_TO_CM = 2.54


def _cm(inches: float) -> float:
    """theme.py 의 inch 값을 cm 로."""
    return inches * IN_TO_CM


def _c(hex6: str) -> RGBColor:
    return RGBColor.from_string(hex6)


# ═══════════════════════════ 슬라이드 프레임 (theme.py 파생)
SLIDE_W_CM = _cm(T.SLIDE_W)      # 33.866
SLIDE_H_CM = _cm(T.SLIDE_H)      # 19.05


# ═══════════════════════════ 마스터 요소 (theme.py 좌표를 cm 로)
class Master:
    """
    헤더·키메시지의 실제 그리기는 `apply_masters()` 가 theme 컴포넌트에
    위임한다. 아래 값은 호출부가 위치를 참조할 때만 쓴다.
    """
    # 캠페인 태그 (theme.TAG_POS)
    LOGO_LEFT_CM = _cm(T.TAG_POS[0])
    LOGO_TOP_CM = _cm(T.TAG_POS[1])
    LOGO_W_CM = _cm(T.TAG_POS[2])
    LOGO_H_CM = _cm(T.TAG_POS[3])

    # 키메시지 (theme.KEY_POS) — 중앙 정렬 24pt
    TITLE_LEFT_CM = _cm(T.KEY_POS[0])
    TITLE_TOP_CM = _cm(T.KEY_POS[1])
    TITLE_W_CM = _cm(T.KEY_POS[2])
    TITLE_H_CM = _cm(T.KEY_POS[3])

    # 리드 문장은 키메시지 블록의 sub 단락으로 흡수됐다.
    # 좌표만 남겨 두어 호출부가 참조해도 깨지지 않게 한다.
    LEAD_LEFT_CM = TITLE_LEFT_CM
    LEAD_TOP_CM = TITLE_TOP_CM + TITLE_H_CM
    LEAD_W_CM = TITLE_W_CM
    LEAD_H_CM = _cm(0.30)

    # 페이지 번호 — 각주 라인 우측 끝
    PAGENO_W_CM = _cm(1.20)
    PAGENO_H_CM = _cm(0.30)
    PAGENO_LEFT_CM = SLIDE_W_CM - PAGENO_W_CM - _cm(0.38)
    PAGENO_TOP_CM = _cm(T.FOOT_Y)


# ═══════════════════════════ 본문 그리드
class Body:
    """
    본문 영역. 상단은 theme 의 콘텐츠 존, 하단은 각주 라인에서 자동으로 온다.
    열 수·행 수는 데이터 양에 따라 계산한다 (하드코딩 금지 — 프로젝트 규칙).
    """
    LEFT_CM = _cm(0.49)                      # 표준 외곽 여백
    TOP_CM = _cm(T.CONTENT_Y + 0.20)         # 콘텐츠 존 + 대괄호 라벨 자리
    RIGHT_CM = SLIDE_W_CM - _cm(0.49)
    BOTTOM_CM = _cm(T.FOOT_Y - 0.12)         # 각주 위 여유

    @classmethod
    def width_cm(cls) -> float:
        return cls.RIGHT_CM - cls.LEFT_CM

    @classmethod
    def height_cm(cls) -> float:
        return cls.BOTTOM_CM - cls.TOP_CM

    @classmethod
    def columns(cls, n: int, gap_cm: float = _cm(0.08)):
        """본문을 n 등분 → [(left_cm, width_cm), ...]. 거터 기본값은 실측 0.08in."""
        total = cls.width_cm()
        col_w = (total - gap_cm * (n - 1)) / n
        return [(cls.LEFT_CM + i * (col_w + gap_cm), col_w) for i in range(n)]

    @classmethod
    def rows(cls, n: int, gap_cm: float = 0.3):
        """세로 균등 분할 → [(top_cm, height_cm), ...]"""
        total = cls.height_cm()
        row_h = (total - gap_cm * (n - 1)) / n
        return [(cls.TOP_CM + i * (row_h + gap_cm), row_h) for i in range(n)]


# ═══════════════════════════ 팔레트 (theme.py 파생)
class Palette:
    INK = _c(T.INK)                  # 본문 #404040
    INK_STRONG = _c(T.BLACK)         # 제목·강조 #000000
    INK_MUTED = _c(T.FOOT)           # 각주·캡션 #7F7F7F

    ACCENT = _c(T.BLUE_SKY)          # #0096FF — 실측 시그니처 액센트
    ACCENT_SOFT = _c(T.BLUE_LIGHT)   # #18A2FF
    FILL_STRONG = _c('3E86D6')       # 매체 패널 헤더바 (흰 글자 전용)

    TBL_HEAD = _c(T.TBL_HEAD)        # #E1F3FF — 표 헤더 (검정 글자)
    TOTAL_ROW = _c(T.TOTAL_ROW)      # #767171 — 합계 행 (흰 글자)
    HILITE = _c(T.HILITE)            # #FEF5BE — 강조 셀
    BAND_LIGHT = _c(T.TBL_HEAD)
    BAND_MEDIUM = _c('98D5FC')
    NEUTRAL_BG = _c(T.PANEL)         # #F8F9FD — 전폭 패널·카드 바탕
    BORDER = _c(T.LINE_CARD)         # #D9D9D9 — 괘선·카드 테두리
    WHITE = _c(T.WHITE)

    # 상태색 — Checklist 전용. 레퍼런스에 색 코딩은 없으나
    # 이 화면은 광고주 보고가 아니라 기획자 확인용이라 예외로 둔다.
    ALERT = _c(T.NEG)                # 미달·에러 #D96D77
    WARN = _c('A8761C')
    OK = _c('1F6F4A')


# ═══════════════════════════ 타이포그래피 (theme.py 파생)
class Font:
    HEAD_BOLD = T.HEAD_BOLD
    HEAD_MEDIUM = T.HEAD_MED
    HEAD_REGULAR = T.HEAD_REG
    HEAD_LIGHT = T.HEAD_LIGHT
    BODY_BOLD = T.BODY_BOLD
    BODY_REGULAR = T.BODY_REG
    BODY_LIGHT = T.BODY_LIGHT


class Size:
    COVER = Pt(T.SZ_COVER)          # 36
    SECTION = Pt(T.SZ_SECTION)      # 28
    TITLE = Pt(T.SZ_KEY)            # 24 — 키메시지
    HEADLINE = Pt(T.SZ_KEY_SUB)     # 18 — 키커·부제
    SUBTITLE = Pt(T.SZ_TAG)         # 16 — 태그·섹션 라벨
    CARD_TITLE = Pt(T.SZ_CARD_TITLE)  # 14
    BODY = Pt(T.SZ_BODY)            # 12
    LABEL = Pt(T.SZ_LABEL)          # 11 — 대괄호 소제목
    SMALL = Pt(T.SZ_TABLE)          # 10 — 표 셀
    ANNOT = Pt(T.SZ_CHART)          # 9
    CAPTION = Pt(T.SZ_FOOT)         # 8 — 각주·페이지 번호


# ═══════════════════════════ 저수준 헬퍼

def _set_run(run, text, *, font, size, color, bold=False):
    """
    런의 글꼴·크기·색을 지정한다. `theme.set_run_font()` 에 위임하므로
    latin/ea/cs 세 typeface 가 함께 기록되고 bold 플래그는 제거된다.

    (통합 전 이 함수는 `font.name` 만 설정해 **한글이 테마 폰트로 새는**
     문제가 있었다. 위임으로 그 결함이 함께 사라진다.)

    bold=True 는 폰트 이름을 같은 패밀리의 Bold 로 승격시킨다.
    """
    run.text = text
    face = font
    if bold and not face.endswith('Bold'):
        stem = face.rsplit(' ', 1)[0] if face.rsplit(' ', 1)[-1] in (
            'Light', 'Regular', 'Medium') else face
        face = stem + ' Bold'
    pts = size.pt if hasattr(size, 'pt') else float(size)
    hex6 = str(color) if not isinstance(color, str) else color
    T.set_run_font(run, face, pts, hex6)


def add_text_box(slide, left_cm, top_cm, w_cm, h_cm, *,
                 anchor='top', align='left'):
    """텍스트 박스 하나 그리고 반환. 첫 문단은 슬라이드가 자동 생성."""
    box = slide.shapes.add_textbox(Cm(left_cm), Cm(top_cm),
                                   Cm(w_cm), Cm(h_cm))
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Cm(0.05)
    tf.margin_top = tf.margin_bottom = Cm(0.02)
    tf.vertical_anchor = {
        'top': MSO_ANCHOR.TOP,
        'middle': MSO_ANCHOR.MIDDLE,
        'bottom': MSO_ANCHOR.BOTTOM,
    }[anchor]
    tf.paragraphs[0].alignment = {
        'left': PP_ALIGN.LEFT, 'center': PP_ALIGN.CENTER,
        'right': PP_ALIGN.RIGHT,
    }[align]
    return box


def add_filled_rect(slide, left_cm, top_cm, w_cm, h_cm,
                    fill_rgb, *, line_rgb=None, line_pt=0.5,
                    shape=MSO_SHAPE.RECTANGLE):
    """도형 하나 그리고 채움·선 색 지정. 그림자는 항상 끈다 (레퍼런스 0건)."""
    sh = slide.shapes.add_shape(shape, Cm(left_cm), Cm(top_cm),
                                Cm(w_cm), Cm(h_cm))
    sh.shadow.inherit = False
    sh.fill.solid()
    sh.fill.fore_color.rgb = fill_rgb
    if line_rgb is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = line_rgb
        sh.line.width = Pt(line_pt)
    sh.text_frame.margin_left = sh.text_frame.margin_right = Cm(0.1)
    sh.text_frame.margin_top = sh.text_frame.margin_bottom = Cm(0.05)
    return sh


# ═══════════════════════════ 마스터 렌더러 — theme 컴포넌트에 위임

def draw_page_no(slide, page: int, total: int):
    box = add_text_box(slide, Master.PAGENO_LEFT_CM, Master.PAGENO_TOP_CM,
                       Master.PAGENO_W_CM, Master.PAGENO_H_CM,
                       anchor='middle', align='right')
    _set_run(box.text_frame.paragraphs[0].add_run(),
             f'{page:02d} / {total:02d}',
             font=Font.BODY_LIGHT, size=Size.CAPTION, color=Palette.INK_MUTED)


def apply_masters(slide, *, doc_title: str, section: str, page: int, total: int,
                  title: str, lead: str = ''):
    """
    정적 마스터를 한 번에 얹는다.

    2026.09.09 — 자체 구현(좌상단 로고 + 좌측 액센트 바 제목)을 버리고
    `theme.add_header()` / `theme.add_key_message()` 로 위임했다. 이제
    이 경로로 만든 덱도 운영 경로와 **글자 하나까지 같은 헤더 골격**을 갖는다.
      · 캠페인 태그 ｜ 섹션  → 괘선 → 셰브런 플래그 + 라벨
      · 키메시지 24pt Head Bold 중앙 정렬 (+ lead 를 sub 단락으로)
    """
    T.add_header(slide, doc_title, section)
    T.add_key_message(slide, [{'text': title, 'emph': True}],
                      sub=lead or None)
    draw_page_no(slide, page, total)
