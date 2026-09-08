# -*- coding: utf-8 -*-
"""
레이아웃 영역 침범 검사 — 미리보기 카드 · 산출물 좌표

    python Scripts/test_layout_overlap.py

미리보기 카드는 요소를 **절대 좌표**로 얹는다. 이 방식에서 두 가지가 겹침을
만들었고, 둘 다 실제로 제보됐다.

  ① 높이 없는 블록 — 표가 길어지자 아래 각주 위로 자랐다.
  ② 고정 px 카드 — `width:560px` 카드가 그보다 좁은 Streamlit 칼럼에 들어가자
     오른쪽 '문안 수정' 패널을 덮었다.

②를 고치며 좌표를 전부 **카드 대비 %** 로 바꿨다. 덕분에 이 검사도 강해졌다 —
비율 좌표는 카드가 어떤 크기든 상대 관계가 같으므로, **한 번만 확인하면 모든
폭에서 성립한다.** (px 시절엔 폭마다 따로 확인해야 했다.)

함께 보는 것
  · 위치를 가진 블록에 높이가 있는가 (없으면 = 침범 가능 상태)
  · 세로로 겹치는 블록 쌍이 있는가
  · 카드(0~100%) 밖으로 나가는 블록이 있는가
  · 카드 자체가 담긴 칼럼을 넘지 않게 되어 있는가 (고정 px 폭 금지)
  · 산출물(PPTX) 좌표 상수끼리 애초에 겹치게 정의돼 있지는 않은가
"""

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from utils import slide_preview as SP            # noqa: E402
from utils.report import theme as TH             # noqa: E402
from utils.report.blocks import SlideSpec        # noqa: E402

# 세로로 겹치면 안 되는 블록 — 같은 x 대역을 위아래로 나눠 쓴다
_STACK = ('sp-tag', 'sp-sec', 'sp-key', 'sp-body', 'sp-foot')
# 높이를 반드시 가져야 하는 블록 (내용이 길어질 수 있는 것들)
_MUST_HAVE_HEIGHT = ('sp-key', 'sp-body', 'sp-foot')

_DIV_RE = re.compile(r'<div class="([^"]+)" style="([^"]*)"')
_PCT = re.compile(r'(-?[\d.]+)%')


def _boxes(html: str):
    """미리보기 HTML → {클래스: (top%, height% 또는 None)}"""
    out = {}
    for cls, style in _DIV_RE.findall(html):
        key = next((c for c in _STACK if c in cls.split()), None)
        if key is None:
            continue
        top = height = None
        for prop, val in re.findall(r'([a-z-]+)\s*:\s*([^;]+)', style):
            m = _PCT.search(val)
            if not m:
                continue
            if prop == 'top':
                top = float(m.group(1))
            elif prop == 'height':
                height = float(m.group(1))
        if top is not None:
            out[key] = (top, height)
    return out


def _card_style(html: str) -> str:
    m = re.search(r'<div class="sp-slide" style="([^"]*)"', html)
    return m.group(1) if m else ''


CASES = [
    ('표 20행', SlideSpec('media_table', {
        'section': '매체별 집행 결과',
        'headline_parts': [{'text': 'Digital 9개 매체 집행 결과'}],
        'header': ['매체', '집행 비용(원)', '노출(회)', '조회(회)', '클릭(회)',
                   'VTR', 'CTR', 'CPM(원)', 'CPC(원)'],
        'rows': [[f'매체{i}', f'{i*1000000:,}', f'{i*99999:,}', f'{i*777:,}',
                  f'{i*55:,}', f'{i}%', f'0.{i}%', f'{i*11:,}', f'{i*3:,}']
                 for i in range(20)],
        'sources': ['자료원: 데일리리포트_25년_시스템에어컨캠페인(Phase1,2통합).xlsx '
                    '<일자별 통합> · 매체별 Total'],
    })),
    ('아주 긴 헤드라인', SlideSpec('media_table', {
        'section': '매체별 집행 결과',
        'headline_parts': [{'text': '아주 긴 키메시지 ' * 30}],
        'header': ['매체', '노출'], 'rows': [['유튜브', '1,000']],
        'sources': ['자료원: 테스트'],
    })),
    ('불릿 20줄', SlideSpec('lesson', {
        'section': 'Lesson Learned',
        'bullets': [f'{i}. 매우 긴 제언 문장입니다 ' * 4 for i in range(20)],
        'sources': ['자료원: 포스트바이'],
    })),
    ('빈 본문', SlideSpec('lesson', {
        'section': '빈 장', 'bullets': [], 'sources': ['자료원: 없음'],
    })),
    ('표지(hero)', SlideSpec('cover', {'title': '2025 캠페인 결과 보고'})),
]

# 실제 호출부가 쓰는 최대 폭 (썸네일 / 상세)
WIDTHS = (300, 560)


