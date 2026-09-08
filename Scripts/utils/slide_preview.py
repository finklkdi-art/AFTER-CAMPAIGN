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
    """
    인치 좌표 → **상대 단위** 변환기.

    🔴 예전에는 인치를 px 로 굳혀 넣었다. 카드가 `width:560px` 로 고정되니,
       Streamlit 칼럼이 그보다 좁아지는 순간(브라우저 폭 1030 근처) 카드가
       오른쪽 '문안 수정' 패널 위로 삐져나왔다. 고정 px 를 유동 칼럼에 넣으면
       겹치는 건 예외가 아니라 정상 동작이다.

       이제 좌표는 **카드 대비 %**, 글자는 **cqw(카드 폭의 1%)** 로 낸다.
       카드는 `width:100%` + `aspect-ratio` 로 칼럼을 따라 줄었다 늘었다 하고,
       내부는 항상 같은 비율을 유지한다. 어떤 폭에서도 넘칠 수가 없다.
    """

    def __init__(self, width_px: int):
        self.w = width_px                    # 이제 '최대 폭' 힌트로만 쓴다
        self.h = round(width_px * ASPECT)
        self.ppi = width_px / SLIDE_W_IN

    def fx(self, inches: float) -> str:
        """가로 좌표·폭 — 카드 폭 대비 %"""
        return f'{round(inches / SLIDE_W_IN * 100, 3)}%'

    def fy(self, inches: float) -> str:
        """세로 좌표·높이 — 카드 높이 대비 %"""
        return f'{round(inches / SLIDE_H_IN * 100, 3)}%'

    def ff(self, points: float, floor: float = 0) -> str:
        """
        글자 크기 — 카드 폭에 비례(cqw)하되 가독 하한(px)을 지킨다.

        비율만 따르면 300px 썸네일에서 본문 10.5pt 가 3.5px 가 되어 글자가
        아니라 얼룩이 된다. `max()` 로 하한을 걸어 두면, 큰 카드에서는 실제
        덱과 같은 비율로 커지고 작은 카드에서만 하한이 작동한다.
        """
        cqw = round(points / 72 / SLIDE_W_IN * 100, 4)
        if floor:
            return f'max({floor}px, {cqw}cqw)'
        return f'{cqw}cqw'


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


