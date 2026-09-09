# -*- coding: utf-8 -*-
"""
Stage 2 — ReportSpec 빌더

CampaignDataset(파서 산출) + CampaignKnowledge(검증 결과)를 받아
슬라이드 명세(SlideSpec) 목록으로 변환한다.

원칙:
  - 데이터에서 직접 도출되는 사실만 문장화한다 (추측성 포장 금지)
  - 모든 수치 블록에 출처(sources)를 붙인다 (데이터-근거 1:1)
  - 결손을 건너뛴 항목의 슬라이드는 만들지 않는다
    (사유는 이미 Checklist 에 기록되어 1페이지에 실림)
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from models.campaign_data import (
    CampaignDataset, GAP_FILLED, Insight, InsightSet, StrategyItem,
)
from models.campaign_knowledge import CampaignKnowledge
from models.checklist import ChecklistItem
from . import formatters as fmt


@dataclass
class SlideSpec:
    """렌더러가 소비하는 슬라이드 한 장의 명세"""
    kind: str                                  # checklist/cover/toc/divider/...
    payload: Dict[str, Any] = field(default_factory=dict)
    block_id: str = ''                         # 부분 리렌더링 식별자 (Stage 4.5)


@dataclass
class ReportSpec:
    campaign_tag: str = ''                     # L3a 고정 표기
    slides: List[SlideSpec] = field(default_factory=list)
    toc: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    insights: Optional[InsightSet] = None      # Stage 3 산출물 (화면 표시용)

    def slide_of(self, block_id: str) -> Optional[SlideSpec]:
        """block_id 로 슬라이드를 찾는다."""
        for s in self.slides:
            if s.block_id and s.block_id == block_id:
                return s
        return None

    def replace_block(self, block_id: str, new_slide: Optional[SlideSpec]) -> bool:
        """
        한 블록을 교체한다 (부분 리렌더링).

        new_slide 가 None 이면 교체하지 않는다 — 재생성에 실패했다고 해서
        기존 슬라이드를 지우면 조용한 소실이 된다 (claude.md 3.1).
        """
        if new_slide is None:
            return False
        for i, s in enumerate(self.slides):
            if s.block_id == block_id:
                new_slide.block_id = block_id
                self.slides[i] = new_slide
                return True
        return False


# 인사이트 축 → 화면·문구 표기
# Lesson Learned 5축 (utils/insight/axes.py 와 동일 — 순환 임포트를 피해 여기 복제)
AXIS_LABELS = {
    'message': '전략·메시지',
    'media': '매체·상품 효율',
    'targeting': '타겟팅',
    'creative': '크리에이티브',
    'funnel': '전환·퍼널',
    # 구 축 표기 호환
    'kpi': '전환·퍼널',
    'period': '매체·상품 효율',
}


# 매체명 → 대표 표기 정리는 하지 않는다 (원본 표기 유지 — 임의 판단 금지)


def _totalizer(truncated: bool):
    """
    Total 행 누적기.

    표의 각 행은 fmt.comma() 로 정수 반올림되어 표기되므로, 원본 실수의 합을
    반올림하면 광고주가 열을 더한 값과 최대 (행 수/2)원 어긋난다.
    (실측: 에어컨 캠페인 집행 비용 열 1원 불일치)

    · 전량 표기 표 — 표시되는 반올림 값 기준으로 더해 열이 맞아떨어지게 한다
    · 상위 N건만 표기하는 표 — 각주로 고지한 대로 전체 합계를 유지한다
      (행 합과 다른 것이 의도된 표기임)
    """
    if truncated:
        return lambda v: float(v or 0)
    return lambda v: float(round(v or 0))


# ══════════════════════ 확장형 동적 렌더링 (사용자 지시 2026.09.06)
#
# 포스트바이 원본의 방대한 표를 요약·절단하지 않고 1:1 미러링한다.
#   · 한 장에 하나의 굵직한 표만 온전히 담는다
#   · 표가 슬라이드 밖으로 넘치면 폰트를 줄이는 대신 여러 장으로 분할한다
#   · 표(매체군) 개수만큼 슬라이드를 동적으로 확장한다
#
# 한 페이지에 안정적으로 들어가는 데이터 행 수 (헤더 제외).
# 본문 영역(y 2.95 → 약 6.85, row_h 0.24 기준)에서 약 16행이 한계라
# 여백을 두어 보수적으로 잡는다.
_ROWS_PER_PAGE = 15          # 파생 표(매체·소재·목적별) 페이지당 데이터 행
_RAW_ROWS_PER_PAGE = 14      # 포스트바이 원본 표 페이지당 데이터 행
_MAX_DEEPDIVE_SLIDES = 80    # 폭주 방지 상한 (초과분은 Checklist 로 고지)


def _looks_numeric(s: Any) -> bool:
    """수치·비율·금액처럼 보이면 우측 정렬 대상으로 판정한다."""
    text = str(s).strip()
    if not text or text in ('-', '–', 'N/A', 'n/a', '·'):
        return False
    digits = sum(ch.isdigit() for ch in text)
    if digits == 0:
        return False
    allowed = sum(1 for ch in text
                  if ch.isdigit() or ch in ' ,.%+-원회억만천건명초₩()~/')
    return allowed / len(text) >= 0.7


def _is_substantial_table(table: List[List[str]]) -> bool:
    """미러링할 가치가 있는 표인지 (빈 표·라벨 조각 제외, 절단은 하지 않음)."""
    if not table or len(table) < 2:
        return False
    width = max((len(r) for r in table), default=0)
    if width < 2:
        return False
    non_empty = sum(1 for r in table for c in r if str(c).strip())
    return non_empty >= 3


def _paginate_rows(base: Dict[str, Any], header: List[Any],
                   data_rows: List[Any], total_row: Optional[List[Any]],
                   col_w: Optional[List[float]],
                   per_page: int = _ROWS_PER_PAGE) -> List['SlideSpec']:
    """
    긴 표를 여러 SlideSpec 으로 나눈다 (행 절단 금지 — CLAUDE.md 3.1).

    · 헤더는 매 장 반복
    · Total 행은 마지막 장에만 붙인다
    · 2장 이상이면 섹션 라벨에 (k/n) 페이지 표기를 단다
    """
    chunks = [data_rows[i:i + per_page]
              for i in range(0, len(data_rows), per_page)] or [[]]
    n = len(chunks)
    slides: List['SlideSpec'] = []
    for pi, chunk in enumerate(chunks, 1):
        rows = list(chunk)
        use_total = bool(total_row) and pi == n
        if use_total:
            rows = rows + [total_row]
        payload = dict(base)
        payload['header'] = header
        payload['rows'] = rows
        payload['col_w'] = col_w
        payload['use_total_row'] = use_total
        if n > 1:
            payload['section'] = f"{base['section']} ({pi}/{n})"
            payload['page'] = [pi, n]
            src = list(payload.get('sources') or [])
            if pi == 1:
                src.append(f'표가 길어 {n}장으로 분할 게재 — 원본 행 전량 보존')
            payload['sources'] = src
        slides.append(SlideSpec('media_table', payload))
    return slides


def _to_num(s: Any) -> Optional[float]:
    """표 셀 문자열에서 대표 수치를 뽑는다 (콤마·단위 무시)."""
    text = str(s).strip()
    if not text or text in ('-', '–', 'N/A', 'n/a'):
        return None
    text = text.replace(',', '')
    m = re.search(r'-?\d+\.?\d*', text)
    return float(m.group()) if m else None


def _table_scope(title: str) -> str:
    """표 제목에서 대상(매체군 등)만 추린다 — '집행 결과'·'표 N' 등 상투어 제거."""
    t = re.sub(r'\([^)]*\)', '', title).strip()
    t = re.sub(r'·?\s*표\s*\d+\s*$', '', t).strip()
    t = re.sub(r'\s*(집행\s*결과|집행결과|결과|현황|비교|분석|효율)\s*$', '',
               t).strip()
    return t or title.strip()


def _find_col(header_rows: List[List[str]], *keywords: str) -> Optional[int]:
    """헤더(병합으로 여러 줄인 경우 포함)에서 키워드가 있는 열 인덱스."""
    width = max((len(r) for r in header_rows), default=0)
    for j in range(width):
        blob = ' '.join(str(r[j]) for r in header_rows if j < len(r)).lower()
        if any(k.lower() in blob for k in keywords):
            return j
    return None


def _header_span(norm: List[List[str]]) -> int:
    """
    상단에서 '헤더로 보이는' 행 수를 센다 (숫자가 거의 없는 행).

    병합된 다단 헤더(AA 표는 3줄)를 헤더로 인식하되, 데이터 행을 헤더로
    잘못 넣어 열 키워드가 오매칭되는 것을 막는다.
    """
    n = 0
    for row in norm[:3]:
        vals = [c for c in row if c]
        if not vals:
            n += 1
            continue
        numeric = sum(1 for c in vals if _to_num(c) is not None)
        if numeric <= len(vals) * 0.4:
            n += 1
        else:
            break
    return max(1, n)


def _summarize_table(title: str, table: List[List[str]]) -> List[dict]:
    """
    표 데이터에서 광고주 보고용 2줄 요약(하이라이트·인사이트)을 만든다.

    · 팩트 기반만 서술한다 (추측성 포장 금지 — CLAUDE.md 5)
    · 숫자·핵심어는 강조 런으로 분리한다
    반환: add_key_message 용 parts 리스트 (두 줄, 사이에 break)
    """
    scope = _table_scope(title)
    if not table or len(table) < 2:
        return [{'text': f'{scope} 상세 집행 성과', 'emph': True}]

    width = max(len(r) for r in table)
    norm = [[(str(r[j]) if j < len(r) else '').strip() for j in range(width)]
            for r in table]
    n_head = _header_span(norm)
    head_rows = norm[:n_head]
    body = norm[n_head:]

    # Total 행과 데이터 행 분리
    def is_total(row):
        c0 = row[0].lower() if row else ''
        return ('total' in c0 or '합계' in c0 or c0 in ('계', '총계', '소계'))
    total_row = next((r for r in body if is_total(r)), None)
    data = [r for r in body if r and r[0] and not is_total(r)]

    imp = _find_col(head_rows, '노출', 'imps', 'impression')
    view = _find_col(head_rows, '조회', 'view')
    clk = _find_col(head_rows, '클릭', 'click')
    spend = _find_col(head_rows, '집행금액', '집행 비용', '집행비용', '금액')
    vtr = _find_col(head_rows, 'vtr')
    ctr = _find_col(head_rows, 'ctr')
    cpv = _find_col(head_rows, 'cpv')
    cpc = _find_col(head_rows, 'cpc')
    reach = _find_col(head_rows, 'reach', '도달')
    freq = _find_col(head_rows, 'freq', '빈도')
    visit = _find_col(head_rows, 'visit', '방문', '유입')

    def cell(row, j):
        return row[j] if (row and j is not None and j < len(row)) else ''

    def total_of(j):
        if total_row and cell(total_row, j):
            return cell(total_row, j)
        vals = [_to_num(cell(r, j)) for r in data]
        vals = [v for v in vals if v is not None]
        if not vals:
            return ''
        return f'{int(round(sum(vals))):,}'

    def em(text):
        return {'text': text, 'emph': True}

    def best(col, want_max=True):
        cand = [(r[0], cell(r, col), _to_num(cell(r, col)))
                for r in data if _to_num(cell(r, col)) is not None]
        if not cand:
            return None
        cand.sort(key=lambda x: x[2], reverse=want_max)
        return cand[0]

    line1: List[dict] = []
    line2: List[dict] = []

    # ── 도달·빈도 표 (Reach/Frequency) — 합산이 무의미하므로 규모+최다 도달
    if reach is not None or freq is not None:
        line1 = [{'text': f'{scope} — '}]
        if imp is not None and total_of(imp):
            line1 += [{'text': '총 노출 '}, em(f'{total_of(imp)}회')]
            line1 += [{'text': ' 기준 매체별 순 도달·유효 빈도 분석'}]
        else:
            line1 += [{'text': '매체별 순 도달 및 유효 빈도 분석'}]
        b = best(reach, True) if reach is not None else None
        if b:
            line2 = [em(b[0]), {'text': ' 라인이 순 도달 '}, em(f'{b[1]}명'),
                     {'text': '으로 최다 도달 확보'}]

    # ── Adobe Analytics (유입/전환 퍼널)
    elif visit is not None:
        line1 = [{'text': f'{scope} — '}]
        if total_of(visit):
            line1 += [{'text': '총 유입(Visit) '}, em(f'{total_of(visit)}회'),
                      {'text': ' 확보'}]
        else:
            line1 += [{'text': '매체별 유입·전환 퍼널 분석'}]
        b = best(visit, True)
        if b:
            line2 = [em(b[0]), {'text': ' 라인이 Visit '}, em(f'{b[1]}회'),
                     {'text': '로 유입 기여 최대'}]

    # ── 일반 매체/소재 성과 표
    else:
        line1 = [{'text': f'{scope} — '}]
        scale_bits: List[List[dict]] = []
        big = 100    # 노출 대비 비현실적 소수(오매칭) 방지 하한
        if imp is not None and total_of(imp):
            scale_bits.append([{'text': '총 노출 '}, em(f'{total_of(imp)}회')])
        if view is not None and (_to_num(total_of(view)) or 0) >= big:
            scale_bits.append([{'text': '조회 '}, em(f'{total_of(view)}회')])
        if clk is not None and (_to_num(total_of(clk)) or 0) >= big:
            scale_bits.append([{'text': '클릭 '}, em(f'{total_of(clk)}회')])
        if not scale_bits and spend is not None and total_of(spend):
            scale_bits.append([{'text': '총 집행 '}, em(f'{total_of(spend)}원')])

        if scale_bits:
            for i, bit in enumerate(scale_bits[:3]):
                if i:
                    line1.append({'text': ' · '})
                line1.extend(bit)
            line1.append({'text': ' 확보'})
        else:
            labels = [r[0] for r in data if r[0]][:3]
            if labels:
                line1 = [em(' · '.join(labels)),
                         {'text': f' 등 {len(data)}개 항목의 상세 성과 비교'}]
            else:
                line1 = [{'text': f'{scope} 상세 집행 성과', 'emph': True}]

        if vtr is not None and best(vtr, True):
            lbl, disp, _ = best(vtr, True)
            line2 = [em(lbl), {'text': ' 라인이 VTR '}, em(disp),
                     {'text': '로 영상 몰입도 최고'}]
        elif ctr is not None and best(ctr, True):
            lbl, disp, _ = best(ctr, True)
            line2 = [em(lbl), {'text': ' 라인이 CTR '}, em(disp),
                     {'text': '로 클릭 반응 최고'}]
        elif cpv is not None and best(cpv, False):
            lbl, disp, _ = best(cpv, False)
            line2 = [em(lbl), {'text': ' 라인이 CPV '}, em(disp),
                     {'text': '로 조회 효율 우위'}]
        elif cpc is not None and best(cpc, False):
            lbl, disp, _ = best(cpc, False)
            line2 = [em(lbl), {'text': ' 라인이 CPC '}, em(disp),
                     {'text': '로 클릭 효율 우위'}]
        elif imp is not None and best(imp, True):
            lbl, disp, _ = best(imp, True)
            line2 = [em(lbl), {'text': ' 라인에 노출 '}, em(f'{disp}회'),
                     {'text': ' 집중'}]

    parts: List[dict] = list(line1)
    if line2:
        parts.append({'text': '', 'break': True})
        parts.extend(line2)
    return parts


def _raw_table_slides(title: str, summary_parts: List[dict],
                      table: List[List[str]], source: str,
                      src: Optional[dict] = None,
                      per_page: int = _RAW_ROWS_PER_PAGE) -> List['SlideSpec']:
    """
    포스트바이 원본 표 1개를 슬라이드(들)로 미러링한다.

    렌더러는 가능하면 원본 pptx 의 표 도형을 그대로 복제해(디자인 100% 유지),
    복제가 불가하면 아래 header/rows 텍스트로 표를 재구성한다(폴백).
    """
    width = max(len(r) for r in table)
    norm = [[(str(r[j]) if j < len(r) else '') for j in range(width)]
            for r in table]
    header, body = norm[0], norm[1:]

    if width <= 6:
        font, row_h = 9.0, 0.26
    elif width <= 9:
        font, row_h = 8.0, 0.24
    elif width <= 12:
        font, row_h = 7.5, 0.24
    else:
        font, row_h = 7.0, 0.24

    col_w = ([1.7] + [1.0] * (width - 1)) if width > 1 else [1.0]

    def cellify(row: List[str], is_header: bool = False) -> List[Any]:
        out: List[Any] = []
        for j, v in enumerate(row):
            v = v.strip()
            if is_header or j == 0:
                out.append(v)
            elif _looks_numeric(v):
                out.append({'t': v, 'right': True})
            else:
                out.append(v)
        return out

    header_cells = cellify(header, is_header=True)

    # 원본 표가 있으면: 표 전체를 한 장에 그대로 복제한다(렌더러가 비율 유지
    # 축소로 지면에 맞춤). 원본 디자인 100% 보존이 최우선이므로 큰 표도
    # 쪼개지 않는다. 복제 실패 시에만 아래 header/rows 텍스트로 재구성한다.
    if src:
        return [SlideSpec('postbuy_table', {
            'section': title,
            'key_parts': summary_parts,
            'header': header_cells,
            'rows': [cellify(r) for r in body],
            'col_w': col_w,
            'font_size': font,
            'row_h': row_h,
            'sources': [source],
            'src_pptx': src.get('pptx', ''),
            'src_slide_no': src.get('slide_no', 0),
            'src_table_ord': src.get('table_ord', 0),
        })]

    # 원본 복제가 불가한 경우(폴백): 텍스트 표를 페이지로 나눠 전량 게재
    chunks = [body[i:i + per_page]
              for i in range(0, len(body), per_page)] or [[]]
    n = len(chunks)
    slides: List['SlideSpec'] = []
    for pi, chunk in enumerate(chunks, 1):
        sec = title if n == 1 else f'{title} ({pi}/{n})'
        sources = [source]
        if n > 1:
            sources.append(f'지면 관계상 상세 표를 {n}개 장에 나누어 수록')
        payload = {
            'section': sec,
            'key_parts': (summary_parts if pi == 1
                          else [{'text': f'{_table_scope(title)} 상세 (이어짐)',
                                 'emph': True}]),
            'header': header_cells,
            'rows': [cellify(r) for r in chunk],
            'col_w': col_w,
            'font_size': font,
            'row_h': row_h,
            'sources': sources,
        }
        slides.append(SlideSpec('postbuy_table', payload))
    return slides


def _lesson_cards(bullets: List[str]) -> List[dict]:
    """
    Lesson 원문 불릿을 [헤드라인 + 근거] 카드로 묶는다.

    '·'·머리 없는 문장 = 새 카드(발견/제언), '-'·'>' 로 시작 = 앞 카드의 근거.
    """
    cards: List[dict] = []
    cur: Optional[dict] = None
    for raw in bullets:
        for seg in re.split(r'\s*/\s*', str(raw)):
            seg = seg.strip()
            if len(seg) < 4:
                continue
            is_sub = seg.lstrip('ㆍ·  ').startswith(('-', '–', '>', '▷', '＞'))
            clean = re.sub(r'^[·\-–>▷＞ㆍ\s]+', '', seg).strip()
            if len(clean) < 4:
                continue
            if is_sub and cur is not None:
                cur['evidence'].append(clean)
            else:
                cur = {'finding': clean, 'evidence': []}
                cards.append(cur)
    return cards


def _pack_lesson_pages(cards: List[dict], budget: float = 4.15,
                       max_pages: int = 3) -> tuple:
    """
    카드를 슬라이드 본문 높이에 맞춰 여러 장으로 그리디 배치한다.

    광고주 보고 분량을 감안해 최대 max_pages 장으로 제한하고, 넘치는 카드 수는
    각주 고지용으로 함께 돌려준다 (조용한 소실 방지 — CLAUDE.md 3.1).
    반환: (pages, dropped_card_count)
    """
    def card_h(c: dict) -> float:
        ev = sum(1 + (len(e) // 46) for e in c['evidence'])
        return 0.46 + 0.015 + 0.235 * ev + 0.26

    pages: List[List[dict]] = []
    cur: List[dict] = []
    h = 0.0
    used = 0
    for idx, c in enumerate(cards):
        ch = card_h(c)
        if cur and h + ch > budget:
            pages.append(cur)
            cur, h = [], 0.0
            if len(pages) >= max_pages:
                return pages, len(cards) - used
        cur.append(c)
        h += ch + 0.12
        used += 1
    if cur:
        pages.append(cur)
    return pages, 0


@dataclass
class BlockDef:
    """
    슬라이드 블록 정의 (Stage 4.5 부분 리렌더링용 레지스트리 항목)

    build 는 (knowledge, dataset, insights, options) 를 받아
    SlideSpec 또는 None(데이터 없어 미생성)을 반환한다.
    """
    block_id: str
    label: str                                 # 화면에 보일 이름
    section: str                               # 소속 섹션 ('' = 섹션 밖)
    build: Any
    editable: bool = False                     # 문안 수정(리렌더) 대상인지


def _blocks() -> List[BlockDef]:
    """
    슬라이드 블록 레지스트리.

    build() 는 이 목록만 보고 덱을 조립하므로, 목록의 순서가 곧 슬라이드
    순서다. 부분 리렌더링은 이 중 한 블록만 다시 만들어 교체한다.
    """
    b = ReportSpecBuilder

    # 5-챕터 볼륨 구조 (사용자 지시 2026.09.06)
    #   01 Campaign Overview   — 로드맵·스케줄
    #   02 Executive Summary   — 총괄 성과·전체 KPI
    #   03 Post-buy Deep-Dive  — 원본 매체군 표를 개수만큼 N장 동적 생성 (절대 축약 금지)
    #   04 Advanced Analytics  — 도달·빈도 / Adobe Analytics / 검색·버즈
    #   05 Insight & Next Step — Lesson Learned·차기 전략
    C1, C2, C3, C4, C5 = ('Campaign Overview', 'Executive Summary',
                          'Post-buy Deep-Dive', 'Advanced Analytics',
                          'Insight & Next Step')
    return [
        # ── 섹션 밖 (고정 위치)
        BlockDef('checklist', 'Checklist', '',
                 lambda k, d, i, o: b._checklist(k, d)),
        BlockDef('cover', '표지', '',
                 lambda k, d, i, o: b._cover(k)),

        # ── 01 Campaign Overview
        # Part 1 은 '실행 前 기획 의도' 영역이다. 소스가 없어도 슬라이드를
        # 지우지 않고 작성 가이드를 깔아 AE 가 채우게 한다 (지시 2026.09.07).
        BlockDef('overview_goal', '캠페인 목표', C1,
                 lambda k, d, i, o: b._overview_goal(k), editable=True),
        BlockDef('overview_strategy', '캠페인 전략', C1,
                 lambda k, d, i, o: b._overview_strategy(k), editable=True),
        BlockDef('overview_roadmap', '캠페인 로드맵', C1,
                 lambda k, d, i, o: b._overview_roadmap(k), editable=True),

        BlockDef('roadmap', '매체별 집행 로드맵', C1,
                 lambda k, d, i, o: b._roadmap(k, d)),
        BlockDef('creative_roadmap', '소재별 집행 로드맵', C1,
                 lambda k, d, i, o: b._creative_roadmap(k, d)),
        BlockDef('daily_trend', '일자별 추이 (스케줄)', C1,
                 lambda k, d, i, o: b._daily_trend(k, d)),

        # ── 02 Executive Summary
        # 요약 문장은 강조 수치가 런으로 끼어든 구조라 문안 수정 대상이 아니다
        # (근거: revise.PROSE_SLOTS 주석)
        BlockDef('summary', '캠페인 총괄 성과', C2,
                 lambda k, d, i, o: b._summary(k, d)),
        BlockDef('kpi', '전체 KPI 달성률', C2,
                 lambda k, d, i, o: b._kpi(k, d)),

        # ── 03 Post-buy Deep-Dive (원본 표 개수만큼 N장 — 절대 축약 금지)
        BlockDef('postbuy_deepdive', '포스트바이 매체군 원본 표', C3,
                 lambda k, d, i, o: b._postbuy_deepdive(k, d)),
        BlockDef('media_table', 'Digital 매체별 집행 결과', C3,
                 lambda k, d, i, o: b._media_table(k, d)),
        BlockDef('creative_table', '소재별 집행 결과', C3,
                 lambda k, d, i, o: b._creative_table(k, d)),
        BlockDef('purpose_table', '목적별 집행 결과', C3,
                 lambda k, d, i, o: b._purpose_table(k, d)),
        BlockDef('creative_cards', '소재 이미지', C3,
                 lambda k, d, i, o: b._creative_cards(k, d)),
        BlockDef('placement_cards', '매체별 게재 화면', C3,
                 lambda k, d, i, o: b._placement_cards(k, d)),

        # ── 04 Advanced Analytics
        BlockDef('postbuy_analytics', '도달·빈도 / Adobe Analytics 원본 표', C4,
                 lambda k, d, i, o: b._postbuy_analytics(k, d)),
        BlockDef('search_buzz', '검색·버즈', C4,
                 lambda k, d, i, o: b._search_buzz(d)),

        # ── 05 Insight & Next Step
        # 2026.09 개편 — 자동 도출(5축 3단 논법) 우선.
        # 포스트바이 원문 복사는 엔진이 한 건도 만들지 못했을 때의 폴백으로 내린다.
        # (원문 그대로 옮겨 적는 방식은 '기획적 해석'이 없어 실무 품질에 미달)
        BlockDef('insight', 'Lesson Learned (자동 도출)', C5,
                 lambda k, d, i, o: b._insight(i), editable=True),
        BlockDef('lesson', 'Lesson Learned (원문 폴백)', C5,
                 lambda k, d, i, o: (None if (i and i.insights)
                                     else b._lesson(d)), editable=True),
        BlockDef('strategy', '차기 전략', C5,
                 lambda k, d, i, o: b._strategy(i), editable=True),
    ]


def _fmt_cover_date(raw: str) -> str:
    """
    표지용 작성일자 표기. 'YYMMDD' → 'YYYY.MM.DD'.

    형식이 다르면 **추측해서 고치지 않고 원문 그대로** 보여 준다
    (Rule Book 2.1). 비어 있을 때만 오늘 날짜로 채운다.
    """
    from datetime import date
    txt = (raw or '').strip()
    if not txt:
        return date.today().strftime('%Y.%m.%d')
    if len(txt) == 6 and txt.isdigit():
        return f'20{txt[0:2]}.{txt[2:4]}.{txt[4:6]}'
    if len(txt) == 8 and txt.isdigit():
        return f'{txt[0:4]}.{txt[4:6]}.{txt[6:8]}'
    return txt


class ReportSpecBuilder:
    """CampaignDataset → ReportSpec"""

    @staticmethod
    def registry() -> List[BlockDef]:
        """슬라이드 블록 레지스트리를 반환한다."""
        return _blocks()

    @staticmethod
    def build(knowledge: CampaignKnowledge,
              dataset: CampaignDataset,
              insights: Optional[InsightSet] = None,
              options: Optional[Dict[str, Dict[str, Any]]] = None) -> ReportSpec:
        """
        Args:
            options: {block_id: 블록별 재생성 옵션} — 부분 리렌더링에서 사용
        """
        spec = ReportSpec()
        spec.campaign_tag = knowledge.campaign_name or '캠페인 결과보고'
        options = options or {}

        # Stage 3 — Checklist 슬라이드보다 먼저 실행해야 자동 도출 결과가
        # 1페이지 Checklist 에 함께 실린다
        if insights is None:
            insights = ReportSpecBuilder._run_stage3(knowledge, dataset, spec)
        spec.insights = insights

        # Part 1 개요 — 가이드(Placeholder)가 깔릴 슬라이드가 있으면
        # Checklist 슬라이드보다 먼저 기재해야 1페이지에 함께 실린다
        try:
            ReportSpecBuilder._record_overview_gap(knowledge)
        except Exception as e:
            spec.warnings.append(f'개요 결손 기재 실패: {e}')

        # 레지스트리 순서대로 조립 (데이터가 있는 블록만)
        fixed: List[SlideSpec] = []
        sections: List[tuple] = []
        by_section: Dict[str, List[SlideSpec]] = {}

        for bd in _blocks():
            try:
                result = bd.build(knowledge, dataset, insights,
                                  options.get(bd.block_id) or {})
            except Exception as e:
                # 블록 하나가 실패해도 덱 생성을 중단하지 않는다 (claude.md 3.3)
                spec.warnings.append(f'슬라이드 블록 생성 실패 [{bd.label}]: {e}')
                continue
            if result is None:
                continue
            # 블록은 SlideSpec 하나 또는 여러 장(N장 동적 확장)을 반환할 수 있다
            produced = [s for s in (result if isinstance(result, list)
                                    else [result]) if s is not None]
            if not produced:
                continue
            for idx, slide in enumerate(produced, 1):
                slide.block_id = (bd.block_id if len(produced) == 1
                                  else f'{bd.block_id}#{idx}')
                if not bd.section:
                    fixed.append(slide)
                    continue
                if bd.section not in by_section:
                    by_section[bd.section] = []
                    sections.append(bd.section)
                by_section[bd.section].append(slide)

        # 1페이지 Checklist + 표지 (CLAUDE.md 강제 조항)
        spec.slides.extend(fixed)

        # 목차 + 간지 배치
        spec.toc = list(sections)
        spec.slides.append(SlideSpec('toc', {'items': spec.toc}))
        for idx, name in enumerate(sections, 1):
            spec.slides.append(SlideSpec('divider', {'text': f'0{idx}. {name}'}))
            spec.slides.extend(by_section[name])

        spec.slides.append(SlideSpec('eod', {}))
        return spec

    # ────────────────────────── 부분 리렌더링 (Stage 4.5)

    @staticmethod
    def rebuild_block(block_id: str,
                      knowledge: CampaignKnowledge,
                      dataset: CampaignDataset,
                      insights: Optional[InsightSet] = None,
                      options: Optional[Dict[str, Any]] = None
                      ) -> Optional[SlideSpec]:
        """
        블록 한 개만 다시 만든다. 파싱(Stage 1)은 다시 하지 않는다.

        원본 데이터를 변형하지 않으며, 수정은 표현 계층에서만 일어난다.
        """
        # 'base#k' 형태 — 한 블록이 N장을 낼 때 k번째 장을 가리킨다
        base = block_id.split('#', 1)[0]
        page_idx = None
        if '#' in block_id:
            try:
                page_idx = int(block_id.split('#', 1)[1]) - 1
            except ValueError:
                page_idx = None

        bd = next((x for x in _blocks() if x.block_id == base), None)
        if bd is None:
            return None
        result = bd.build(knowledge, dataset, insights, options or {})
        if result is None:
            return None
        produced = [s for s in (result if isinstance(result, list)
                                else [result]) if s is not None]
        if not produced:
            return None
        if page_idx is not None:
            if page_idx < 0 or page_idx >= len(produced):
                return None
            slide = produced[page_idx]
        else:
            slide = produced[0]
        slide.block_id = block_id
        return slide

    # ────────────────────────── Stage 3 실행

    @staticmethod
    def _run_stage3(knowledge: CampaignKnowledge, dataset: CampaignDataset,
                    spec: ReportSpec) -> InsightSet:
        """
        인사이트 엔진을 돌리고 결과를 Checklist 에 반영한다.

        임포트를 함수 안에서 하는 이유: utils.insight 가 문구 조립을 위해
        utils.report.formatters 를 참조하므로 모듈 최상단에서 서로를 임포트하면
        순환이 된다.
        """
        try:
            from utils.insight import InsightEngine
        except Exception as e:
            spec.warnings.append(f'Stage 3 인사이트 엔진 로딩 실패: {e}')
            return InsightSet()

        engine = InsightEngine()
        result = engine.generate(knowledge, dataset)
        for item in engine.to_checklist_items(result):
            knowledge.add_checklist_item(item)
        spec.warnings.extend(result.warnings)
        return result

    # ────────────────────────── Part 1 캠페인 개요 (기획 의도)

    # 소스가 없을 때 슬라이드에 까는 AE 작성 가이드 (지시문 원문)
    TIP_GOAL = (
        '[Data Missing] 캠페인 기획/제안 내용이 확인되지 않습니다.\n'
        '기획자 직접 작성 가이드\n'
        '1. 당면 과제 — 이 캠페인을 왜 진행했는지\n'
        '2. 코어 타겟 — 누구를 대상으로 했는지\n'
        '3. 메인 카피/메시지 — 어떤 메시지를 전달했는지\n'
        '위 3가지를 2~3줄로 요약해 주세요.\n'
        '(우측/하단에는 KV 등 크리에이티브 에셋 이미지를 삽입해 주세요)')

    TIP_ROADMAP = (
        '[Data Missing] 캠페인 일정 및 로드맵 데이터가 확인되지 않습니다.\n'
        '기획자 직접 작성 가이드\n'
        '캠페인의 전체 일정과 각 Phase별 핵심 목적을 기재해 주세요.\n'
        '예) 런칭기 인지 확보 → 성수기 전환 유도\n'
        '가급적 시각적인 타임라인 형태로 얹어주시는 것을 권장합니다.')

    @staticmethod
    def _ov(knowledge: CampaignKnowledge) -> Dict[str, Any]:
        return getattr(knowledge, 'overview', None) or {}

    @staticmethod
    def _record_overview_gap(knowledge: CampaignKnowledge) -> None:
        """
        Part 1 슬라이드 중 작성 가이드가 깔리는 것이 있으면 Checklist 에 남긴다.

        가이드가 깔린 채로 보고서가 나가면 AE 가 못 보고 지나칠 수 있다.
        1페이지에 반드시 노출시킨다 (claude.md 3.4).
        """
        from utils.parsers import overview_parser as ovp
        from models.checklist import ChecklistItem

        ov = ReportSpecBuilder._ov(knowledge)
        missing = []
        if not ovp.has_goal(ov):
            missing.append('목표')
        if not ovp.has_strategy(ov):
            missing.append('전략')
        if not ovp.has_roadmap(ov):
            missing.append('로드맵')
        if not missing:
            return

        knowledge.add_checklist_item(ChecklistItem(
            type='overview_missing',
            severity='warning',
            message=("'캠페인 개요(목표/전략/로드맵)' 소스 누락 — 수기 작성 요망"),
            detail=(f'누락 항목: {" · ".join(missing)}. 해당 슬라이드는 삭제하지 않고 '
                    f'작성 가이드를 넣어 두었습니다. 제안서·미디어브리프를 추가로 '
                    f'올리시거나 슬라이드에 직접 기재해 주세요.'),
            source='Stage 4 Part 1 렌더링',
        ))

    @staticmethod
    def _ov_sources(ov: Dict[str, Any]) -> List[str]:
        names = ov.get('sources') or []
        return [f'자료원: {n}' for n in names[:2]]

    @staticmethod
    def _overview_goal(knowledge: CampaignKnowledge) -> SlideSpec:
        """캠페인 목표 — 당면 과제 · 핵심 타겟 · 메인 카피"""
        ov = ReportSpecBuilder._ov(knowledge)
        goal = ov.get('goal') or {}
        rows = [
            ('당면 과제', (goal.get('challenge') or '').strip()),
            ('핵심 타겟', (goal.get('core_target') or '').strip()),
            ('메인 카피', (goal.get('key_message') or '').strip()),
        ]
        filled = [(k, v) for k, v in rows if v]
        return SlideSpec('ov_goal', {
            'section': '캠페인 목표',
            'headline': ('캠페인 실행 前 수립한 기획 의도 요약'
                         if filled else '기획 의도 소스 미확보 — 기획자 작성 필요'),
            'rows': filled,
            'tip': None if filled else ReportSpecBuilder.TIP_GOAL,
            'sources': ReportSpecBuilder._ov_sources(ov),
        })

    @staticmethod
    def _overview_strategy(knowledge: CampaignKnowledge) -> SlideSpec:
        """캠페인 전략 — 방향성 · Phase 구성 · 핵심 채널"""
        ov = ReportSpecBuilder._ov(knowledge)
        strat = ov.get('strategy') or {}
        road = ov.get('roadmap') or {}
        direction = (strat.get('direction') or '').strip()
        channels = list(strat.get('channels') or [])
        phases = list(road.get('phases') or [])
        has_any = bool(direction or channels)

        # 헤드라인은 요약이어야 한다 — 원문 구간을 그대로 자르면 문장이 끊긴다.
        # 앞쪽 의미 단위 몇 개만 붙여 한 줄로 만든다.
        head = ''
        if direction:
            for seg in [s.strip() for s in direction.split('/') if s.strip()]:
                if len(seg) < 4 or seg.endswith(('개요', '가이드라인')):
                    continue
                head = f'{head} · {seg}' if head else seg
                if len(head) >= 60:
                    break
            head = head[:100]
        return SlideSpec('ov_strategy', {
            'section': '캠페인 전략',
            'headline': (head or
                         ('활용 채널 기준 캠페인 전개 방향'
                          if channels else '캠페인 전략 소스 미확보 — 기획자 작성 필요')),
            'direction': direction,
            'phases': phases,
            'channels': channels,
            'tip': None if has_any else ReportSpecBuilder.TIP_GOAL,
            'sources': ReportSpecBuilder._ov_sources(ov),
        })

    @staticmethod
    def _overview_roadmap(knowledge: CampaignKnowledge) -> SlideSpec:
        """캠페인 로드맵 — 전체 기간 × Phase 타임라인 (기획 의도 기준)"""
        ov = ReportSpecBuilder._ov(knowledge)
        road = ov.get('roadmap') or {}
        phases = list(road.get('phases') or [])
        period = (road.get('period') or '').strip()
        head = ('전체 기간 ' + period + ' 기준 Phase 순차 전개'
                if period and phases else
                ('Phase 구분 기준 캠페인 전개' if phases else
                 '캠페인 일정·로드맵 소스 미확보 — 기획자 작성 필요'))
        return SlideSpec('ov_roadmap', {
            'section': '캠페인 로드맵',
            'headline': head,
            'period': period,
            'phases': phases,
            'tip': None if phases else ReportSpecBuilder.TIP_ROADMAP,
            'sources': ReportSpecBuilder._ov_sources(ov),
        })

    # ────────────────────────── 게재 화면 (게재 보고 원천)

    @staticmethod
    def _media_vocab(dataset: CampaignDataset) -> List[str]:
        """실제 집행된 매체명 — 게재 화면 교차검증의 정답지"""
        names: List[str] = []

        def add(v):
            v = (v or '').strip()
            if v and v not in names:
                names.append(v)

        dr = dataset.daily_report
        if dr:
            for n in (dr.media_names or []):
                add(n)
            for r in (dr.media_totals or []):
                add(r.media)
            for r in (dr.media_performance or []):
                add(r.media)
        try:
            for line in dataset.plan_lines():
                add(line.media)
        except Exception:
            pass
        pb = dataset.postbuy
        if pb:
            for r in (pb.campaign_summary or []):
                add(r.media)
        return names

    @staticmethod
    def _placement_cards(knowledge: CampaignKnowledge,
                         dataset: CampaignDataset) -> Optional[List[SlideSpec]]:
        """
        매체별 게재 화면 — 게재 보고에서 뽑은 이미지를 실제 집행 매체와 대조해 배치.

        문서에 적힌 이름을 그대로 믿지 않고 미디어믹스·데일리리포트·포스트바이의
        매체명과 교차 검증한다. 확정되지 않은 이미지는 버리지 않고 Checklist 로
        보낸다 (조용한 소실 금지 — claude.md 3.1).
        """
        from pathlib import Path as _P
        from utils.parsers.placement_parser import PlacementShot, match_media
        from models.checklist import ChecklistItem

        raw = (getattr(knowledge, 'creative_info', None) or {}).get('placements')
        if not raw:
            return None
        shots = [PlacementShot.from_dict(d) for d in raw]
        if not shots:
            return None

        matched_n, unmatched_n = match_media(shots, ReportSpecBuilder._media_vocab(dataset))

        if unmatched_n:
            knowledge.add_checklist_item(ChecklistItem(
                type='placement_unmatched',
                severity='info',
                message=f'게재 화면 {unmatched_n}건은 매체를 확정하지 못했습니다',
                detail='실제 집행 매체명과 대조되지 않아 슬라이드에 싣지 않았습니다. '
                       '필요하시면 게재 보고 문서에서 직접 가져와 주세요.',
                source='Stage 4 게재 화면 교차검증',
            ))
        if not matched_n:
            return None

        # 매체별 대표 1장 (같은 매체가 여러 장이면 큰 이미지 우선)
        by_media: Dict[str, PlacementShot] = {}
        for s in shots:
            if not s.matched:
                continue
            cur = by_media.get(s.media)
            if cur is None or (s.width * s.height) > (cur.width * cur.height):
                by_media[s.media] = s

        root = _P(__file__).resolve().parents[3]
        totals = {}
        dr = dataset.daily_report
        if dr:
            for r in (dr.media_totals or []):
                totals[r.media] = r.metrics

        cards = []
        for media, shot in by_media.items():
            img = _P(shot.image_path)
            if not img.is_absolute():
                img = root / shot.image_path
            if not img.exists():
                continue
            m = totals.get(media)
            metric = ''
            if m:
                bits = []
                if m.impressions:
                    bits.append(f'노출 {fmt.count_korean(m.impressions)}회')
                if m.clicks:
                    bits.append(f'클릭 {fmt.count_korean(m.clicks)}회')
                metric = ' · '.join(bits)
            cards.append({'image': str(img), 'media': media, 'metric': metric})

        if not cards:
            return None

        per_page = 4
        pages = [cards[i:i + per_page] for i in range(0, len(cards), per_page)]
        n = len(pages)
        src = sorted({s.source_file for s in shots if s.matched})
        slides: List[SlideSpec] = []
        for pi, page in enumerate(pages, 1):
            section = ('매체별 게재 화면' if n == 1
                       else f'매체별 게재 화면 ({pi}/{n})')
            slides.append(SlideSpec('placement_cards', {
                'section': section,
                'headline': (f'게재 보고 기준 매체 {len(cards)}개의 '
                             f'실제 노출 화면 확인' if pi == 1
                             else '매체별 실제 노출 화면'),
                'cards': page,
                'sources': [f'자료원: {s}' for s in src[:2]],
            }))
        return slides

    # ────────────────────────── 슬라이드별 빌더

    @staticmethod
    def _checklist(knowledge: CampaignKnowledge,
                   dataset: CampaignDataset) -> SlideSpec:
        icon = {'error': '✗', 'warning': '!', 'info': '·'}
        rows = []
        items = knowledge.get_checklist_items()
        for it in items:
            rows.append({
                'sev': it.severity,
                'mark': icon.get(it.severity, '·'),
                'message': it.message,
                'detail': (it.detail or '')[:80],
            })
        return SlideSpec('checklist', {
            'rows': rows[:14],
            'overflow': max(0, len(rows) - 14),
            'mode': dataset.mode,
        })

    @staticmethod
    def _cover(knowledge: CampaignKnowledge) -> SlideSpec:
        """
        표지 — 캠페인명 + '결과보고서' + 작성일자 (사용자 지시 2026.09.09).

        작성일자는 AE 가 Stage 1.5 팝업에서 넣은 `date_created`(YYMMDD)를
        쓴다. 예전엔 렌더 시각(date.today)을 찍어, AE 가 지정한 날짜와
        표지가 어긋났다 — 파일명은 date_created 를 쓰는데 표지만 오늘이라
        같은 보고서에 두 날짜가 생기는 상태였다.
        """
        return SlideSpec('cover', {
            'title': knowledge.campaign_name or '캠페인',
            'subtitle': '결과보고서',
            'date': _fmt_cover_date(knowledge.date_created),
        })

    # ────────────────────────── Post-buy 원본 표 1:1 미러링 (Ch3 / Ch4)

    @staticmethod
    def _postbuy_deepdive(knowledge: CampaignKnowledge,
                          dataset: CampaignDataset) -> Optional[List[SlideSpec]]:
        """
        포스트바이 원본의 매체군 표(동영상·배너·버티컬·OTT·OOH 등)를
        표 개수만큼 슬라이드로 무한 확장해 100% 미러링한다 (절대 축약 금지).
        """
        return ReportSpecBuilder._postbuy_tables(
            knowledge, dataset,
            kinds={'summary', 'media', 'other'})

    @staticmethod
    def _postbuy_analytics(knowledge: CampaignKnowledge,
                           dataset: CampaignDataset) -> Optional[List[SlideSpec]]:
        """도달·빈도 / Adobe Analytics 원본 표를 표 개수만큼 미러링한다."""
        return ReportSpecBuilder._postbuy_tables(
            knowledge, dataset,
            kinds={'reach', 'analytics'})

    @staticmethod
    def _postbuy_tables(knowledge: CampaignKnowledge,
                        dataset: CampaignDataset,
                        kinds: set) -> Optional[List[SlideSpec]]:
        """
        포스트바이 섹션에서 지정한 종류의 원본 표를 모아, 표 1개 = 슬라이드 1장
        (넘치면 여러 장)으로 전량 게재한다. 원본 데이터를 변형하지 않는다.
        """
        pb = dataset.postbuy
        if not pb or not pb.sections:
            return None

        # 원본 pptx 절대 경로 — 있으면 렌더러가 표 도형을 그대로 복제한다
        src_pptx = ''
        try:
            from pathlib import Path
            if knowledge.folder_path and pb.source_file:
                cand = Path(knowledge.folder_path) / pb.source_file
                if cand.exists():
                    src_pptx = str(cand)
        except Exception:
            src_pptx = ''

        # (섹션, 섹션 내 순번, 섹션 내 표 개수, 표, 원본 표 서수) 수집.
        # table_ord 는 섹션 내 '모든' 표 기준 서수여야 렌더 시 원본과 정확히 매칭된다.
        collected = []
        for sec in pb.sections:
            if sec.kind not in kinds:
                continue
            subst = [(ord0, t) for ord0, t in enumerate(sec.tables)
                     if _is_substantial_table(t)]
            for ti, (ord0, table) in enumerate(subst, 1):
                collected.append((sec, ti, len(subst), ord0, table))
        if not collected:
            return None

        total = len(collected)
        slides: List[SlideSpec] = []
        dropped = 0
        for gi, (sec, ti, n_in_sec, ord0, table) in enumerate(collected, 1):
            if len(slides) >= _MAX_DEEPDIVE_SLIDES:
                dropped = total - gi + 1
                break
            title = (sec.title or f'포스트바이 p{sec.slide_no}')
            title = title.split(' / ')[0].strip()
            if len(title) > 46:
                title = title[:45] + '…'
            if n_in_sec > 1:
                title = f'{title} · 표 {ti}'
            summary = _summarize_table(title, table)
            source = f'자료원: {pb.source_file} p{sec.slide_no} 집행 결과'
            src = {'pptx': src_pptx, 'slide_no': sec.slide_no,
                   'table_ord': ord0} if src_pptx else None
            slides.extend(_raw_table_slides(title, summary, table, source,
                                            src=src))

        if dropped:
            knowledge.add_checklist_item(ChecklistItem(
                type='postbuy_deepdive_overflow',
                severity='warning',
                message=(f'포스트바이 원본 표 {dropped}개가 슬라이드 상한'
                         f'({_MAX_DEEPDIVE_SLIDES}장) 초과로 미게재 — 확인 필요'),
                detail='원본 표 수가 매우 많습니다. 상한을 조정하거나 별도 첨부를 검토하세요.',
                source='Stage 2 Post-buy Deep-Dive',
            ))
        return slides or None

    @staticmethod
    def _roadmap(knowledge: CampaignKnowledge,
                 dataset: CampaignDataset) -> Optional[SlideSpec]:
        """
        집행 로드맵 간트 — 기간이 확보된 계획 라인 사용

        미디어믹스에 기간 컬럼이 없는 파일이 있어 자동으로는 시간축을 만들 수
        없는 경우가 있다. Stage 1.5 결손 화면에서 기획자가 입력한 기간이 있으면
        그 값을 얹어 로드맵을 구성한다 (입력값 출처는 각주에 구분 표기).
        """
        from utils.roadmap_overlay import apply_period_overlay, MANUAL_SOURCE

        try:
            applied, extras, overlay_notes = apply_period_overlay(dataset)
        except Exception as e:                  # 보정 실패가 생성을 막지 않도록
            applied, extras, overlay_notes = 0, [], [f'기간 보정 실패: {e}']

        lines = [l for l in dataset.plan_lines() + extras
                 if l.period_start and l.period_end]
        if not lines:
            return None

        def key(day: str) -> int:                       # 'MM-DD' → 정렬키
            m, d = day.split('-')
            return int(m) * 31 + int(d)

        lines.sort(key=lambda l: (key(l.period_start), l.media))
        # 행 수 상한: 넘치면 매체 단위로 병합
        if len(lines) > 14:
            merged: Dict[str, dict] = {}
            for l in lines:
                g = merged.setdefault(l.media, {
                    'media': l.media, 'product': '',
                    'start': l.period_start, 'end': l.period_end,
                    'creative': '', 'src': l.source.label()})
                if key(l.period_start) < key(g['start']):
                    g['start'] = l.period_start
                if key(l.period_end) > key(g['end']):
                    g['end'] = l.period_end
            bars = list(merged.values())
            note = f'계획 라인 {len(lines)}건을 매체 단위로 병합 표기'
        else:
            bars = []
            for l in lines:
                bar = {'media': l.media, 'product': l.product,
                       'start': l.period_start, 'end': l.period_end,
                       'creative': l.creative, 'src': l.source.label()}
                # 목적 축은 미디어믹스에 목적 컬럼이 있는 파일에서만 확보된다
                if getattr(l, 'purpose', ''):
                    bar['label'] = f'{l.media} · {l.purpose}'
                bars.append(bar)
            note = None

        srcs = sorted({b['src'].split(':')[0] for b in bars if b.get('src')})
        mm = dataset.media_mix

        # 기획자 입력으로 채운 기간이 있으면 각주에 출처를 구분해 남긴다
        notes = [f'자료원: {s}' for s in srcs if s != MANUAL_SOURCE]
        if applied or extras:
            parts = []
            if applied:
                parts.append(f'계획 라인 {applied}건')
            if extras:
                parts.append(f'별도 막대 {len(extras)}건')
            notes.append(f'집행 기간 {" · ".join(parts)}은 '
                         f'{MANUAL_SOURCE} 값 기준')

        # 보정 특이사항(해석 실패·미매칭·기간 미확보)은 각주에 다 담으면
        # 슬라이드 하단을 넘긴다. 요약만 남기고 상세는 Checklist 로 보낸다.
        if overlay_notes:
            notes.append(f'기간 보정 특이사항 {len(overlay_notes)}건 '
                         f'— Checklist 참조')
            knowledge.add_checklist_item(ChecklistItem(
                type='roadmap_period_overlay',
                severity='warning',
                message=(f'집행 로드맵 기간 보정 특이사항 '
                         f'{len(overlay_notes)}건 — 확인 필요'),
                detail=' | '.join(overlay_notes),
                source='Stage 2 집행 로드맵',
            ))
        notes = notes[:3]                  # L8 각주 상자는 3줄까지

        return SlideSpec('roadmap', {
            'section': '캠페인 집행 로드맵',
            'bars': bars,
            'period_raw': (mm.period_raw if mm else '') or
                          (dataset.daily_report.period_raw if dataset.daily_report else ''),
            'note': note,
            'sources': notes,
        })

    # 소재 칸에 실제 소재명 대신 들어오는 미표기 값 (버리지 않고 라벨만 정규화)
    _CREATIVE_BLANKS = {'-', '–', '미정', 'tbd', 'n/a', 'na', '없음'}

    @staticmethod
    def _creative_label(raw: str) -> str:
        """소재 라벨 — 미표기 값은 읽을 수 있는 문구로 바꾼다"""
        text = (raw or '').strip()
        if not text or text.lower() in ReportSpecBuilder._CREATIVE_BLANKS:
            return '(소재 미표기)'
        return text

    @staticmethod
    def _creative_roadmap(knowledge: CampaignKnowledge,
                          dataset: CampaignDataset) -> Optional[SlideSpec]:
        """
        소재별 집행 로드맵 — CLAUDE.md 핵심 산출물 1번의 소재 축

        매체 단위 로드맵은 행 수 상한 때문에 소재 표기가 병합에 묻히므로,
        같은 계획 라인을 소재 기준으로 다시 묶어 별도 장으로 만든다.
        """
        from utils.roadmap_overlay import apply_period_overlay

        try:
            apply_period_overlay(dataset)       # 멱등 — 기간 보정 반영
        except Exception:
            pass

        lines = [l for l in dataset.plan_lines()
                 if l.creative and l.period_start and l.period_end]
        if not lines:
            return None

        def key(day: str) -> int:
            m, d = day.split('-')
            return int(m) * 31 + int(d)

        merged: Dict[str, dict] = {}
        for l in lines:
            label = ReportSpecBuilder._creative_label(l.creative)
            g = merged.setdefault(label, {
                'label': label, 'media': label, 'product': '',
                'start': l.period_start, 'end': l.period_end,
                'medias': set(), 'src': l.source.label()})
            if key(l.period_start) < key(g['start']):
                g['start'] = l.period_start
            if key(l.period_end) > key(g['end']):
                g['end'] = l.period_end
            if l.media:
                g['medias'].add(l.media)

        bars = sorted(merged.values(), key=lambda g: (key(g['start']), g['label']))
        hidden = 0
        if len(bars) > 14:
            hidden = len(bars) - 14
            bars = bars[:14]

        for g in bars:                          # 라벨에 매체 수를 덧붙인다
            n = len(g.pop('medias'))
            if n > 1:
                g['label'] = f"{g['label']} ({n}개 매체)"

        srcs = sorted({b['src'].split(':')[0] for b in bars if b.get('src')})
        note = f'소재 {hidden}종은 지면 제약으로 미표기' if hidden else None
        mm = dataset.media_mix
        return SlideSpec('roadmap', {
            'section': '소재별 집행 로드맵',
            'bars': bars,
            'period_raw': (mm.period_raw if mm else ''),
            'note': note,
            'sources': [f'자료원: {s}' for s in srcs][:2],
        })

    @staticmethod
    def _creative_cards(knowledge: CampaignKnowledge,
                        dataset: CampaignDataset) -> Optional[SlideSpec]:
        """
        소재 카드 — 캠페인 폴더의 이미지를 소재명에 매칭해 지표와 함께 배치

        이미지가 한 장도 매칭되지 않으면 자리표시자만 남아 소재별 표와 중복되므로
        슬라이드를 만들지 않는다 (사유는 creative_assets 결손으로 Checklist 에 기재됨).
        """
        from utils.creative_assets import match_assets, scan_assets

        dr = dataset.daily_report
        if not dr:
            return None
        rows = [r for r in dr.media_performance
                if r.axis == 'creative' and r.creative]
        if not rows:
            return None

        agg: Dict[str, dict] = {}
        for r in rows:
            label = ReportSpecBuilder._creative_label(r.creative)
            a = agg.setdefault(label, {'imp': 0.0, 'view': 0.0, 'clk': 0.0,
                                       'spend': 0.0})
            m = r.metrics
            a['imp'] += m.impressions or 0
            a['view'] += m.views or 0
            a['clk'] += m.clicks or 0
            a['spend'] += m.spend or 0
        if not agg:
            return None

        try:
            images, videos = scan_assets(knowledge.folder_path)
        except Exception:
            images, videos = [], []
        if not images:
            return None

        ordered = sorted(agg.items(), key=lambda kv: kv[1]['imp'], reverse=True)
        picked = ordered[:5]
        matched = match_assets([name for name, _ in picked], images)
        if not any(matched.values()):
            return None

        cards: List[dict] = []
        for name, a in picked:
            imp, view, clk, spend = a['imp'], a['view'], a['clk'], a['spend']
            lines = [f'노출 {fmt.count_korean(imp)}회']
            if view:
                lines.append(f'조회 {fmt.count_korean(view)}회 · '
                             f'VTR {fmt.pct(view / imp, 1) if imp else "-"}')
                if spend:
                    lines.append(f'CPV {fmt.comma(spend / view)}원')
            elif clk:
                lines.append(f'클릭 {fmt.count_korean(clk)}회 · '
                             f'CTR {fmt.pct(clk / imp, 2) if imp else "-"}')
                if spend:
                    lines.append(f'CPC {fmt.comma(spend / clk)}원')
            path = matched.get(name)
            cards.append({'label': name, 'image': str(path) if path else '',
                          'lines': lines})

        found = sum(1 for c in cards if c['image'])
        sources = [f'자료원: {dr.source_file} 매체 시트 소재별 표']
        sources.append(f'소재 이미지 {found}/{len(cards)}종 반영 — '
                       f'미발견 소재는 자리표시자 표기')
        if len(ordered) > len(picked):
            sources.append(f'노출 상위 {len(picked)}종만 표기 '
                           f'(전체 {len(ordered)}종)')
        if videos:
            sources.append(f'영상 파일 {len(videos)}건은 썸네일 추출 불가로 미표기')

        return SlideSpec('creative_cards', {
            'section': '소재별 집행 결과 — 소재 카드',
            'block_label': '소재 별 노출·효율',
            'headline_parts': [
                {'text': '소재 '},
                {'text': f'{len(ordered)}종', 'emph': True},
                {'text': ' 운영 — 노출 상위 소재 기준'},
            ],
            'cards': cards,
            'sources': sources[:3],
        })

    @staticmethod
    def _purpose_table(knowledge: CampaignKnowledge,
                       dataset: CampaignDataset) -> Optional[List[SlideSpec]]:
        """
        목적별 집행 결과 표 — 매체 시트 '목적별 효율' 표(axis='purpose') 합산

        CLAUDE.md 산출물 1번의 목적 축. 계획축(미디어믹스)에 목적 컬럼이 없는
        파일이 많아 로드맵 시간축으로는 만들 수 없고, 실적축으로 집계한다.
        """
        dr = dataset.daily_report
        if not dr:
            return None
        rows = [r for r in dr.media_performance if r.axis == 'purpose' and r.purpose]
        if len(rows) < 2:
            return None

        agg: Dict[str, dict] = {}
        for r in rows:
            a = agg.setdefault(r.purpose, {'medias': set(), 'spend': 0.0,
                                           'imp': 0.0, 'view': 0.0, 'clk': 0.0})
            m = r.metrics
            if r.media:
                a['medias'].add(r.media)
            a['spend'] += m.spend or 0
            a['imp'] += m.impressions or 0
            a['view'] += m.views or 0
            a['clk'] += m.clicks or 0
        if len(agg) < 2:
            return None

        ordered = sorted(agg.items(), key=lambda kv: kv[1]['imp'], reverse=True)
        q = _totalizer(False)
        tot = {'imp': 0.0, 'view': 0.0, 'clk': 0.0, 'spend': 0.0}
        for _, a in ordered:
            for k in tot:
                tot[k] += q(a[k])

        table_rows: List[List[Any]] = []
        for name, a in ordered:                 # 전량 게재 (넘치면 분할)
            imp = a['imp']
            vtr = (a['view'] / imp) if imp and a['view'] else None
            ctr = (a['clk'] / imp) if imp and a['clk'] else None
            cpv = (a['spend'] / a['view']) if a['view'] and a['spend'] else None
            cpc = (a['spend'] / a['clk']) if a['clk'] and a['spend'] else None
            table_rows.append([
                name if len(name) <= 40 else name[:39] + '…',
                {'t': f"{len(a['medias'])}", 'right': True},
                {'t': fmt.comma(a['spend']), 'right': True},
                {'t': fmt.comma(imp), 'right': True},
                {'t': fmt.comma(a['view']), 'right': True},
                {'t': fmt.comma(a['clk']), 'right': True},
                fmt.pct(vtr, 2) if vtr else '-',
                fmt.pct(ctr, 2) if ctr else '-',
                {'t': fmt.comma(cpv or cpc), 'right': True},
            ])
        total_row = [
            'Total',
            {'t': '-', 'right': True},
            {'t': fmt.comma(tot['spend']), 'right': True},
            {'t': fmt.comma(tot['imp']), 'right': True},
            {'t': fmt.comma(tot['view']), 'right': True},
            {'t': fmt.comma(tot['clk']), 'right': True},
            '-', '-', '-',
        ]
        base = {
            'section': '목적별 집행 결과',
            'block_label': '캠페인 목적 별 집행 결과',
            'headline_parts': [
                {'text': '캠페인 목적 '},
                {'text': f'{len(ordered)}개 구간', 'emph': True},
                {'text': ' 운영 — 노출 순 정렬 · 전량 게재'},
            ],
            'sources': [f'자료원: {dr.source_file} 매체 시트 목적별 표'],
        }
        return _paginate_rows(
            base,
            ['목적', '매체 수', '집행 비용(원)', '노출(회)', '조회(회)',
             '클릭(회)', 'VTR', 'CTR', 'CPV/CPC(원)'],
            table_rows, total_row,
            col_w=[2.4, 0.8, 1.7, 1.6, 1.4, 1.3, 0.9, 0.9, 1.2])

    @staticmethod
    def _creative_table(knowledge: CampaignKnowledge,
                        dataset: CampaignDataset) -> Optional[List[SlideSpec]]:
        """소재별 집행 결과 표 — 매체 시트의 소재축(axis='creative') 합산"""
        dr = dataset.daily_report
        if not dr:
            return None
        rows = [r for r in dr.media_performance if r.axis == 'creative' and r.creative]
        if len(rows) < 2:
            return None

        agg: Dict[str, dict] = {}
        for r in rows:
            a = agg.setdefault(ReportSpecBuilder._creative_label(r.creative), {
                'medias': set(), 'spend': 0.0, 'imp': 0.0,
                'view': 0.0, 'clk': 0.0})
            m = r.metrics
            if r.media:
                a['medias'].add(r.media)
            a['spend'] += m.spend or 0
            a['imp'] += m.impressions or 0
            a['view'] += m.views or 0
            a['clk'] += m.clicks or 0
        if len(agg) < 2:
            return None

        # 비율은 합계에서 다시 계산한다 (평균 금지)
        def ratios(a: dict) -> dict:
            imp = a['imp']
            return {
                'vtr': (a['view'] / imp) if imp and a['view'] else None,
                'ctr': (a['clk'] / imp) if imp and a['clk'] else None,
                'cpv': (a['spend'] / a['view']) if a['view'] and a['spend'] else None,
                'cpc': (a['spend'] / a['clk']) if a['clk'] and a['spend'] else None,
            }

        # 노출 기준 정렬 — 조회 기준으로 두면 조회수가 없는 배너·이미지 소재가
        # 물량과 무관하게 뒤로 밀린다. 행은 절단하지 않고 전량 게재(넘치면 분할).
        ordered = sorted(agg.items(),
                         key=lambda kv: (kv[1]['imp'], kv[1]['view']), reverse=True)
        q = _totalizer(False)
        tot = {'imp': 0.0, 'view': 0.0, 'clk': 0.0, 'spend': 0.0}
        for _, a in ordered:
            for k in tot:
                tot[k] += q(a[k])

        table_rows: List[List[Any]] = []
        for name, a in ordered:
            r = ratios(a)
            table_rows.append([
                name if len(name) <= 40 else name[:39] + '…',
                {'t': f"{len(a['medias'])}", 'right': True},
                {'t': fmt.comma(a['imp']), 'right': True},
                {'t': fmt.comma(a['view']), 'right': True},
                {'t': fmt.comma(a['clk']), 'right': True},
                fmt.pct(r['vtr'], 2) if r['vtr'] else '-',
                fmt.pct(r['ctr'], 2) if r['ctr'] else '-',
                {'t': fmt.comma(r['cpv']), 'right': True},
                {'t': fmt.comma(r['cpc']), 'right': True},
            ])
        total_row = [
            'Total',
            {'t': '-', 'right': True},
            {'t': fmt.comma(tot['imp']), 'right': True},
            {'t': fmt.comma(tot['view']), 'right': True},
            {'t': fmt.comma(tot['clk']), 'right': True},
            '-', '-', '-', '-',
        ]
        base = {
            'section': '소재별 집행 결과',
            'block_label': '소재 별 집행 결과',
            'headline_parts': [
                {'text': '소재 '},
                {'text': f'{len(ordered)}종', 'emph': True},
                {'text': ' 운영 — 노출 순 정렬 · 전량 게재'},
            ],
            'sources': [f'자료원: {dr.source_file} 매체 시트 소재별 표'],
        }
        return _paginate_rows(
            base,
            ['소재', '매체 수', '노출(회)', '조회(회)', '클릭(회)',
             'VTR', 'CTR', 'CPV(원)', 'CPC(원)'],
            table_rows, total_row,
            col_w=[2.9, 0.8, 1.5, 1.5, 1.3, 0.9, 0.9, 1.0, 1.1])

    @staticmethod
    def _summary(knowledge: CampaignKnowledge,
                 dataset: CampaignDataset) -> Optional[SlideSpec]:
        """캠페인 운영 요약 — 데일리 Total 팩트 문장 (tone-guide 상용구)"""
        dr = dataset.daily_report
        if not dr or dr.total.spend is None:
            return None
        t = dr.total

        # 🔴 헤드라인 금액은 '매체비 총합'이다.
        #
        # 예전에는 데일리리포트 Total 행의 집행 금액(t.spend)을 그대로 썼다.
        # 실측 캠페인에서 그 값은 476,725,145원이었지만 실제 매체비는
        # 395,170,000원이었다 — 두 숫자는 다른 것을 뜻하는데 한 자리에서
        # 섞여 쓰였다. 집행 이후 문서(Media Mix 시트 · 포스트바이 총계)에서
        # 확정한 매체비가 있으면 그것을 쓰고, 없을 때만 종전 값으로 물러난다.
        spend_info = dataset.media_spend()
        headline_amount = spend_info.total if spend_info else t.spend
        headline_label = '매체비' if spend_info else '집행 금액'

        parts = [
            {'text': '총 '},
            {'text': fmt.krw_eok(headline_amount), 'emph': True},
            {'text': f' {headline_label}  /  총 노출 '},
            {'text': f'{fmt.count_korean(t.impressions)}회', 'emph': True},
        ]
        if t.views:
            parts += [{'text': ' · 조회 '},
                      {'text': f'{fmt.count_korean(t.views)}회', 'emph': True}]
        if t.clicks:
            parts += [{'text': ' · 클릭 '},
                      {'text': f'{fmt.count_korean(t.clicks)}회', 'emph': True}]
        parts.append({'text': ' 달성'})

        cards = [
            (headline_label, fmt.krw_eok(headline_amount)),
            ('노출', f'{fmt.count_korean(t.impressions)}회'),
            ('조회', f'{fmt.count_korean(t.views)}회' if t.views else '-'),
            ('클릭', f'{fmt.count_korean(t.clicks)}회' if t.clicks else '-'),
        ]
        notes = [f'자료원: {dr.source_file} (최종 데일리 리포트 기준 데이터)']
        if dr.period_raw:
            notes.insert(0, f'기간: {dr.period_raw}')
        # 매체비는 어느 문서의 어느 표에서 왔는지 반드시 병기한다 (claude.md 3.2)
        if spend_info:
            cite = f'매체비: {spend_info.source_label or "집행 결과 문서"}'
            if spend_info.is_verified():
                cite += ' (포스트바이 총계와 일치)'
            elif spend_info.note:
                cite += f' — {spend_info.note}'
            notes.append(cite)
        return SlideSpec('summary', {
            'section': '캠페인 운영 요약',
            'key_parts': parts,
            'cards': cards,
            'sources': notes,
        })

    @staticmethod
    def _daily_trend(knowledge: CampaignKnowledge,
                     dataset: CampaignDataset) -> Optional[SlideSpec]:
        """
        Scheduling — 일자별 집행 추이 + 운영 이벤트

        그리는 구간은 데일리리포트 행 수가 아니라 **문서가 말하는 집행 기간**
        이다(`dataset.campaign_period()`). 행을 그대로 쓰면 캠페인이 끝난 뒤의
        빈 행까지 기간에 들어가, 미디어믹스가 6/29~7/28 인 캠페인이 '55일 ·
        8/22 까지' 로 찍힌다. 잘라낸 행은 각주와 Checklist 에 남긴다
        (claude.md 3.1 — 조용한 소실 금지).
        """
        dr = dataset.daily_report
        if not dr or len(dr.daily_rows) < 5:
            return None

        rows = list(dr.daily_rows)
        use_spend = any(r.metrics.spend for r in rows)

        def val(r) -> float:
            return (r.metrics.spend if use_spend else r.metrics.impressions) or 0

        period = dataset.campaign_period()
        kept = [r for r in rows if period is None or period.contains(r.date)]
        # 기간 밖으로 판정돼 한 행도 안 남으면 기간 쪽을 의심한다. 원본을 살린다.
        if len(kept) < 5:
            kept, period = rows, None

        # 집행이 없는 앞뒤 꼬리는 '집행 기간'이 아니다. 가운데 0 은 사실이므로 둔다.
        while kept and not val(kept[0]):
            kept.pop(0)
        while kept and not val(kept[-1]):
            kept.pop()
        if len(kept) < 5:
            kept = rows

        # 값이 같은 행이 있어도 헷갈리지 않게 동일성으로 뺀다
        kept_ids = {id(r) for r in kept}
        dropped = [r.date for r in rows if id(r) not in kept_ids]
        notes = [f'자료원: {dr.source_file} <일자별 통합> 시트']
        if dropped:
            notes.append(f'집행 기간 {kept[0].date[5:]}~{kept[-1].date[5:]} '
                         f'기준 · 기간 밖 {len(dropped)}일 제외')
            knowledge.add_checklist_item(ChecklistItem(
                type='daily_trend_period',
                severity='warning',
                message=(f'일자별 추이에서 집행 기간 밖 {len(dropped)}일을 '
                         f'제외했어요 — 기간이 맞는지 확인해 주세요.'),
                detail=(f'그린 구간 {kept[0].date}~{kept[-1].date} · '
                        f'제외 {dropped[0]}~{dropped[-1]} ({len(dropped)}일)'
                        + (f' · 기간 출처 {period.source_label}' if period else '')
                        + (f' · {period.note}' if period and period.note else '')),
                source='Stage 2 일자별 추이',
            ))
        if period and period.confidence == 'low':
            notes.append('미디어믹스와 포스트바이의 기간이 달라요 — Checklist 참조')

        events = [{'date': e.date[5:].replace('-', '/'), 'note': e.note}
                  for e in dr.events if period is None or period.contains(e.date)]
        return SlideSpec('daily_trend', {
            'section': 'Scheduling — 일자별 집행 추이',
            'metric_name': '집행 금액' if use_spend else '노출수',
            'categories': [r.date[5:].replace('-', '/') for r in kept],   # MM/DD
            'values': [val(r) for r in kept],
            'events': events[:8],
            'event_total': len(events),
            'sources': notes[:3],
        })

    @staticmethod
    def _aggregate_by_media(rows: List[Any]) -> List[Any]:
        """
        같은 매체의 여러 행을 매체 단위로 합산한다.

        비율 지표는 평균하지 않고 합계에서 다시 계산한다 (노출 가중 무시 방지).
        """
        agg: Dict[str, dict] = {}
        for mp in rows:
            a = agg.setdefault(mp.media, {'spend': 0.0, 'imp': 0.0,
                                          'view': 0.0, 'clk': 0.0})
            m = mp.metrics
            a['spend'] += m.spend or 0
            a['imp'] += m.impressions or 0
            a['view'] += m.views or 0
            a['clk'] += m.clicks or 0

        out = []
        for media, a in agg.items():
            out.append(type('Row', (), {
                'media': media, 'product': '', 'budget': None,
                'metrics': type('M', (), {
                    'spend': a['spend'], 'impressions': a['imp'],
                    'views': a['view'], 'clicks': a['clk'],
                    'ctr': (a['clk'] / a['imp']) if a['imp'] else None,
                    'vtr': (a['view'] / a['imp']) if a['imp'] else None,
                    'cpm': (a['spend'] / a['imp'] * 1000) if a['imp'] else None,
                    'cpc': (a['spend'] / a['clk']) if a['clk'] else None,
                    'cpv': (a['spend'] / a['view']) if a['view'] else None,
                })()
            })())
        return out

    @staticmethod
    def _media_table(knowledge: CampaignKnowledge,
                     dataset: CampaignDataset) -> Optional[List[SlideSpec]]:
        """Digital 매체별 집행 결과 표"""
        sources: List[str] = []
        dr = dataset.daily_report

        # 원천 우선순위: 데일리 매체별 Total 블록 > 상품축 합산 > 포스트바이 요약
        #
        # media_performance 를 축 구분 없이 합산하면 같은 매체가 상품축·타겟팅축·
        # 소재축으로 중복 계상되어 총액이 배로 부푼다. 반드시 한 축만 쓴다.
        if dr and dr.media_totals:
            perf = list(dr.media_totals)
            sources.append(f'자료원: {dr.source_file} <일자별 통합> 매체별 Total')
        elif dr and any(mp.axis == 'product' for mp in dr.media_performance):
            perf = ReportSpecBuilder._aggregate_by_media(
                [mp for mp in dr.media_performance if mp.axis == 'product'])
            sources.append(f'자료원: {dr.source_file} <상품 별 효율> 매체 단위 합산')
        elif dataset.postbuy and dataset.postbuy.campaign_summary:
            perf = list(dataset.postbuy.campaign_summary)
            sources.append(f'자료원: {dataset.postbuy.source_file} Campaign Summary')
        else:
            return None

        def spend_of(p) -> float:
            m = p.metrics
            value = m.spend if m.spend is not None else getattr(p, 'budget', None)
            return value or 0.0

        perf = [p for p in perf
                if p.media and str(p.media).strip().lower() != 'total']
        if not perf:
            return None

        # 원천 간 총액 불일치는 임의로 택하지 않고 양쪽을 병기하고 Checklist 에 기재
        if (dr and dr.media_totals and dataset.postbuy
                and dataset.postbuy.campaign_summary):
            ours = sum(spend_of(p) for p in dr.media_totals)
            theirs = sum(spend_of(p) for p in dataset.postbuy.campaign_summary)
            if ours and theirs and abs(ours - theirs) / ours > 0.01:
                sources.append(
                    f'포스트바이 Campaign Summary 합계 {fmt.krw_eok(theirs)}과 '
                    f'차이 있음 — 표는 데일리리포트 매체별 Total 기준')
                knowledge.add_checklist_item(ChecklistItem(
                    type='data_mismatch',
                    severity='warning',
                    message=('매체별 집행 총액 원천 간 불일치 — '
                             f'데일리 {fmt.krw_eok(ours)} vs '
                             f'포스트바이 {fmt.krw_eok(theirs)}'),
                    detail=('매체별 집행 결과 표는 데일리리포트 <일자별 통합> 매체별 '
                            'Total 기준으로 작성됨. 포스트바이 Campaign Summary 표의 '
                            '파싱 범위를 확인할 것'),
                    source='Stage 2 매체별 집행 결과',
                ))

        # 행을 절단하지 않는다 — 집행 금액 순으로 정렬 후 전량 게재(넘치면 분할)
        shown = sorted(perf, key=spend_of, reverse=True)

        # Total 은 전체 매체 합계 (전량 표기이므로 표시값 기준 반올림 합)
        q = _totalizer(False)
        tot = {'spend': 0.0, 'imp': 0.0, 'view': 0.0, 'clk': 0.0}
        for p in perf:
            m = p.metrics
            tot['spend'] += q(spend_of(p))
            tot['imp'] += q(m.impressions)
            tot['view'] += q(m.views)
            tot['clk'] += q(m.clicks)

        header = ['매체', '집행 비용(원)', '노출(회)', '조회(회)', '클릭(회)',
                  'VTR', 'CTR', 'CPM(원)', 'CPC(원)']
        rows_out: List[List[Any]] = []
        for p in shown:
            m = p.metrics
            rows_out.append([
                p.media,
                {'t': fmt.comma(spend_of(p)), 'right': True},
                {'t': fmt.comma(m.impressions), 'right': True},
                {'t': fmt.comma(m.views), 'right': True},
                {'t': fmt.comma(m.clicks), 'right': True},
                fmt.pct(m.vtr, 2) if m.vtr else '-',
                fmt.pct(m.ctr, 2) if m.ctr else '-',
                {'t': fmt.comma(m.cpm), 'right': True},
                {'t': fmt.comma(m.cpc), 'right': True},
            ])

        total_row = [
            'Total',
            {'t': fmt.comma(tot['spend']), 'right': True},
            {'t': fmt.comma(tot['imp']), 'right': True},
            {'t': fmt.comma(tot['view']), 'right': True},
            {'t': fmt.comma(tot['clk']), 'right': True},
            '-', '-', '-', '-',
        ]
        base = {
            'section': 'Digital 매체별 집행 결과',
            'block_label': 'Digital 매체 별 집행 결과',
            'headline_parts': [
                {'text': 'Digital '},
                {'text': f'{len(perf)}개 매체', 'emph': True},
                {'text': ' 집행 결과 — 상세 지표 하기 표 기준'},
            ],
            'sources': sources,
        }
        return _paginate_rows(base, header, rows_out, total_row, col_w=None)

    @staticmethod
    def _kpi(knowledge: CampaignKnowledge,
             dataset: CampaignDataset) -> Optional[List[SlideSpec]]:
        """KPI 달성율 — Full: 포스트바이 확정 목표 / Lite: 기획자 입력값"""
        chart_items: List[dict] = []
        table_rows: List[List[Any]] = []
        sources: List[str] = []

        if dataset.postbuy and dataset.postbuy.kpi_targets:
            targets = dataset.postbuy.kpi_targets
            primary = [k for k in targets if not k.product][:3] or targets[:3]
            for k in primary:
                if k.achievement_rate:
                    chart_items.append({
                        'label': k.kpi_name or k.media or k.scope,
                        'pct': int(round(k.achievement_rate * 100)),
                    })
            # 강조 셀은 소수만 (design-spec §4) — 최고 달성율 1건만 하이라이트.
            # 행은 절단하지 않고 전량 게재한다 (넘치면 이어지는 표 슬라이드로 분할).
            rates = [k.achievement_rate for k in targets if k.achievement_rate]
            best = max(rates) if rates else None
            for k in targets:
                table_rows.append([
                    k.scope, k.media, k.kpi_name,
                    {'t': fmt.comma(k.target), 'right': True},
                    {'t': fmt.comma(k.actual), 'right': True},
                    {'t': fmt.pct(k.achievement_rate),
                     'hilite': bool(best and k.achievement_rate == best)},
                ])
            sources.append(f'자료원: {dataset.postbuy.source_file} KPI 달성 현황')
            headline = 'KPI 목표 대비 달성율 — 포스트바이 확정 목표 기준'
        else:
            gap = dataset.gap('kpi_target')
            if not gap or gap.resolution != GAP_FILLED or not gap.filled_value:
                return None
            dr = dataset.daily_report
            actual_map = {}
            if dr:
                actual_map = {'노출': dr.total.impressions, 'IMPRESSION': dr.total.impressions,
                              '조회': dr.total.views, 'VIEW': dr.total.views,
                              '클릭': dr.total.clicks, 'CLICK': dr.total.clicks}
            for row in gap.filled_value:
                kpi_name = str(row.get('KPI', '')).strip()
                target = None
                try:
                    target = float(str(row.get('목표치', '')).replace(',', ''))
                except ValueError:
                    pass
                actual = None
                for key, v in actual_map.items():
                    if key in kpi_name.upper() or key in kpi_name:
                        actual = v
                        break
                rate = (actual / target) if (target and actual) else None
                if rate:
                    chart_items.append({'label': kpi_name,
                                        'pct': int(round(rate * 100))})
                table_rows.append([
                    row.get('매체', ''), row.get('상품', ''), kpi_name,
                    {'t': fmt.comma(target), 'right': True},
                    {'t': fmt.comma(actual), 'right': True},
                    {'t': fmt.pct(rate) if rate else '-'},
                ])
            sources.append('목표치: 기획자 직접 입력 (Stage 1.5 검증 화면)')
            if dr:
                sources.append(f'실적: {dr.source_file}')
            headline = 'KPI 목표 대비 달성율 — 기획자 확정 목표 기준'

        if not chart_items and not table_rows:
            return None

        header = ['구분', '매체', 'KPI', '목표', '집행 결과', '달성율']
        # 첫 장은 차트 옆 좁은 표라 여유 있게 담기는 만큼만, 나머지는 이어지는
        # 전폭 표 슬라이드로 분할한다 (KPI 행 절단 금지).
        first_budget = 14
        first_rows = table_rows[:first_budget]
        rest_rows = table_rows[first_budget:]

        slides: List[SlideSpec] = [SlideSpec('kpi', {
            'section': '전체 KPI 달성률',
            'headline': headline,
            'chart_items': chart_items[:4],
            'table_header': header,
            'table_rows': first_rows,
            'sources': sources,
        })]
        if rest_rows:
            base = {
                'section': '전체 KPI 달성률',
                'block_label': '매체 · 상품별 KPI 달성 현황 (이어짐)',
                'headline_parts': [{'text': 'KPI 달성 현황 — 이어지는 상세'}],
                'sources': sources,
            }
            slides += _paginate_rows(
                base, header, rest_rows, None,
                col_w=[1.1, 1.3, 1.2, 1.2, 1.2, 0.9])
        return slides

    @staticmethod
    def _search_buzz(dataset: CampaignDataset) -> Optional[SlideSpec]:
        """검색량·버즈량 헤드라인 인용 (Full 모드, 원문 텍스트 그대로)"""
        pb = dataset.postbuy
        if not pb:
            return None
        quotes = []
        for kind in ('search', 'buzz'):
            for sec in pb.sections_of(kind):
                for h in sec.headlines:
                    if ('우위' in h or '증가' in h or '比' in h) and len(h) < 90:
                        quotes.append({'label': sec.title, 'text': h})
                        break
        if not quotes:
            return None
        return SlideSpec('quotes', {
            'section': '검색량 · 버즈량 트렌드',
            'quotes': quotes[:3],
            'sources': [f'자료원: {pb.source_file} (Cheil Keybox / SMA / 네이버 데이터랩 기준)'],
        })

    @staticmethod
    def _lesson(dataset: CampaignDataset) -> Optional[List[SlideSpec]]:
        """
        Lesson Learned — 포스트바이 원문(또는 기획자 입력)을 분석형 카드로 재구성.

        원본의 [발견 → 근거] 위계를 살려 카드마다 헤드라인 + 근거 불릿으로
        묶고, 분량이 많으면 여러 장으로 나눈다 (내용 축약 금지).
        """
        bullets: List[str] = []
        sources: List[str] = []
        if dataset.postbuy and dataset.postbuy.lesson_learned:
            seen = set()
            for t in dataset.postbuy.lesson_learned:
                t = t.strip()
                if t and t not in seen and not t.lower().startswith('lesson'):
                    seen.add(t)
                    bullets.append(t)
            sources.append(f'자료원: {dataset.postbuy.source_file} Lesson Learned')
        else:
            gap = dataset.gap('lesson_learned')
            if gap and gap.resolution == GAP_FILLED and gap.filled_value:
                bullets = [ln.strip() for ln in str(gap.filled_value).splitlines()
                           if ln.strip()]
                sources.append('기획자 직접 입력 (Stage 1.5 검증 화면)')
        if not bullets:
            return None

        cards = _lesson_cards(bullets)
        if not cards:
            return None
        pages, dropped = _pack_lesson_pages(cards)
        n = len(pages)
        shown_cards = len(cards) - dropped
        slides: List[SlideSpec] = []
        for pi, page in enumerate(pages, 1):
            sec = 'Lesson Learned' if n == 1 else f'Lesson Learned ({pi}/{n})'
            headline = [
                {'text': '캠페인 운영에서 도출한 '},
                {'text': f'핵심 학습 {shown_cards}건', 'emph': True},
                {'text': ' 정리', 'break': True},
                {'text': '매체 운영·타겟팅·소재 전략의 '},
                {'text': '차기 개선 방향', 'emph': True},
                {'text': ' 제시'},
            ] if pi == 1 else [
                {'text': '차기 캠페인 실행을 위한 '},
                {'text': '세부 학습 사항', 'emph': True},
                {'text': ' (이어짐)'},
            ]
            page_sources = list(sources)
            if pi == n and dropped:
                page_sources.append(
                    f'그 외 세부 제언 {dropped}건은 포스트바이 원문 참조')
            slides.append(SlideSpec('lesson', {
                'section': sec,
                'headline_parts': headline,
                'cards': page,
                'sources': page_sources,
            }))
        return slides

    @staticmethod
    def _insight(insights: Optional[InsightSet]) -> Optional[List[SlideSpec]]:
        """
        Lesson Learned (자동 도출) — 발견 → 평가 → 제언 3단 논법 블록.

        5축에서 최대 12건이 나오므로 한 장에 4건씩 나눠 싣는다.
        한 장에 몰아 넣으면 렌더러의 자동 맞춤이 뒷건을 조용히 버린다.
        """
        if not insights or not insights.insights:
            return None
        rows = insights.insights
        # 장수 제한 없음 — 도출된 인사이트를 한 건도 버리지 않는다 (AE 결정).
        # 한 장에 많이 넣을수록 렌더러 밀도 사다리가 폰트를 줄이고 근거를
        # '…' 로 잘라내므로, 장당 2건으로 넉넉히 두고 장수를 늘린다.
        per_page = 2

        axis_labels: List[str] = []
        for i in rows:
            label = AXIS_LABELS.get(i.axis, i.axis)
            if label not in axis_labels:
                axis_labels.append(label)

        # 균등 분할 — 단순 청크는 7건이 3+3+1 이 되어 마지막 장이 비어 보인다.
        # 장수는 그대로 두고 3+2+2 로 고르게 나눈다.
        n = max(1, (len(rows) + per_page - 1) // per_page)
        base, extra = divmod(len(rows), n)
        pages, cursor = [], 0
        for p in range(n):
            size = base + (1 if p < extra else 0)
            pages.append(rows[cursor:cursor + size])
            cursor += size
        slides: List[SlideSpec] = []

        for pi, page in enumerate(pages, 1):
            blocks = [{
                'finding': i.finding,
                'context': i.context,
                'recommendation': i.recommendation,
                'evidence': list(i.evidence),
                'axis': AXIS_LABELS.get(i.axis, i.axis),
            } for i in page]

            if pi == 1:
                headline = (f"{' · '.join(axis_labels)} {len(axis_labels)}개 축 기준 "
                            f"시사점 {len(rows)}건 도출")
            else:
                page_axes: List[str] = []
                for i in page:
                    label = AXIS_LABELS.get(i.axis, i.axis)
                    if label not in page_axes:
                        page_axes.append(label)
                headline = f"{' · '.join(page_axes)} 축 세부 시사점"

            sources: List[str] = []
            for i in page:
                for s in i.sources:
                    if s not in sources:
                        sources.append(s)

            section = 'Lesson Learned' if n == 1 else f'Lesson Learned ({pi}/{n})'
            slides.append(SlideSpec('insight', {
                'section': section,
                'headline': headline,
                'blocks': blocks,
                'sources': sources[:2],
            }))
        return slides

    @staticmethod
    def _strategy(insights: Optional[InsightSet]) -> Optional[SlideSpec]:
        """차기 캠페인 전략 방향 — 영역별 카드"""
        if not insights or not insights.strategies:
            return None
        items = insights.strategies
        cards = [{'area': s.area, 'direction': s.direction, 'basis': s.basis}
                 for s in items]
        headline = (f"{' · '.join(s.area for s in items)} "
                    f"{len(items)}개 영역의 차기 캠페인 방향 도출")

        sources: List[str] = []
        for s in items:
            for src in s.sources:
                if src not in sources:
                    sources.append(src)
        return SlideSpec('strategy', {
            'section': '차기 캠페인 전략 방향',
            'headline': headline,
            'cards': cards,
            'sources': sources[:2],
        })
