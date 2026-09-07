# -*- coding: utf-8 -*-
"""
슬라이드 미리보기 렌더러 — SlideSpec → 16:9 HTML 카드

Stage 4.5 의 썸네일 미리보기를 담당한다. PPTX 를 이미지로 변환하지 않고,
`SlideSpec` 을 산출물과 같은 좌표계(13.333 × 7.5 in)와 같은 팔레트로
HTML 에 다시 그린다.

왜 PPTX→이미지 변환을 쓰지 않는가 (2026.09.07 실측)
  · PowerPoint COM 으로 `Slide.Export` 하면 변환 자체는 0.29초/장으로 빠르나,
    **사내 DRM(NASCA)이 POWERPNT.EXE 가 쓰는 모든 파일을 암호화**한다.
    내보낸 PNG 헤더가 `<## NASCA DRM FILE` 이 되어 브라우저가 읽지 못한다.
  · 외부 변환 API(CloudConvert 류)는 claude.md 1 의 외부 전송 금지에 걸린다.
    광고주 자산이 담긴 덱 전체를 제3자에 업로드하게 되므로 채택하지 않았다.
  · DRM 우회는 `utils/drm_check.py` 의 방침대로 시도하지 않는다.
  → 결론: 변환을 하지 않고 명세에서 직접 그린다. 외부 전송 0건, 추가 의존성
    0개, 변환 지연 0초이며 문안 수정 결과가 즉시 반영된다.

한계 — 이것은 **facsimile 이지 PPTX 렌더가 아니다.**
  레이아웃 골격(태그·섹션·키메시지·본문·표·출처)과 팔레트는 산출물과 같지만,
  표 셀 폭·자동 줄바꿈·차트 도형까지 동일하지는 않다. 최종 확인은 내려받은
  PPTX 로 해야 하며, 화면에도 그 취지를 함께 표시한다.

좌표는 `utils/report/theme.py` 의 값을 단일 출처로 삼는다. 두 곳에 같은
숫자를 적어 두면 산출물만 바뀌고 미리보기는 안 바뀌는 사고가 난다.
"""

from typing import Any, Dict, List, Optional, Sequence

from .report import theme as TH

# ─────────────────────────── 지오메트리 (theme.py 에서 가져온다)
SLIDE_W_IN = TH.SLIDE_W          # 13.333
SLIDE_H_IN = TH.SLIDE_H          # 7.5
ASPECT = SLIDE_H_IN / SLIDE_W_IN

# 미리보기 크기 프리셋 — 폭(px)만 정하면 나머지는 비례로 계산된다.
SIZE_THUMB = 320
SIZE_FULL = 760