def check_preview() -> list:
    problems = []
    for width in WIDTHS:
        for label, slide in CASES:
            html = SP.slide_html(slide, '2025 테스트 캠페인',
                                 width=width, index=1)
            tag = f'[{width}px/{label}]'

            # ── 카드가 담긴 칼럼을 넘지 않게 되어 있는가
            style = _card_style(html)
            if re.search(r'(?<!max-)width\s*:\s*\d+px', style):
                problems.append(
                    f'{tag} 카드에 고정 px 폭이 박혀 있어요 — '
                    f'좁은 칼럼에서 옆 영역을 덮습니다 ({style})')
            if 'max-width' not in style:
                problems.append(f'{tag} 카드에 max-width 상한이 없어요')

            boxes = _boxes(html)

            # ── 높이 없는 블록 = 다음 영역을 침범할 수 있는 블록
            for key, (_, height) in boxes.items():
                if key in _MUST_HAVE_HEIGHT and height is None:
                    problems.append(
                        f'{tag} {key} 에 높이가 없어 아래 영역을 침범할 수 있어요')

            # ── 실제로 겹치는가 (비율 좌표라 폭과 무관하게 성립)
            order = [k for k in _STACK if k in boxes]
            for a, b in zip(order, order[1:]):
                ta, ha = boxes[a]
                tb, _ = boxes[b]
                if ha is None:
                    continue
                if ta + ha > tb + 0.01:
                    problems.append(
                        f'{tag} {a}(끝 {ta + ha:.2f}%) 가 '
                        f'{b}(시작 {tb:.2f}%) 를 침범')

            # ── 카드 밖으로 나가는가
            for key, (top, height) in boxes.items():
                end = top + (height or 0)
                if end > 100.01:
                    problems.append(
                        f'{tag} {key} 가 카드 아래로 {end - 100:.2f}% 넘침')
    return problems


def check_theme_constants() -> list:
    """산출물 좌표 상수끼리 애초에 겹치게 정의돼 있지 않은가."""
    problems = []
    key_y, key_h = TH.KEY_POS[1], TH.KEY_POS[3]
    if key_y + key_h > TH.CONTENT_Y + 1e-6:
        problems.append(
            f'KEY_POS(끝 {key_y + key_h:.2f}in) 가 '
            f'CONTENT_Y({TH.CONTENT_Y:.2f}in) 를 침범')
    if TH.CONTENT_Y >= TH.FOOT_Y:
        problems.append('CONTENT_Y 가 FOOT_Y 보다 아래')
    if TH.FOOT_Y >= TH.SLIDE_H:
        problems.append('FOOT_Y 가 슬라이드 높이를 벗어남')

    # 헤더 3단 — 태그 → 괘선 → 셰브런 플래그가 서로/키메시지를 침범하지 않는가
    # (2026.09.09 — ■ 사각 SEC_SQ 를 셰브런 플래그로 교체하며 함께 개정)
    tag_y, tag_h = TH.TAG_POS[1], TH.TAG_POS[3]
    rule_y = TH.RULE_POS[1]
    flag_y, flag_h = TH.FLAG_POS[1], TH.FLAG_POS[3]
    if tag_y + tag_h > rule_y + 1e-6:
        problems.append(
            f'TAG_POS(끝 {tag_y + tag_h:.2f}in) 가 RULE_POS({rule_y:.2f}in) 를 침범')
    if flag_y + flag_h > key_y + 1e-6:
        problems.append(
            f'FLAG_POS(끝 {flag_y + flag_h:.2f}in) 가 KEY_POS({key_y:.2f}in) 를 침범')

    # 키메시지는 캔버스 중앙에 놓여야 한다 (4개 덱 68/72 슬라이드의 규칙)
    center = TH.KEY_POS[0] + TH.KEY_POS[2] / 2
    if abs(center - TH.SLIDE_W / 2) > 0.02:
        problems.append(
            f'KEY_POS 중심({center:.3f}in) 이 캔버스 중심'
            f'({TH.SLIDE_W / 2:.3f}in) 과 어긋남')

    # 표 행 높이 사다리는 내림차순이어야 한다 (넘칠 때 단계적으로 낮추는 용도)
    ladder = list(TH.ROW_H_LADDER)
    if ladder != sorted(ladder, reverse=True):
        problems.append('ROW_H_LADDER 가 내림차순이 아님')
    return problems


def main() -> int:
    problems = check_theme_constants() + check_preview()
    checked = len(WIDTHS) * len(CASES)
    if problems:
        print(f'영역 침범 {len(problems)}건 (검사 {checked}조합)\n')
        for p in problems:
            print('  - ' + p)
        return 1
    print(f'통과 — 미리보기 {checked}조합(비율 좌표라 모든 폭에서 성립) · '
          f'산출물 좌표 상수, 영역 침범 없음')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
