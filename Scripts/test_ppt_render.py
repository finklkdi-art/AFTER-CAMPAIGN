# -*- coding: utf-8 -*-
"""
Stage 4 단독 렌더 테스트 — 표본 PPTX의 디자인 시스템을 그대로 재현한다.

리빌드 방침 (사용자 지시 2026.09.04)
  · 좌표를 개별 슬라이드마다 외우지 않음. 표본 정밀 분석에서 뽑아낸
    마스터·그리드·팔레트를 `utils.report.design_spec` 상수로 승격해 사용.
  · 데이터의 양이 바뀌어도 본문 그리드가 스스로 균등 분할되도록 배치.
  · 모든 텍스트 폰트는 Samsung SS Head/Body KR 만 사용
    (표본의 SamsungOneKoreanOTF 를 웨이트별로 매핑).

실행
  cd C:\\Users\\CHEIL\\desktop\\ax3bb
  python Scripts/test_ppt_render.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# 프로젝트 루트에서 실행되도록 경로 세팅
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
SCRIPTS = PROJECT_ROOT / 'Scripts'
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from pptx import Presentation                                    # noqa: E402
from pptx.util import Cm, Pt, Emu                                # noqa: E402
from pptx.enum.shapes import MSO_SHAPE                           # noqa: E402
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR                  # noqa: E402
from pptx.oxml.ns import qn                                      # noqa: E402
from lxml import etree                                           # noqa: E402

from utils.report import theme as T                              # noqa: E402
from utils.report.design_spec import (                           # noqa: E402
    SLIDE_W_CM, SLIDE_H_CM, _cm,
    Body, Font, Palette, Size,
    apply_masters, add_filled_rect, add_text_box, _set_run,
)


# ═══════════════════════════ Mock Data (파서가 이미 뽑았다고 가정)

DOC_TITLE = '2025 Infinite AI 무풍 시스템에어컨'
DOC_SECTION = '캠페인 결과보고'
CATEGORY = '에어컨'
DATE = '260904'

CHECKLIST = [
    ('warning', "제안서에 명시된 '카카오 비즈보드'가 실집행 데일리리포트에 없음",
     '제안 단계 배정 예산 5,000만원. 집행 취소 여부와 대체 매체 확인 필요.'),
    ('error', "'Click' 지표 달성률 87.5% — 목표 대비 하회",
     '목표 250만 클릭 대비 실적 218.7만 (-12.5%). 원인 분석 코멘트 필요.'),
]

# 로드맵: 매체 × 소재 × 기간 (본문 그리드가 자동 배치)
ROADMAP_LINES = [
    ('YouTube',   'Trueview Instream · 메인 티저 30s', 'Phase 1', '04-21 ~ 05-20'),
    ('YouTube',   'Bumper · 메인 티저 6s',             'Phase 1', '04-21 ~ 05-20'),
    ('Meta',      'Reels · 기능 소개 15s',             'Phase 2', '05-15 ~ 06-30'),
    ('Meta',      'Feed · 라이프컷 이미지 4종',         'Phase 2', '05-15 ~ 06-30'),
    ('네이버 GFA', 'Smart Channel · 가격 소구 이미지',   'Phase 3', '06-01 ~ 07-19'),
    ('네이버 GFA', '검색 SA · 검색어 대응 문안',         'Phase 3', '06-01 ~ 07-19'),
]

# 매체 성과 표 (자동 열 수 계산)
MEDIA_HEADERS = ['매체', '집행 금액', '노출', '조회', '클릭', 'VTR', 'CTR', 'CPV']
MEDIA_ROWS = [
    ['YouTube',    '1.60억', '76,812,004', '39,120,884', '640,112', '50.9%', '0.83%', '4.09원'],
    ['Meta',       '1.48억', '62,411,002', '32,988,120', '812,007', '52.9%', '1.30%', '4.49원'],
    ['네이버 GFA',  '1.69억', '48,369,425', '21,106,876', '735,324', '43.6%', '1.52%', '8.01원'],
    ['Total',      '4.77억', '187,592,431','93,215,880', '2,187,443','49.7%','1.17%', '5.11원'],
]

INSIGHTS = [
    ('YouTube VTR 우위',
     'YouTube VTR 50.9% — 캠페인 평균 대비 1.03배 상회',
     '영상 라인 예산 비중 유지 후 확대 검토',
     ['VTR 50.9% (평균 49.7%)', 'CPV 4.09원 (평균 대비 -20%)']),
    ('Meta CTR 최상',
     'Meta CTR 1.30% — 3개 매체 중 최상',
     '유입 목적 예산 비중 상향 검토',
     ['Meta CTR 1.30% · YouTube 0.83%', 'CPC 182원 (매체 중 최저)']),
]

LESSONS = [
    'Bumper 6s 대비 30s 소재의 CPM 32% 우위 — 짧은 러닝타임 조합의 효율 확보',
    'Meta Reels 라인 기간 후반 클릭율 상승세 — 리테일 시즌 예산 상향 검토의 필요',
    '네이버 GFA 검색 SA 라인 CPC 급등 (기간 대비 1.6배) — 경쟁강도 모니터링 권고',
]

STRATEGIES = [
    ('매체 운영', 'YouTube Trueview + Bumper 조합의 예산 비중 상향',
     'VTR 50.9% (평균 대비 +1.2%p) · CPV 4.09원 우위'),
    ('타겟팅', 'Meta Reels 리테일 시즌 진입 시 예산 상향',
     '기간 후반 CTR 상승세 · CPC 182원 최저'),
    ('예산 배분', '네이버 GFA 검색 SA 라인 경쟁강도 상시 모니터링',
     '기간 대비 CPC 1.6배 급등 확인'),
]

TOTAL_SLIDES = 4


# ═══════════════════════════ 슬라이드 1 — Checklist

def slide_checklist(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])   # blank
    apply_masters(slide, doc_title=DOC_TITLE, section=DOC_SECTION,
                  page=1, total=TOTAL_SLIDES,
                  title='[Checklist] 사람이 확인할 예외 항목',
                  lead='기획자 확인 필요 사항 요약 — 최종 보고 전 반드시 처리')

    # 본문: 항목 수에 맞춰 세로 균등 분할
    rows = Body.rows(len(CHECKLIST) + 1, gap_cm=0.3)   # +1: 여백용
    for (severity, headline, detail), (top, height) in zip(CHECKLIST, rows):
        color = {'error': Palette.ALERT,
                 'warning': Palette.WARN,
                 'info': Palette.OK}[severity]

        # 좌측 상태 밴드
        add_filled_rect(slide, Body.LEFT_CM, top, 0.25, height, color)

        # 카드 배경
        add_filled_rect(slide, Body.LEFT_CM + 0.35, top,
                        Body.width_cm() - 0.35, height,
                        Palette.NEUTRAL_BG, line_rgb=Palette.BORDER)

        # 헤드라인 + 상세
        box = add_text_box(slide, Body.LEFT_CM + 0.7, top + 0.15,
                           Body.width_cm() - 1.0, height - 0.3, anchor='top')
        tf = box.text_frame
        # 상태 라벨
        p0 = tf.paragraphs[0]
        _set_run(p0.add_run(), f'[{severity.upper()}]  ',
                 font=Font.BODY_BOLD, size=Size.BODY, color=color)
        _set_run(p0.add_run(), headline,
                 font=Font.BODY_BOLD, size=Size.BODY, color=Palette.INK_STRONG)
        # 상세
        p1 = tf.add_paragraph()
        _set_run(p1.add_run(), detail,
                 font=Font.BODY_REGULAR, size=Size.SMALL,
                 color=Palette.INK_MUTED)


# ═══════════════════════════ 슬라이드 2 — 캠페인 기간·매체·소재 로드맵

def slide_roadmap(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    apply_masters(slide, doc_title=DOC_TITLE, section=DOC_SECTION,
                  page=2, total=TOTAL_SLIDES,
                  title='캠페인 기간·매체·소재 집행 로드맵',
                  lead='Phase 별 2단계 구성 · 총 3개 매체 6개 소재 라인 병행')

    # 헤더 (좌: 매체·소재 · 우: 3구간 기간 축)
    header_h = 0.7
    label_col_w = 11.0
    period_col_w = Body.width_cm() - label_col_w
    header_top = Body.TOP_CM

    # 라벨 헤더
    add_filled_rect(slide, Body.LEFT_CM, header_top, label_col_w, header_h,
                    Palette.FILL_STRONG)
    box = add_text_box(slide, Body.LEFT_CM + 0.3, header_top,
                       label_col_w - 0.3, header_h, anchor='middle')
    _set_run(box.text_frame.paragraphs[0].add_run(),
             '매체 · 소재 라인',
             font=Font.BODY_BOLD, size=Size.SMALL,
             color=RGBColor_white_for_header())

    # 기간 헤더 (Apr / May / Jun / Jul 4개월 격자)
    months = ['4월', '5월', '6월', '7월']
    month_w = period_col_w / len(months)
    for i, m in enumerate(months):
        L = Body.LEFT_CM + label_col_w + i * month_w
        add_filled_rect(slide, L, header_top, month_w, header_h,
                        Palette.BAND_LIGHT, line_rgb=Palette.BORDER)
        box = add_text_box(slide, L, header_top, month_w, header_h,
                           anchor='middle', align='center')
        _set_run(box.text_frame.paragraphs[0].add_run(), m,
                 font=Font.BODY_BOLD, size=Size.SMALL, color=Palette.INK)

    # 본문 로드맵 행 (매체·소재 별로 자동 균등 분배)
    body_top = header_top + header_h + 0.15
    remaining_h = Body.BOTTOM_CM - body_top
    row_h = remaining_h / len(ROADMAP_LINES)

    # 기간 문자열 → 월 위치 매핑 헬퍼
    def month_to_ratio(mm_dd: str) -> float:
        m, d = mm_dd.strip().split('-')
        return (int(m) - 4) + (int(d) - 1) / 30.0    # 4월=0

    for i, (media, creative, phase, period_raw) in enumerate(ROADMAP_LINES):
        top = body_top + i * row_h
        # 라벨 셀
        bg = Palette.NEUTRAL_BG if i % 2 == 0 else RGBColor_from_hex('FFFFFF')
        add_filled_rect(slide, Body.LEFT_CM, top, label_col_w, row_h,
                        bg, line_rgb=Palette.BORDER)
        box = add_text_box(slide, Body.LEFT_CM + 0.3, top + 0.1,
                           label_col_w - 0.4, row_h - 0.2, anchor='middle')
        tf = box.text_frame
        _set_run(tf.paragraphs[0].add_run(), media,
                 font=Font.BODY_BOLD, size=Size.SMALL, color=Palette.INK_STRONG)
        p = tf.add_paragraph()
        _set_run(p.add_run(), f'{phase} · {creative}',
                 font=Font.BODY_LIGHT, size=Size.ANNOT, color=Palette.INK_MUTED)

        # 기간 격자 배경
        for j in range(len(months)):
            L = Body.LEFT_CM + label_col_w + j * month_w
            add_filled_rect(slide, L, top, month_w, row_h,
                            bg, line_rgb=Palette.BORDER)

        # 간트 바 (기간에 비례)
        p_start, p_end = period_raw.split(' ~ ')
        r_start = month_to_ratio(p_start)
        r_end = month_to_ratio(p_end)
        bar_left = Body.LEFT_CM + label_col_w + (r_start / len(months)) * period_col_w
        bar_w = ((r_end - r_start) / len(months)) * period_col_w
        add_filled_rect(slide, bar_left, top + row_h * 0.25,
                        bar_w, row_h * 0.5, Palette.ACCENT_SOFT,
                        shape=MSO_SHAPE.ROUNDED_RECTANGLE)

        # 기간 텍스트
        box = add_text_box(slide, bar_left, top + row_h * 0.25,
                           bar_w, row_h * 0.5, anchor='middle', align='center')
        _set_run(box.text_frame.paragraphs[0].add_run(), period_raw,
                 font=Font.BODY_BOLD, size=Size.ANNOT, color=Palette.INK_STRONG)


# ═══════════════════════════ 슬라이드 3 — 매체 성과 (표) + 인사이트

def slide_media_and_insight(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    apply_masters(slide, doc_title=DOC_TITLE, section=DOC_SECTION,
                  page=3, total=TOTAL_SLIDES,
                  title='매체별 집행 성과 및 인사이트',
                  lead='매체 3종 실집행 실적 및 축별 도출 시사점')

    # ── 좌: 매체 성과 표 (본문 폭의 60%)
    table_w = Body.width_cm() * 0.62
    table_left = Body.LEFT_CM
    table_top = Body.TOP_CM

    # 행 높이는 theme 의 사다리에서 고른다 — 임의 높이를 쓰면 실측 규격
    # (8행 이하 0.403in) 을 벗어난다.
    n_rows = len(MEDIA_ROWS) + 1
    row_h_cm = _cm(T.row_height_for(n_rows))
    table_h = row_h_cm * n_rows
    n_cols = len(MEDIA_HEADERS)
    tbl_shape = slide.shapes.add_table(
        n_rows, n_cols, Cm(table_left), Cm(table_top),
        Cm(table_w), Cm(table_h))
    tbl = tbl_shape.table

    # 열 폭: 첫 열 넓게, 나머지 균등
    first_col_w = 3.0
    other_w = (table_w - first_col_w) / (n_cols - 1)
    tbl.columns[0].width = Cm(first_col_w)
    for i in range(1, n_cols):
        tbl.columns[i].width = Cm(other_w)

    def style_cell(cell, text, *, header=False, total=False):
        # 헤더는 옅게(검정 글자), 합계는 진하게(흰 글자) — 실측 규격.
        # 통합 전에는 이 둘이 반대였다: 헤더가 진한 파랑에 흰 글자,
        # 합계가 옅은 하늘색. 17열까지 늘어나는 표에서 진한 헤더는
        # 잉크를 먹고 수치 가독성을 떨어뜨린다 (design-system §6).
        cell.margin_left = cell.margin_right = Cm(0.1)
        cell.margin_top = cell.margin_bottom = Cm(0.05)
        cell.fill.solid()
        if header:
            cell.fill.fore_color.rgb = Palette.TBL_HEAD
        elif total:
            cell.fill.fore_color.rgb = Palette.TOTAL_ROW
        else:
            cell.fill.fore_color.rgb = Palette.WHITE

        if header:
            face, color = Font.HEAD_MEDIUM, Palette.INK_STRONG
        elif total:
            face, color = Font.HEAD_MEDIUM, Palette.WHITE
        else:
            face, color = Font.BODY_REGULAR, Palette.INK_STRONG

        tf = cell.text_frame
        tf.paragraphs[0].alignment = PP_ALIGN.LEFT if header else PP_ALIGN.RIGHT
        _set_run(tf.paragraphs[0].add_run(), text,
                 font=face, size=Size.SMALL, color=color)

    # 헤더
    for j, h in enumerate(MEDIA_HEADERS):
        c = tbl.cell(0, j)
        c.text = ''   # 초기화
        style_cell(c, h, header=True)
        c.text_frame.paragraphs[0].alignment = (
            PP_ALIGN.LEFT if j == 0 else PP_ALIGN.RIGHT)

    # 데이터 행
    for i, row in enumerate(MEDIA_ROWS, 1):
        is_total = (row[0] == 'Total')
        for j, val in enumerate(row):
            c = tbl.cell(i, j)
            c.text = ''
            style_cell(c, val, total=is_total)
            c.text_frame.paragraphs[0].alignment = (
                PP_ALIGN.LEFT if j == 0 else PP_ALIGN.RIGHT)

    # ── 우: 인사이트 카드 (표 우측 세로 스택)
    card_left = table_left + table_w + 0.5
    card_w = Body.LEFT_CM + Body.width_cm() - card_left
    n_cards = len(INSIGHTS)
    card_gap = 0.3
    card_h = (table_h - card_gap * (n_cards - 1)) / n_cards

    for i, (tag, finding, reco, evidence) in enumerate(INSIGHTS):
        top = table_top + i * (card_h + card_gap)
        # 카드 배경
        add_filled_rect(slide, card_left, top, card_w, card_h,
                        Palette.NEUTRAL_BG, line_rgb=Palette.BORDER)
        # 상단 액센트 바
        add_filled_rect(slide, card_left, top, card_w, 0.35, Palette.ACCENT)
        box = add_text_box(slide, card_left + 0.2, top,
                           card_w - 0.4, 0.35, anchor='middle')
        _set_run(box.text_frame.paragraphs[0].add_run(), tag,
                 font=Font.BODY_BOLD, size=Size.ANNOT,
                 color=RGBColor_white_for_header())

        # 발견 / 제안 / 근거
        body = add_text_box(slide, card_left + 0.3, top + 0.5,
                            card_w - 0.6, card_h - 0.7, anchor='top')
        tf = body.text_frame
        _set_run(tf.paragraphs[0].add_run(), '[발견] ' + finding,
                 font=Font.BODY_BOLD, size=Size.SMALL,
                 color=Palette.INK_STRONG)
        p = tf.add_paragraph()
        _set_run(p.add_run(), '[제안] ' + reco,
                 font=Font.BODY_REGULAR, size=Size.SMALL,
                 color=Palette.ACCENT)
        for ev in evidence:
            p = tf.add_paragraph()
            _set_run(p.add_run(), '· ' + ev,
                     font=Font.BODY_LIGHT, size=Size.ANNOT,
                     color=Palette.INK_MUTED)

    # 자료원 캡션 (하단)
    box = add_text_box(slide, Body.LEFT_CM, Body.BOTTOM_CM - 0.5,
                       Body.width_cm(), 0.4, anchor='middle')
    _set_run(box.text_frame.paragraphs[0].add_run(),
             '※ 자료원: 데일리리포트_비스포크AI무풍콤보_0813.xlsx <매체별 Total>',
             font=Font.BODY_LIGHT, size=Size.CAPTION,
             color=Palette.INK_MUTED)


# ═══════════════════════════ 슬라이드 4 — Lesson Learned + 차기 전략

def slide_lesson_strategy(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    apply_masters(slide, doc_title=DOC_TITLE, section=DOC_SECTION,
                  page=4, total=TOTAL_SLIDES,
                  title='Lesson Learned 및 차기 캠페인 전략',
                  lead='포스트바이 원문 기반 학습 사항 · 차기 캠페인 3영역 액션')

    # 상하 2단 분할
    top_rows = Body.rows(2, gap_cm=0.5)
    lesson_top, lesson_h = top_rows[0]
    strat_top, strat_h = top_rows[1]

    # ── 상단: Lesson Learned (좌측 액센트 + Bullet)
    add_filled_rect(slide, Body.LEFT_CM, lesson_top, 0.25, lesson_h,
                    Palette.ACCENT)
    box = add_text_box(slide, Body.LEFT_CM + 0.5, lesson_top,
                       Body.width_cm() - 0.5, 0.7, anchor='top')
    _set_run(box.text_frame.paragraphs[0].add_run(),
             'LESSON LEARNED',
             font=Font.HEAD_BOLD, size=Size.HEADLINE,
             color=Palette.INK_STRONG)

    body = add_text_box(slide, Body.LEFT_CM + 0.5, lesson_top + 0.9,
                        Body.width_cm() - 0.5, lesson_h - 0.9, anchor='top')
    tf = body.text_frame
    for i, ln in enumerate(LESSONS):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(6)
        _set_run(p.add_run(), '· ',
                 font=Font.BODY_BOLD, size=Size.BODY, color=Palette.ACCENT)
        _set_run(p.add_run(), ln,
                 font=Font.BODY_REGULAR, size=Size.BODY, color=Palette.INK)

    # ── 하단: 차기 전략 (3-card 자동 균등)
    box = add_text_box(slide, Body.LEFT_CM + 0.5, strat_top,
                       Body.width_cm() - 0.5, 0.7, anchor='top')
    _set_run(box.text_frame.paragraphs[0].add_run(),
             '차기 캠페인 전략',
             font=Font.HEAD_BOLD, size=Size.HEADLINE,
             color=Palette.INK_STRONG)

    cards_top = strat_top + 0.9
    cards_h = strat_h - 0.9
    cols = Body.columns(len(STRATEGIES), gap_cm=0.5)

    for (left, width), (area, direction, basis) in zip(cols, STRATEGIES):
        # 카드
        add_filled_rect(slide, left, cards_top, width, cards_h,
                        Palette.NEUTRAL_BG, line_rgb=Palette.BORDER)
        # 상단 area 태그
        add_filled_rect(slide, left, cards_top, width, 0.7,
                        Palette.FILL_STRONG)
        box = add_text_box(slide, left, cards_top, width, 0.7,
                           anchor='middle', align='center')
        _set_run(box.text_frame.paragraphs[0].add_run(), area,
                 font=Font.BODY_BOLD, size=Size.SUBTITLE,
                 color=RGBColor_white_for_header())

        # 방향
        box = add_text_box(slide, left + 0.3, cards_top + 0.9,
                           width - 0.6, cards_h - 1.0, anchor='top')
        tf = box.text_frame
        _set_run(tf.paragraphs[0].add_run(), direction,
                 font=Font.BODY_BOLD, size=Size.BODY,
                 color=Palette.INK_STRONG)
        # 근거
        p = tf.add_paragraph()
        p.space_before = Pt(6)
        _set_run(p.add_run(), '근거 · ' + basis,
                 font=Font.BODY_LIGHT, size=Size.SMALL,
                 color=Palette.INK_MUTED)


# ═══════════════════════════ 색 헬퍼 (짧게 재활용)

def RGBColor_from_hex(h: str):
    from pptx.dml.color import RGBColor
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def RGBColor_white_for_header():
    return RGBColor_from_hex('FFFFFF')


# ═══════════════════════════ 실행

def main() -> int:
    prs = Presentation()
    prs.slide_width = Cm(SLIDE_W_CM)
    prs.slide_height = Cm(SLIDE_H_CM)

    slide_checklist(prs)
    slide_roadmap(prs)
    slide_media_and_insight(prs)
    slide_lesson_strategy(prs)

    filename = f'{DATE}_{CATEGORY}_결과리포트_v0_Cheil.pptx'
    out_dir = PROJECT_ROOT / 'Output' / f'{DATE}_{DOC_TITLE}'
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / filename
    v = 0
    while out_path.exists():
        v += 1
        out_path = out_dir / f'{DATE}_{CATEGORY}_결과리포트_v{v}_Cheil.pptx'

    prs.save(str(out_path))
    kb = out_path.stat().st_size // 1024

    print('=' * 62)
    print(f'PPTX 생성 완료 — {len(prs.slides)}장 · {kb} KB')
    print(f'  {out_path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