def _esc(s: Any) -> str:
    """HTML 이스케이프 — 캠페인명·매체명이 그대로 마크업에 들어가므로 필수"""
    return (str(s if s is not None else '')
            .replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


class _Scale:
    """인치 좌표 → 픽셀 변환기. 폭 하나로 전체 배율이 정해진다."""

    def __init__(self, width_px: int):
        self.w = width_px
        self.h = round(width_px * ASPECT)
        self.ppi = width_px / SLIDE_W_IN

    def x(self, inches: float) -> float:
        return round(inches * self.ppi, 2)

    y = x                                    # 등방 배율이라 축이 같다

    def pt(self, points: float, floor: float = 0) -> float:
        """
        포인트(1/72 in) → px. `floor` 아래로는 내려가지 않는다.

        배율을 그대로 따르면 320px 썸네일에서 본문 10.5pt 가 3.5px 가 되어
        글자가 아니라 얼룩이 된다. 위치·비율은 산출물과 맞추되 **글자 크기만
        가독 하한을 둔다.** 그 결과 작은 카드에서는 텍스트가 실제 덱보다
        상대적으로 커 보이지만, 슬라이드를 알아보고 고를 수 있어야 한다는
        미리보기의 목적에는 이쪽이 맞다.
        """
        return max(round(points / 72 * self.ppi, 2), floor)


# ─────────────────────────── 페이로드 해석
# 렌더러(`utils/report/renderer.py`)가 kind 별로 소비하는 키를 공통 골격으로
# 환원한다. kind 가 11 종이라 장별 전용 렌더러를 두면 산출물과 이중 관리가
# 되므로, 하나의 골격에 담고 없는 요소는 그냥 비워 둔다.

def _first_text(p: Dict[str, Any], *keys: str) -> str:
    for k in keys:
        v = p.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
        if isinstance(v, (list, tuple)) and v:
            parts = []
            for x in v:
                if isinstance(x, str):
                    parts.append(x)
                elif isinstance(x, dict):
                    parts.append(str(x.get('text') or x.get('t') or ''))
            joined = ' '.join(s for s in parts if s).strip()
            if joined:
                return joined
    return ''


# dict 항목에서 사람이 읽을 문장을 꺼낼 때 볼 키 (실측 기준).
#   checklist → message / lesson_cards → finding / 표 셀 → t
_TEXT_KEYS = ('text', 't', 'title', 'message', 'finding', 'label', 'name')


def _dict_text(x: Dict[str, Any]) -> str:
    for k in _TEXT_KEYS:
        v = x.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ''


def _bullets(p: Dict[str, Any], limit: int = 7) -> List[str]:
    """
    본문 불릿. kind 마다 담는 키가 달라 실측한 것을 모두 훑는다.

    `rows` 도 본다 — checklist 는 표가 아니라 **dict 행 목록**이라
    표로 그리면 빈 줄만 남는다.
    """
    out: List[str] = []
    for key in ('items', 'bullets', 'lines', 'cards', 'blocks',
                'quotes', 'notes', 'rows'):
        for x in (p.get(key) or []):
            if len(out) >= limit:
                return out
            if isinstance(x, str):
                if x.strip():
                    out.append(x.strip())
            elif isinstance(x, dict):
                t = _dict_text(x)
                if t:
                    mark = str(x.get('mark') or '').strip()
                    out.append(f'{mark} {t}'.strip())
    return out


def _cell(c: Any) -> str:
    if isinstance(c, dict):
        return _dict_text(c)
    return str(c if c is not None else '')


def _table(p: Dict[str, Any], max_rows: int = 6):
    """
    (헤더, 본문행들, 전체 본문 행수) 를 돌려준다.

    `media_table` 처럼 `header` 를 따로 들고 있는 kind 가 있다. 그 경우
    `rows[0]` 을 헤더로 쓰면 **데이터 한 줄이 조용히 사라진다.**
    """
    raw = p.get('rows') or []
    # dict 행(예: checklist)은 표가 아니라 목록이다. 표로 그리면 셀이 비어
    # 빈 줄만 남으므로 여기서 물러나고 불릿 경로에 맡긴다.
    if raw and not isinstance(raw[0], (list, tuple)):
        return [], [], 0
    rows = [list(r) for r in raw]
    hdr = p.get('header')
    if hdr:
        header = [_cell(c) for c in
                  (hdr if isinstance(hdr, (list, tuple)) else [hdr])][:9]
        body = rows
    elif rows:
        header = [_cell(c) for c in rows[0]][:9]
        body = rows[1:]
    else:
        return [], [], 0
    shown = [[_cell(c) for c in r][:9] for r in body[:max_rows]]
    return header, shown, len(body)


def _sources(p: Dict[str, Any]) -> str:
    src = p.get('sources') or []
    parts = [str(s) for s in src if str(s).strip()]
    if p.get('note'):
        parts.append(str(p['note']))
    return ' · '.join(parts)


# ─────────────────────────── 렌더

def slide_html(slide, campaign_tag: str = '', *,
               width: int = SIZE_THUMB, index: Optional[int] = None) -> str:
    """
    SlideSpec 한 장을 16:9 HTML 카드로 그린다.

    Args:
        slide: SlideSpec (kind / payload)
        campaign_tag: 좌상단 고정 태그 (ReportSpec.campaign_tag)
        width: 카드 폭(px). 높이와 글자 크기는 비례로 따라온다.
        index: 좌하단에 표시할 장 번호 (없으면 생략)
    """
    s = _Scale(width)
    p: Dict[str, Any] = getattr(slide, 'payload', None) or {}
    kind = getattr(slide, 'kind', '') or ''

    section = _first_text(p, 'section', 'block_label')
    # 키 이름은 kind 마다 다르다 (실측: divider=text, summary=key_parts,
    # media_table=headline_parts, cover=title). 순서대로 처음 잡히는 걸 쓴다.
    headline = _first_text(p, 'headline_parts', 'headline', 'key_parts',
                           'title', 'text', 'label')
    bullets = _bullets(p)
    head, body_rows, total_rows = _table(p)
    src = _sources(p)

    # 표지·간지는 본문 대신 제목을 크게 — 산출물의 위계를 따른다
    hero = kind in ('cover', 'divider', 'eod')

    px = lambda v: f'{v}px'                                   # noqa: E731
    parts: List[str] = [
        f'<div class="sp-slide" style="width:{px(s.w)};height:{px(s.h)}">'
    ]

    # L3a 캠페인 태그 — 작은 카드에서는 생략한다.
    # 글자 크기에 하한을 두다 보니 태그(0.28in)와 섹션 라벨(0.63in)이 서로
    # 붙어 읽히고, 모든 장에 같은 값이 반복돼 정보량도 없다.
    if campaign_tag and not hero and width >= 500:
        parts.append(
            f'<div class="sp-tag" style="left:{px(s.x(TH.TAG_POS[0]))};'
            f'top:{px(s.y(TH.TAG_POS[1]))};font-size:{px(s.pt(9, 7))}">'
            f'{_esc(campaign_tag)}</div>')

    # L3b 섹션 라벨 + ■ 액센트
    if section and not hero:
        parts.append(
            f'<div class="sp-sq" style="left:{px(s.x(TH.SEC_SQ[0]))};'
            f'top:{px(s.y(TH.SEC_SQ[1]))};width:{px(s.x(TH.SEC_SQ[2]))};'
            f'height:{px(s.y(TH.SEC_SQ[3]))}"></div>')
        parts.append(
            f'<div class="sp-sec" style="left:{px(s.x(TH.SEC_POS[0]))};'
            f'top:{px(s.y(TH.SEC_POS[1]))};font-size:{px(s.pt(11, 8.5))}">'
            f'{_esc(section)}</div>')

    # L4 키메시지
    if headline:
        if hero:
            parts.append(
                f'<div class="sp-hero" style="left:{px(s.x(1.0))};'
                f'top:{px(s.y(2.9))};width:{px(s.x(11.3))};'
                f'font-size:{px(s.pt(30, 15))}">{_esc(headline)}</div>')
        else:
            parts.append(
                f'<div class="sp-key" style="left:{px(s.x(TH.KEY_POS[0]))};'
                f'top:{px(s.y(TH.KEY_POS[1]))};width:{px(s.x(TH.KEY_POS[2]))};'
                f'font-size:{px(s.pt(17, 11))}">{_esc(headline)}</div>')

    # 본문 영역 — 표가 있으면 표, 없으면 불릿
    if not hero:
        cy = px(s.y(TH.CONTENT_Y))
        cx = px(s.x(0.63))
        cw = px(s.x(12.06))
        if head or body_rows:
            th = ''.join(f'<th>{_esc(c)}</th>' for c in head)
            tb = ''.join(
                '<tr>' + ''.join(f'<td>{_esc(c)}</td>' for c in r) + '</tr>'
                for r in body_rows)
            more = (f'<div class="sp-more">… 외 '
                    f'{total_rows - len(body_rows)}행</div>'
                    if total_rows > len(body_rows) else '')
            parts.append(
                f'<div class="sp-body" style="left:{cx};top:{cy};width:{cw};'
                f'font-size:{px(s.pt(8, 7))}">'
                f'<table class="sp-tbl"><thead><tr>{th}</tr></thead>'
                f'<tbody>{tb}</tbody></table>{more}</div>')
        elif bullets:
            lis = ''.join(f'<li>{_esc(b)}</li>' for b in bullets)
            parts.append(
                f'<div class="sp-body" style="left:{cx};top:{cy};width:{cw};'
                f'font-size:{px(s.pt(10.5, 8.5))}">'
                f'<ul class="sp-ul">{lis}</ul></div>')
        else:
            parts.append(
                f'<div class="sp-body sp-empty" style="left:{cx};top:{cy};'
                f'width:{cw};font-size:{px(s.pt(10, 8.5))}">'
                f'도표·차트 슬라이드</div>')

    # 출처 푸터
    if src and not hero:
        parts.append(
            f'<div class="sp-foot" style="left:{px(s.x(0.63))};'
            f'top:{px(s.y(TH.FOOT_Y))};width:{px(s.x(12.06))};'
            f'font-size:{px(s.pt(7, 6.5))}">{_esc(src)}</div>')

    if index is not None:
        parts.append(f'<div class="sp-no">{index}</div>')

    parts.append('</div>')
    return ''.join(parts)


def slide_css() -> str:
    """
    미리보기 카드 CSS. `theme_css.inject()` 가 한 번만 내보낸다.

    색은 산출물 팔레트(`utils/report/theme.py`)를 그대로 쓴다 — 화면 테마의
    삼성 블루가 아니라 **PPT 에 실제로 찍히는 색**이어야 미리보기가 의미가 있다.
    """
    return f"""
  .sp-slide {{
      position: relative; background: #fff; overflow: hidden;
      border: 1px solid var(--ax-line); border-radius: 6px;
      font-family: "AXHead", "AXSans", "Malgun Gothic", sans-serif;
      color: #{TH.INK}; line-height: 1.35; flex: 0 0 auto;
  }}
  .sp-slide > div {{ position: absolute; }}
  .sp-tag  {{ color: #{TH.BLUE_MAIN}; font-weight: 700; letter-spacing: -.02em; }}
  .sp-sq   {{ background: #{TH.BLUE_MAIN}; }}
  .sp-sec  {{ color: #{TH.BLUE_MAIN}; font-weight: 700; letter-spacing: -.02em;
             white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .sp-key  {{ color: #{TH.INK}; font-weight: 700; letter-spacing: -.025em;
             word-break: keep-all; overflow-wrap: anywhere;
             display: -webkit-box; -webkit-line-clamp: 2;
             -webkit-box-orient: vertical; overflow: hidden; }}
  .sp-hero {{ color: #{TH.INK}; font-weight: 700; letter-spacing: -.03em;
             text-align: center; word-break: keep-all; }}
  .sp-body {{ color: #{TH.INK}; overflow: hidden; }}
  .sp-ul   {{ margin: 0; padding-left: 1.1em; }}
  .sp-ul li {{ margin-bottom: .45em; word-break: keep-all;
              overflow-wrap: anywhere; }}
  .sp-empty {{ color: #{TH.MUTED}; font-style: normal; }}
  .sp-tbl  {{ width: 100%; border-collapse: collapse;
             font-size: inherit; table-layout: fixed; }}
  .sp-tbl th {{ background: #{TH.TBL_HEAD}; color: #{TH.INK};
               font-weight: 700; padding: .35em .5em; text-align: left;
               border: 1px solid #{TH.LINE_CARD}; white-space: nowrap; }}
  .sp-tbl td {{ padding: .32em .5em; border: 1px solid #{TH.LINE_CARD};
               white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
               max-width: 9em; }}
  .sp-more {{ color: #{TH.MUTED}; margin-top: .4em; }}
  .sp-foot {{ color: #{TH.FOOT}; word-break: keep-all; white-space: nowrap;
             overflow: hidden; text-overflow: ellipsis; }}
  .sp-no   {{ position: absolute; right: 6px; bottom: 5px;
             color: #{TH.MUTED}; font-size: 10px; font-weight: 700; }}
"""
