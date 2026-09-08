# -*- coding: utf-8 -*-
"""
레이아웃 영역 침범 검사 — 미리보기 카드 · 산출물 좌표

    python Scripts/test_layout_overlap.py

미리보기는 모든 요소를 **절대 좌표**로 얹는다. 이 방식에서 높이를 주지 않으면
내용이 길어질 때 다음 영역 위로 자라는 게 기본 동작이다. 실제로 행이 많은 표가
자료원 각주를 덮는 일이 있었다(2026-09-08 제보).

그래서 두 가지를 본다.
  1. 미리보기 HTML 이 실제로 만들어 낸 블록들의 사각형이 겹치지 않는가
  2. 산출물(PPTX) 레이아웃 상수끼리 애초에 겹치게 정의돼 있지는 않은가

폭을 하나만 보지 않는다 — 썸네일(300px)과 상세(560px)는 글자 크기 하한
때문에 비율이 달라서, 한쪽에서만 겹치는 경우가 생긴다.
"""

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from utils import slide_preview as SP            # noqa: E402
from utils.report import theme as TH             # noqa: E402
from utils.report.blocks import SlideSpec        # noqa: E402

# 실제로 쓰이는 폭 (썸네일 / 상세)
WIDTHS = (300, 560)

# 세로로 겹치면 안 되는 블록 쌍 — 같은 x 대역을 공유하는 것들
_STACK = ('sp-tag', 'sp-sec', 'sp-key', 'sp-body', 'sp-foot')

_DIV_RE = re.compile(
    r'<div class="([^"]+)" style="([^"]*)"', re.S)
_NUM = re.compile(r'(-?[\d.]+)px')


def _boxes(html: str):
    """미리보기 HTML → {클래스: (top, height)} (높이가 명시된 것만)"""
    out = {}
    for cls, style in _DIV_RE.findall(html):
        key = next((c for c in _STACK if c in cls.split()), None)
        if key is None:
            continue
        top = height = None
        for prop, val in re.findall(r'([a-z-]+)\s*:\s*([^;]+)', style):
            m = _NUM.search(val)
            if not m:
                continue
            if prop == 'top':
                top = float(m.group(1))
            elif prop == 'height':
                height = float(m.group(1))
        if top is not None:
            out[key] = (top, height)
    return out


def _make_slide(kind: str, payload: dict) -> SlideSpec:
    return SlideSpec(kind, payload)


# 본문이 길어지는 최악 케이스들 — 여기서 안 겹치면 실사용에서도 안 겹친다
CASES = [
    ('표 20행', _make_slide('media_table', {
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
    ('아주 긴 헤드라인', _make_slide('media_table', {
        'section': '매체별 집행 결과',
        'headline_parts': [{'text': '아주 긴 키메시지 ' * 30}],
        'header': ['매체', '노출'],
        'rows': [['유튜브', '1,000'], ['메타', '2,000']],
        'sources': ['자료원: 테스트'],
    })),
    ('불릿 20줄', _make_slide('lesson', {
        'section': 'Lesson Learned',
        'bullets': [f'{i}. 매우 긴 제언 문장입니다 ' * 4 for i in range(20)],
        'sources': ['자료원: 포스트바이'],
    })),
    ('빈 본문', _make_slide('lesson', {
        'section': '빈 장', 'bullets': [],
        'sources': ['자료원: 없음'],
    })),
]


def check_preview() -> list:
    problems = []
    for width in WIDTHS:
        for label, slide in CASES:
            html = SP.slide_html(slide, '2025 테스트 캠페인',
                                 width=width, index=1)
            boxes = _boxes(html)

            # 1) 높이가 없는 블록 = 다음 영역을 침범할 수 있는 블록
            for key, (top, height) in boxes.items():
                if key in ('sp-key', 'sp-body', 'sp-foot') and height is None:
                    problems.append(
                        f'[{width}px/{label}] {key} 에 높이가 없어 '
                        f'아래 영역을 침범할 수 있어요')

            # 2) 실제로 겹치는가
            order = [k for k in _STACK if k in boxes]
            for a, b in zip(order, order[1:]):
                ta, ha = boxes[a]
                tb, _ = boxes[b]
                if ha is None:
                    continue
                if ta + ha > tb + 0.5:          # 0.5px 반올림 여유
                    problems.append(
                        f'[{width}px/{label}] {a}(끝 {ta + ha:.0f}px) 가 '
                        f'{b}(시작 {tb:.0f}px) 를 {ta + ha - tb:.0f}px 침범')

            # 3) 카드 밖으로 나가는가
            card_h = None
            m = re.search(r'class="sp-slide" style="width:[\d.]+px;'
                          r'height:([\d.]+)px', html)
            if m:
                card_h = float(m.group(1))
            if card_h:
                for key, (top, height) in boxes.items():
                    end = top + (height or 0)
                    if end > card_h + 0.5:
                        problems.append(
                            f'[{width}px/{label}] {key} 가 카드 아래로 '
                            f'{end - card_h:.0f}px 넘침')
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
    sq_y, sq_h = TH.SEC_SQ[1], TH.SEC_SQ[3]
    if sq_y + sq_h > key_y + 1e-6:
        problems.append('SEC_SQ 가 KEY_POS 를 침범')
    return problems


def main() -> int:
    problems = check_theme_constants() + check_preview()
    checked = len(WIDTHS) * len(CASES)
    if problems:
        print(f'영역 침범 {len(problems)}건 (검사 {checked}조합)\n')
        for p in problems:
            print('  - ' + p)
        return 1
    print(f'통과 — 미리보기 {checked}조합 · 산출물 좌표 상수, 영역 침범 없음')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
