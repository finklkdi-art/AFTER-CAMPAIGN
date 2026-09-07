# -*- coding: utf-8 -*-
"""
디자인 시스템 (Design Spec) — 표본 PPTX 정밀 분석에서 추출한 상수·헬퍼.

출처
  Output/Samples/결과보고서_25년_시스템에어컨_인피니트&당일설치캠페인_1024.pptx
  분석: scratchpad/analyze_sample.py (21장 · 도형·색·폰트·좌표 통계)

원칙
  1. 정적 마스터  : 문서 브랜딩·제목 바 등 모든 장표 공통 요소는
                    이 파일의 상수 좌표로 고정 (흔들림 방지)
  2. 동적 컨텐츠 : 본문 영역은 BODY 좌표·거터 상수를 기반으로 그리드에
                    비례 배치 (열 수에 따라 자동 분할)
  3. 폰트         : `Samsung SS Head/Body KR` 만 허용.
                    표본은 SamsungOneKoreanOTF 를 썼지만 프로젝트 규칙 우선.
                    웨이트 매핑: 700C↔Bold · 500C↔Medium · 400C↔Regular ·
                                  300C↔Light
"""
from __future__ import annotations

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Cm, Pt


# ═══════════════════════════ 슬라이드 프레임 (16:9 와이드)
# 표본 실측: 33.867 × 19.05 cm (정확히 SlideSize.WIDESCREEN)
SLIDE_W_CM = 33.867
SLIDE_H_CM = 19.05


# ═══════════════════════════ 정적 마스터 요소 (모든 장표 공통 고정 좌표)
# 표본에서 90% 이상 반복 등장한 위치·크기를 그대로 채택.
class Master:
    # 좌상단 문서 브랜딩 (표본: -0.2, 0.7, 7.3×1.8, 90% 반복)
    LOGO_LEFT_CM   = -0.2
    LOGO_TOP_CM    = 0.7
    LOGO_W_CM      = 7.3
    LOGO_H_CM      = 1.8

    # 슬라이드 제목 바 (표본: 0.7, 3.1, 32.4×1.5)
    TITLE_LEFT_CM  = 0.7
    TITLE_TOP_CM   = 3.1
    TITLE_W_CM     = 32.4
    TITLE_H_CM     = 1.5

    # 부제(설명 문장) 텍스트 (표본: 3.6~4.0, 3.3~4.4, ~26.6×2.3)
    LEAD_LEFT_CM   = 3.6
    LEAD_TOP_CM    = 4.6
    LEAD_W_CM      = 26.6
    LEAD_H_CM      = 2.0

    # 페이지 번호 (표본에는 없음. 통일감을 위해 우측 하단에 고정 좌표 부여)
    PAGENO_LEFT_CM = 31.4
    PAGENO_TOP_CM  = 18.3
    PAGENO_W_CM    = 2.2
    PAGENO_H_CM    = 0.5


# ═══════════════════════════ 본문 그리드 (동적 배치용)
class Body:
    """
    본문 영역은 여기 정의된 (LEFT, TOP, W, H) 사각형 안에서만 배치한다.
    실제 열 수·행 수는 데이터의 양에 따라 자동 계산 (하드코딩 금지 — 규칙 3).
    """
    LEFT_CM   = 2.4      # 표본에서 좌측 콘텐츠 정렬 기준
    TOP_CM    = 6.7      # 부제 아래
    RIGHT_CM  = 31.5     # 우측 안전 여백
    BOTTOM_CM = 17.8     # 페이지 번호 위

    @classmethod
    def width_cm(cls) -> float:
        return cls.RIGHT_CM - cls.LEFT_CM

    @classmethod
    def height_cm(cls) -> float:
        return cls.BOTTOM_CM - cls.TOP_CM

    @classmethod
    def columns(cls, n: int, gap_cm: float = 0.4):
        """
        본문 영역을 n개 균등 컬럼으로 분할해 [(left_cm, width_cm), ...] 반환.
        데이터 개수에 맞춰 호출 (예: 매체 카드 3장 → columns(3)).
        """
        total = cls.width_cm()
        col_w = (total - gap_cm * (n - 1)) / n
        return [(cls.LEFT_CM + i * (col_w + gap_cm), col_w) for i in range(n)]

    @classmethod
    def rows(cls, n: int, gap_cm: float = 0.3):
        """세로 방향 균등 분할 [(top_cm, height_cm), ...]"""
        total = cls.height_cm()
        row_h = (total - gap_cm * (n - 1)) / n
        return [(cls.TOP_CM + i * (row_h + gap_cm), row_h) for i in range(n)]