# 본문과 각주 사이 최소 간격(inch). 둘이 맞닿으면 표 마지막 줄과 자료원
# 문구가 붙어 읽혀서, 어디까지가 표인지 눈으로 구분되지 않는다.
_BODY_FOOT_GAP = 0.14


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

    # 카드는 칼럼 폭을 따라간다. `max-width` 는 '이보다 크게는 만들지 말라'는
    # 상한일 뿐이고, 칼럼이 좁아지면 그만큼 줄어든다 — 넘칠 여지가 없다.
    parts: List[str] = [
        f'<div class="sp-slide" style="max-width:{s.w}px">'
    ]

    # L3a 캠페인 태그 — 작은 카드에서는 생략한다.
    # 글자 크기에 하한을 두다 보니 태그(0.28in)와 섹션 라벨(0.63in)이 서로
    # 붙어 읽히고, 모든 장에 같은 값이 반복돼 정보량도 없다.
    if campaign_tag and not hero and width >= 500:
        parts.append(
            f'<div class="sp-tag" style="left:{s.fx(TH.TAG_POS[0])};'
            f'top:{s.fy(TH.TAG_POS[1])};font-size:{s.ff(9, 7)}">'
            f'{_esc(campaign_tag)}</div>')

    # L3 헤더 괘선 + 셰브런 플래그 + 섹션 라벨
    # (2026.09.09 — ■ 사각을 산출물과 같은 셰브런으로 교체. 미리보기가
    #  실제 PPTX 와 다른 표식을 그리면 AE 가 화면으로 검수할 수 없다.)
    if section and not hero:
        parts.append(
            f'<div class="sp-rule" style="left:{s.fx(TH.RULE_POS[0])};'
            f'top:{s.fy(TH.RULE_POS[1])};width:{s.fx(TH.RULE_POS[2])}"></div>')
        parts.append(
            f'<div class="sp-flag" style="left:{s.fx(TH.FLAG_POS[0])};'
            f'top:{s.fy(TH.FLAG_POS[1])};width:{s.fx(TH.FLAG_POS[2])};'
            f'height:{s.fy(TH.FLAG_POS[3])}"></div>')
        parts.append(
            f'<div class="sp-sec" style="left:{s.fx(TH.SEC_POS[0])};'
            f'top:{s.fy(TH.SEC_POS[1])};font-size:{s.ff(11, 8.5)}">'
            f'{_esc(section)}</div>')

    # L4 키메시지
    if headline:
        if hero:
            parts.append(
                f'<div class="sp-hero" style="left:{s.fx(1.0)};'
                f'top:{s.fy(2.9)};width:{s.fx(11.3)};'
                f'font-size:{s.ff(30, 15)}">{_esc(headline)}</div>')
        else:
            parts.append(
                f'<div class="sp-key" style="left:{s.fx(TH.KEY_POS[0])};'
                f'top:{s.fy(TH.KEY_POS[1])};width:{s.fx(TH.KEY_POS[2])};'
                f'height:{s.fy(TH.KEY_POS[3])};'
                f'font-size:{s.ff(17, 11)}">{_esc(headline)}</div>')

    # 본문 영역 — 표가 있으면 표, 없으면 불릿
    if not hero:
        cy = s.fy(TH.CONTENT_Y)
        cx = s.fx(0.63)
        cw = s.fx(12.06)
        # 🔴 본문에 높이를 준다.
        #
        # 예전에는 높이가 없어서, 행이 많은 표가 아래로 계속 자라 **각주
        # 영역을 덮었다**(사용자 제보 스크린샷). 절대 좌표 배치에서는 높이를
        # 주지 않으면 다음 영역을 침범하는 게 기본 동작이다.
        # 각주 바로 위까지로 잘라 두면 넘치는 부분은 overflow:hidden 이
        # 깔끔하게 잘라 내고, '외 N행' 표기가 이미 생략 사실을 알려 준다.
        ch = s.fy(TH.FOOT_Y - TH.CONTENT_Y - _BODY_FOOT_GAP)
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
                f'height:{ch};font-size:{s.ff(8, 7)}">'
                f'<table class="sp-tbl"><thead><tr>{th}</tr></thead>'
                f'<tbody>{tb}</tbody></table>{more}</div>')
        elif bullets:
            lis = ''.join(f'<li>{_esc(b)}</li>' for b in bullets)
            parts.append(
                f'<div class="sp-body" style="left:{cx};top:{cy};width:{cw};'
                f'height:{ch};font-size:{s.ff(10.5, 8.5)}">'
                f'<ul class="sp-ul">{lis}</ul></div>')
        else:
            parts.append(
                f'<div class="sp-body sp-empty" style="left:{cx};top:{cy};'
                f'width:{cw};height:{ch};font-size:{s.ff(10, 8.5)}">'
                f'도표·차트 슬라이드</div>')

    # 출처 푸터
    if src and not hero:
        parts.append(
            f'<div class="sp-foot" style="left:{s.fx(TH.FOOT_POS[0])};'
            f'top:{s.fy(TH.FOOT_Y)};width:{s.fx(TH.FOOT_POS[2])};'
            f'height:{s.fy(TH.SLIDE_H - TH.FOOT_Y - 0.06)};'
            f'font-size:{s.ff(7, 6.5)}">{_esc(src)}</div>')

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
  /* 카드는 담긴 칼럼 폭을 따라간다.
     · width:100% + aspect-ratio → 칼럼이 좁아지면 카드도 같이 줄어든다.
       예전의 고정 px 카드는 칼럼보다 넓어지는 순간 옆 패널을 덮었다.
     · container-type:inline-size → 내부 글자를 cqw(카드 폭의 1%)로 잡아
       어떤 크기에서도 같은 비율을 유지한다.
     · flex:0 0 auto 를 쓰지 않는다 — 그게 축소를 막던 원인이다. */
  .sp-slide {{
      position: relative; background: #fff; overflow: hidden;
      border: 1px solid var(--ax-line); border-radius: 6px;
      font-family: "AXHead", "AXSans", "Malgun Gothic", sans-serif;
      color: #{TH.INK}; line-height: 1.35;
      width: 100%; aspect-ratio: {TH.SLIDE_W} / {TH.SLIDE_H};
      container-type: inline-size;
      max-width: 100%; box-sizing: border-box;
  }}
  .sp-slide > div {{ position: absolute; }}
  .sp-tag  {{ color: #{TH.BLACK}; font-weight: 700; letter-spacing: -.02em; }}
  .sp-rule {{ background: #{TH.BLACK}; height: 1px; }}
  .sp-flag {{ background: linear-gradient(100deg, #{TH.FLAG_A}, #{TH.FLAG_B});
             clip-path: polygon(0 0, 72% 0, 100% 50%, 72% 100%, 0 100%, 26% 50%); }}
  .sp-sec  {{ color: #{TH.BLACK}; font-weight: 700; letter-spacing: -.02em;
             white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .sp-key  {{ color: #{TH.INK}; font-weight: 700; letter-spacing: -.025em;
             word-break: keep-all; overflow-wrap: anywhere;
             display: -webkit-box; -webkit-line-clamp: 2;
             -webkit-box-orient: vertical; overflow: hidden; }}
  .sp-hero {{ color: #{TH.INK}; font-weight: 700; letter-spacing: -.03em;
             text-align: center; word-break: keep-all; }}
  /* 영역마다 높이가 주어지므로, 넘치는 내용은 다음 영역을 밀지 않고 잘린다.
     절대 좌표 배치에서 overflow 를 열어 두면 그게 곧 영역 침범이 된다. */
  .sp-body {{ color: #{TH.INK}; overflow: hidden; }}
  .sp-key  {{ overflow: hidden; }}
  .sp-foot {{ overflow: hidden; }}
  .sp-ul   {{ margin: 0; padding-left: 1.1em; }}
  .sp-ul li {{ margin-bottom: .45em; word-break: keep-all;
              overflow-wrap: anywhere; }}
  .sp-empty {{ color: #{TH.MUTED}; font-style: normal; }}
  /* 작은 글자에서 행이 서로 붙어 읽히던 문제 — 줄간을 표에서만 되잡는다.
     카드 전체 line-height(1.35)를 그대로 쓰면 7~8px 글자에서 행 높이가
     12px 남짓이라 위아래 글자가 맞닿아 보인다. */
  .sp-tbl  {{ width: 100%; border-collapse: collapse;
             font-size: inherit; table-layout: fixed; line-height: 1.5; }}
  .sp-tbl th {{ background: #{TH.TBL_HEAD}; color: #{TH.INK};
               font-weight: 700; padding: .45em .55em; text-align: left;
               border: 1px solid #{TH.LINE_CARD}; white-space: nowrap;
               overflow: hidden; text-overflow: ellipsis; }}
  .sp-tbl td {{ padding: .42em .55em; border: 1px solid #{TH.LINE_CARD};
               white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
               max-width: 9em; }}
  .sp-more {{ color: #{TH.MUTED}; margin-top: .5em; }}
  .sp-foot {{ color: #{TH.FOOT}; word-break: keep-all; white-space: nowrap;
             overflow: hidden; text-overflow: ellipsis; }}
  .sp-no   {{ position: absolute; right: 6px; bottom: 5px;
             color: #{TH.MUTED}; font-size: 10px; font-weight: 700; }}
"""