# ═══════════════════════════ 팔레트 (표본 채움색·글자색 상위)
class Palette:
    # 글자색 (표본: #404040 134회, #000000 99회, #0666D6 4회)
    INK          = RGBColor(0x40, 0x40, 0x40)   # 본문 기본 (부드러운 먹)
    INK_STRONG   = RGBColor(0x00, 0x00, 0x00)   # 강조 헤드라인
    INK_MUTED    = RGBColor(0x6B, 0x6B, 0x6B)   # 캡션·부가정보

    # 액센트 (표본 파랑 계열)
    ACCENT       = RGBColor(0x06, 0x66, 0xD6)   # 링크·강조
    ACCENT_SOFT  = RGBColor(0x18, 0xA2, 0xFF)
    FILL_STRONG  = RGBColor(0x00, 0x84, 0xDE)   # 표 헤더 등 진한 배경

    # 밴드·표 배경
    BAND_LIGHT   = RGBColor(0xE1, 0xF3, 0xFF)   # 부제 배경, 표 짝수행
    BAND_MEDIUM  = RGBColor(0x98, 0xD5, 0xFC)
    NEUTRAL_BG   = RGBColor(0xF8, 0xF9, 0xFD)   # 카드 바탕
    BORDER       = RGBColor(0xCB, 0xD3, 0xDB)   # 표·카드 테두리

    # 상태색 (Checklist)
    ALERT        = RGBColor(0xB3, 0x37, 0x2B)   # 에러
    WARN         = RGBColor(0xA8, 0x76, 0x1C)   # 경고
    OK           = RGBColor(0x1F, 0x6F, 0x4A)   # 정보


# ═══════════════════════════ 타이포그래피 (표본 폰트 크기 상위)
class Font:
    # 폰트 웨이트 — Samsung SS Head/Body KR 만 사용
    # 표본의 SamsungOneKoreanOTF 700C/500C/400C/300C 에 대응
    HEAD_BOLD    = 'Samsung SS Head KR Bold'
    HEAD_MEDIUM  = 'Samsung SS Head KR Medium'
    HEAD_REGULAR = 'Samsung SS Head KR Regular'
    BODY_BOLD    = 'Samsung SS Body KR Bold'
    BODY_REGULAR = 'Samsung SS Body KR Regular'
    BODY_LIGHT   = 'Samsung SS Body KR Light'


class Size:
    # 표본 실측 상위 8개 (24, 20, 14, 12, 10.5, 9, 8 pt)
    TITLE       = Pt(24)   # 슬라이드 제목 바
    HEADLINE    = Pt(20)   # 부제 상단 라인
    SUBTITLE    = Pt(14)   # 부제·리드 문장
    BODY        = Pt(12)   # 본문 텍스트
    SMALL       = Pt(10.5) # 표 셀·주석
    ANNOT       = Pt(9)    # 세부 주석
    CAPTION     = Pt(8)    # 페이지 번호·자료원


# ═══════════════════════════ 마스터 렌더러
def _set_run(run, text, *, font, size, color, bold=False):
    """
    run 의 글꼴·크기·색·볼드를 한 번에.

    🔴 볼드는 폰트 웨이트로 표현하는 것이 원칙 (Samsung SS 는 웨이트별
    독립 패밀리로 등록됨). bold=True 는 폰트 이름을 'Bold' 로 승격시킨다.
    """
    run.text = text
    f = run.font
    if bold and 'Bold' not in font:
        # 폰트 이름에 Bold 승격
        if font.endswith(' Regular'):
            font = font[:-8] + ' Bold'
        elif font.endswith(' Light') or font.endswith(' Medium'):
            font = font.rsplit(' ', 1)[0] + ' Bold'
        else:
            font = font + ' Bold'
    f.name = font
    f.size = size
    f.color.rgb = color
    f.bold = False  # 항상 웨이트로 처리, PPT bold 플래그 사용 금지 (Rule Book)


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
    """도형 하나 그리고 채움·선 색 지정."""
    sh = slide.shapes.add_shape(shape, Cm(left_cm), Cm(top_cm),
                                Cm(w_cm), Cm(h_cm))
    sh.fill.solid()
    sh.fill.fore_color.rgb = fill_rgb
    if line_rgb is None:
        sh.line.fill.background()   # 선 없음
    else:
        sh.line.color.rgb = line_rgb
        sh.line.width = Pt(line_pt)
    # 도형에 딸린 텍스트프레임의 기본 여백만 정리
    sh.text_frame.margin_left = sh.text_frame.margin_right = Cm(0.1)
    sh.text_frame.margin_top = sh.text_frame.margin_bottom = Cm(0.05)
    return sh


# ─────────────────── 마스터: 좌상단 브랜딩 그룹
def draw_master_logo(slide, doc_title: str, section: str = ''):
    """
    좌상단 브랜딩 영역 (표본 90% 반복 위치 그대로).
    표본은 로고 이미지 그룹이지만, 우리는 이미지 자산이 없으므로
    같은 좌표에 타이포그래피로 스타일라이즈한다.
    """
    box = add_text_box(slide, Master.LOGO_LEFT_CM + 0.3, Master.LOGO_TOP_CM,
                       Master.LOGO_W_CM, Master.LOGO_H_CM, anchor='middle')
    tf = box.text_frame
    _set_run(tf.paragraphs[0].add_run(), doc_title,
             font=Font.HEAD_BOLD, size=Pt(12), color=Palette.INK_STRONG)
    if section:
        p = tf.add_paragraph()
        _set_run(p.add_run(), section,
                 font=Font.BODY_REGULAR, size=Pt(8), color=Palette.INK_MUTED)


# ─────────────────── 마스터: 제목 바
def draw_title_bar(slide, title_text: str):
    """
    슬라이드 제목 (표본: 0.7, 3.1, 32.4×1.5).
    좌측에 얇은 액센트 바 + 제목 텍스트.
    """
    # 좌측 액센트 바
    add_filled_rect(slide,
                    Master.TITLE_LEFT_CM, Master.TITLE_TOP_CM + 0.15,
                    0.15, Master.TITLE_H_CM - 0.3,
                    Palette.ACCENT)
    # 제목 텍스트
    box = add_text_box(slide, Master.TITLE_LEFT_CM + 0.4, Master.TITLE_TOP_CM,
                       Master.TITLE_W_CM - 0.4, Master.TITLE_H_CM,
                       anchor='middle')
    _set_run(box.text_frame.paragraphs[0].add_run(), title_text,
             font=Font.HEAD_BOLD, size=Size.TITLE, color=Palette.INK_STRONG)


# ─────────────────── 마스터: 부제(리드 문장)
def draw_lead(slide, lead_text: str):
    box = add_text_box(slide, Master.LEAD_LEFT_CM, Master.LEAD_TOP_CM,
                       Master.LEAD_W_CM, Master.LEAD_H_CM, anchor='top')
    tf = box.text_frame
    for i, line in enumerate(lead_text.split('\n')):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        _set_run(p.add_run(), line,
                 font=Font.BODY_REGULAR, size=Size.SUBTITLE,
                 color=Palette.INK)


# ─────────────────── 마스터: 페이지 번호
def draw_page_no(slide, page: int, total: int):
    box = add_text_box(slide, Master.PAGENO_LEFT_CM, Master.PAGENO_TOP_CM,
                       Master.PAGENO_W_CM, Master.PAGENO_H_CM,
                       anchor='middle', align='right')
    _set_run(box.text_frame.paragraphs[0].add_run(),
             f'{page:02d} / {total:02d}',
             font=Font.BODY_REGULAR, size=Size.CAPTION,
             color=Palette.INK_MUTED)


def apply_masters(slide, *, doc_title: str, section: str, page: int, total: int,
                  title: str, lead: str = ''):
    """정적 마스터 4종을 한 번에 얹는다. 슬라이드 빌더에서 호출."""
    draw_master_logo(slide, doc_title, section)
    draw_title_bar(slide, title)
    if lead:
        draw_lead(slide, lead)
    draw_page_no(slide, page, total)
