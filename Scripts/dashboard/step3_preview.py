# -*- coding: utf-8 -*-
"""
STEP 3 — 슬라이드 미리보기 · 보고서 생성 (Stage 4 + Stage 4.5)

레지스트리(block_id)로 슬라이드를 나눠 보여주고, 한 블록만 다시 만들어
교체할 수 있게 한다. 파싱(Stage 1)은 다시 하지 않는다.

  실측: 파싱 8.8초 / 덱 구성 0.01초 / 렌더 0.46초
  → 부분 리렌더링 0.26초 (전체 재실행 대비 35배)

자유 서술형 수정 지시 해석(Claude API 연동)은 5단계에서 붙인다.
이 화면은 그 자리(수정 지시 입력창)를 마련하되, 지금은 규칙 기반
프리셋으로만 동작한다 — 키가 없어도 전 기능이 동작해야 함 (Rule Book 1.4).
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st
import streamlit.components.v1 as components

from models.campaign_knowledge import CampaignKnowledge
from utils import slide_preview as SP
from dashboard import state, theme_css as T

KEY_SPEC = state.KEY_SPEC
KEY_OPTIONS = 'ax_block_options'


# ═══════════════════════════ 미리보기 텍스트 추출

def _preview_lines(slide) -> List[str]:
    """
    SlideSpec 페이로드에서 사람이 읽을 문안을 뽑는다.

    PPTX 를 이미지로 렌더하려면 LibreOffice 의존이 붙어 배포가 무거워지므로
    텍스트 미리보기로 대신한다.
    """
    p = slide.payload or {}
    out: List[str] = []

    def push(v, prefix=''):
        if v is None:
            return
        if isinstance(v, str):
            if v.strip():
                out.append(prefix + v.strip())
        elif isinstance(v, dict):
            if 'text' in v:
                push(v.get('text'), prefix)
            elif 't' in v:
                push(v.get('t'), prefix)
        elif isinstance(v, (list, tuple)):
            for x in v:
                push(x, prefix)

    for key in ('section', 'block_label', 'title'):
        push(p.get(key))
    push(p.get('headline_parts'))
    push(p.get('headline'))

    for key in ('items', 'bullets', 'lines', 'notes', 'quotes'):
        for x in (p.get(key) or []):
            push(x, '· ')

    rows = p.get('rows') or []
    if rows:
        out.append(f'[표] {len(rows)}행')
        for r in rows[:4]:
            cells = []
            for c in (r if isinstance(r, (list, tuple)) else [r]):
                if isinstance(c, dict):
                    cells.append(str(c.get('t', '')))
                else:
                    cells.append(str(c))
            out.append('   ' + ' | '.join(cells))
        if len(rows) > 4:
            out.append(f'   … 외 {len(rows) - 4}행')

    for src in (p.get('sources') or []):
        push(src, '※ ')
    return out or ['(문안 없음 — 도표·차트 슬라이드)']


# ═══════════════════════════ 부분 리렌더링

def _rebuild(block_id: str, label: str) -> None:
    """한 블록만 다시 만들어 교체한다."""
    from utils.report import ReportSpecBuilder

    spec = state.get(KEY_SPEC)
    knowledge = state.get_knowledge()
    dataset = state.get(state.KEY_DATASET)
    if spec is None or knowledge is None or dataset is None:
        st.warning('먼저 리포트를 만들어 주세요.')
        return

    options = st.session_state.get(KEY_OPTIONS, {}).get(block_id, {})
    try:
        new_slide = ReportSpecBuilder.rebuild_block(
            block_id, knowledge, dataset, spec.insights, options)
    except Exception as e:
        st.error(f'재생성 실패: {e}')
        return

    if new_slide is None:
        st.warning(f'{label} — 다시 만든 결과가 비어 있어서 기존 슬라이드를 그대로 뒀어요.')
        return
    if spec.replace_block(block_id, new_slide):
        state.put(KEY_SPEC, spec)
        st.success(f'{label} 슬라이드를 다시 만들었어요.')
    else:
        st.warning('교체할 슬라이드를 찾지 못했어요.')


KEY_DRAWER = 'ax_chat_open'      # 문안 수정 패널이 잡고 있는 block_id
KEY_SEL = 'ax_sel_slide'         # 고른 슬라이드 인덱스 (None = 아직 안 고름)
KEY_TOP = 'ax_deck_to_top'       # 이 화면에 막 들어왔다 — 첫 장으로 스크롤


PER_ROW = 3


def arm_scroll_top() -> None:
    """
    리포트 화면을 '막 열었을 때'의 상태로 맞춘다 — 고른 장 없음 + 첫 장으로 스크롤.

    Streamlit 은 단계를 넘어가도 스크롤 위치를 그대로 들고 간다. 2단계 맨
    아래의 [리포트 만들기] 에서 넘어오면 3단계도 화면 한복판부터 보인다.
    """
    st.session_state[KEY_SEL] = None
    st.session_state[KEY_DRAWER] = None
    st.session_state[KEY_TOP] = True


def _scroll_to_first_slide() -> None:
    """
    첫 썸네일로 스크롤한다. 플래그를 소모해 **들어온 직후 한 번만** 움직인다.

    한 번만 부르면 듣지 않는다. Streamlit 이 화면을 다 그린 뒤 이전 스크롤
    위치를 되돌려 놓기 때문에, 잠깐(약 1초) 다시 붙잡고 있어야 한다. 그 사이
    사용자가 스크롤·클릭하면 즉시 손을 뗀다 — 조작을 빼앗지 않기 위함이다.
    """
    if not st.session_state.pop(KEY_TOP, False):
        return
    # st.markdown 안의 <script> 는 실행되지 않는다. 컴포넌트 iframe 에서
    # 부모 문서를 잡는다. 제목이 잘리지 않게 두는 여백은 CSS 쪽
    # `.ax-thumb { scroll-margin-top }` 이 맡는다.
    components.html(
        """<script>
        (function () {
          const win = window.parent, doc = win.document;
          let held = false, n = 0;
          const release = () => { held = true; };
          ['wheel', 'touchstart', 'keydown', 'mousedown'].forEach(
              (e) => win.addEventListener(e, release, {once: true, passive: true}));
          const id = setInterval(function () {
            const el = doc.querySelector('.ax-thumb');
            if (el) { el.scrollIntoView({block: 'start'}); }
            if (held || ++n >= 15) { clearInterval(id); }
          }, 80);
        })();
        </script>""",
        height=0)


def _first_editable(spec, registry) -> int:
    """
    문안 슬롯이 있는 첫 번째 장.

    '문안을 고칠 수 있는 장으로 이동' 버튼의 목적지다. 화면을 열 때의 기본
    선택으로는 쓰지 않는다 — 고르지 않은 장이 골라진 것처럼 보인다.
    """
    for i, sl in enumerate(spec.slides):
        bd = registry.get(sl.block_id)
        if bd and bd.editable:
            return i
    return 0


# 레지스트리에 없는 구조 슬라이드(표지·목차·간지 등)의 화면 표기.
# 예전에는 내부 키를 그대로 노출해 버튼에 'toc' · 'divider' 가 찍혔다.
# 사용자에게 보이는 이름과 코드의 식별자는 분리한다.
_KIND_LABEL = {
    'cover': '표지',
    'toc': '목차',
    'divider': '간지',
    'checklist': 'Checklist',
    'summary': '집행 요약',
    'eod': '마무리',
    'quotes': '인용',
    'insight': '인사이트',
    'lesson': 'Lesson Learned',
    'kpi': 'KPI 달성',
    'roadmap': '집행 로드맵',
    'strategy': '캠페인 전략',
    'media_table': '매체별 성과',
    'postbuy_table': '포스트바이 표',
    'daily_trend': '일자별 추이',
    'creative_cards': '소재별 결과',
    'placement_cards': '게재 결과',
    'ov_goal': '캠페인 목표',
    'ov_strategy': '전략 방향',
    'ov_roadmap': '캠페인 로드맵',
}


def _thumb_card(sl, spec, registry, i: int, sel: Optional[int]) -> None:
    """썸네일 한 장 + 선택 버튼."""
    bd = registry.get(sl.block_id)
    label = ((bd.label if bd else '')
             or _KIND_LABEL.get(sl.kind, '')
             or sl.kind or '슬라이드')
    st.markdown(
        f'<div class="ax-thumb {"on" if i == sel else ""}">'
        + SP.slide_html(sl, spec.campaign_tag, width=300, index=i + 1)
        + '</div>', unsafe_allow_html=True)
    # 썸네일 자체를 누르게 하려면 커스텀 컴포넌트가 필요하다. 바로 아래
    # 버튼을 라벨로 써서 의존성 없이 같은 동선을 만든다.
    # 표시는 '수정 가능한 쪽'에만 붙인다. 14장 중 3장만 문안 수정 대상이라
    # 반대로 붙이면 거의 모든 버튼에 같은 꼬리표가 달려 읽기 어려워진다.
    mark = '  ·  수정 가능' if (bd and bd.editable) else ''
    if st.button(f'{i + 1}. {label}{mark}', key=f'ax_sel_{i}',
                 width='stretch',
                 type='primary' if i == sel else 'secondary'):
        st.session_state[KEY_SEL] = i
        st.session_state[KEY_DRAWER] = (
            sl.block_id if (bd and bd.editable) else None)
        st.rerun()


def _detail(sl, spec, registry, i: int) -> None:
    """
    선택한 슬라이드의 상세 — 큰 미리보기 + 수정 요청.

    그리드 맨 아래가 아니라 **고른 장이 있는 줄 바로 밑**에 편다. 썸네일과
    입력창 사이를 눈이 오가지 않아도 되게 하는 배치다.
    """
    bd = registry.get(sl.block_id)
    left, right = st.columns([1.35, 1], gap='large')
    with left:
        st.markdown(
            SP.slide_html(sl, spec.campaign_tag, width=560, index=i + 1),
            unsafe_allow_html=True)
        st.markdown(
            '<p class="ax-lead sm">'
            '<span class="kbr">미리보기는 실제 PPT 와</span> '
            '<span class="kbr">글자 크기·줄바꿈이 다를 수 있어요.</span></p>',
            unsafe_allow_html=True)
    with right:
        if bd and bd.editable:
            render_drawer(sl.block_id)
        else:
            st.markdown('<div class="af-drawer-title">문안 수정</div>',
                        unsafe_allow_html=True)
            st.markdown(
                '<div class="af-empty">'
                '<span class="kbr">이 장은 표·차트라서</span> '
                '<span class="kbr">고칠 문안 슬롯이 없어요.</span><br>'
                '<span class="kbr">수치를 바꾸시려면</span> '
                '<span class="kbr">2단계의 상세 확인에서 고쳐 주세요.</span>'
                '</div>', unsafe_allow_html=True)
            nxt = _first_editable(spec, registry)
            if nxt != i and st.button('문안을 고칠 수 있는 장으로 이동',
                                      key=f'ax_jump_{i}', width='stretch'):
                st.session_state[KEY_SEL] = nxt
                st.session_state[KEY_DRAWER] = spec.slides[nxt].block_id
                st.rerun()


def _grid(spec, registry) -> None:
    """
    썸네일 그리드. 고른 장이 속한 줄 바로 아래에 상세를 펼친다.

    화면에 들어온 직후에는 아무 장도 고르지 않는다. 예전에는 첫 수정 가능한
    장을 미리 골라 뒀는데, AE 가 고른 적 없는 장이 파랗게 눌린 채 상세까지
    펼쳐져 있어 '왜 이 장이 열려 있지' 로 읽혔다.
    """
    slides = spec.slides
    sel = st.session_state.get(KEY_SEL)
    if sel is not None:
        sel = max(0, min(int(sel), len(slides) - 1))

    for start in range(0, len(slides), PER_ROW):
        row = st.columns(PER_ROW, gap='small')
        for j, col in enumerate(row):
            i = start + j
            if i >= len(slides):
                break
            with col:
                _thumb_card(slides[i], spec, registry, i, sel)
        if sel is not None and start <= sel < start + PER_ROW:
            _detail(slides[sel], spec, registry, sel)
            st.divider()


KEY_CHAT = 'ax_chat'          # {block_id: [{'role','text','mode','note'}]}
KEY_PENDING = 'ax_pending'    # {block_id: 전송 대기 중인 지시문}


def _chat_log(block_id: str) -> List[Dict[str, Any]]:
    log = st.session_state.setdefault(KEY_CHAT, {})
    return log.setdefault(block_id, [])


def _revise_and_rerender(bd, slide, instruction: str, use_api: bool) -> None:
    """
    지시문 → (Claude API 또는 프리셋) → 문안 반영 → 해당 블록만 리렌더

    파싱은 다시 하지 않는다. 표현 계층만 바꾼다.
    """
    from utils.report import revise as R

    project_root = state.get(state.KEY_PROJECT_ROOT)
    lines = R.extract_lines(slide)
    if not lines:
        st.warning('이 슬라이드에는 고칠 문안이 없어요.')
        return

    req = R.ReviseRequest(bd.block_id, bd.label, lines, instruction)
    with st.spinner('문안을 다듬는 중...'):
        result = R.revise(req, project_root=project_root, allow_api=use_api)

    if not result.lines:
        st.error(f'수정 실패 — {result.error}')
        return
    if not R.apply_lines(slide, result.lines):
        st.error('문안 슬롯 수가 맞지 않아 반영하지 않았어요.')
        return

    state.put(KEY_SPEC, state.get(KEY_SPEC))     # 세션에 반영 고정

    # 감사 — Checklist 에 API 사용 사실을 남긴다 (Rule Book 1.4-5)
    if result.used_api:
        _record_api_use(bd.label)

    log = _chat_log(bd.block_id)
    log.append({'role': 'ae', 'text': instruction})
    log.append({
        'role': 'system',
        'text': '\n'.join(result.lines),
        'mode': result.mode,
        'note': (result.note if result.used_api
                 else f'{result.note} · 강등 사유: {result.error}'),
    })


def _record_api_use(label: str) -> None:
    """API 로 수정한 문안 건수를 Checklist 에 누적 기재"""
    from models.checklist import ChecklistItem
    knowledge = state.get_knowledge()
    if knowledge is None:
        return
    counter = st.session_state.setdefault('ax_api_calls', {})
    counter[label] = counter.get(label, 0) + 1
    total = sum(counter.values())
    knowledge.add_checklist_item(ChecklistItem(
        type='api_revised_copy',
        severity='info',
        message=f'[자동생성] Claude API 로 수정한 문안 {total}건 — 문구 검증 필요',
        detail=('수정 슬라이드: '
                + ', '.join(f'{k} {v}건' for k, v in counter.items())
                + ' / 전송 범위는 해당 슬라이드 문안과 지시문으로 한정됨'),
        source='step3_preview:_revise_and_rerender',
    ))
    from utils.checklist_manager import ChecklistManager
    ChecklistManager.deduplicate_checklist(knowledge)


EXAMPLES = [
    '이 슬라이드의 톤앤매너를 레슨런 중심으로 고쳐줘',
    '숫자 근거를 문장 맨 앞에 배치해줘',
    '문장을 더 짧게, 명사형으로 끝내줘',
]


def render_drawer(block_id: Optional[str] = None) -> None:
    """
    선택한 슬라이드의 문안 수정 패널.

    2026.09.07 — 사이드바를 없애면서 우측 드로어에서 본문 2단 레이아웃의
    오른쪽 칼럼으로 옮겼다. 함수 이름과 시그니처는 유지한다.

    수정 결과는 [적용/취소] 없이 즉시 반영한다. 되돌리기는 '원래 문안으로'
    버튼으로만 제공한다. 전송 전 공개(claude.md 1.2)는 그대로 지킨다.
    """
    from utils.report import ReportSpecBuilder
    from utils.report import revise as R

    block_id = block_id or st.session_state.get(KEY_DRAWER)
    spec = state.get(KEY_SPEC)
    if spec is None:
        return

    bd = ({b.block_id: b for b in ReportSpecBuilder.registry()}.get(block_id)
          if block_id else None)
    slide = (next((x for x in spec.slides if x.block_id == block_id), None)
             if block_id else None)

    if bd is None or slide is None:
        # 표·차트 슬라이드는 문안 슬롯이 없어 수정 대상이 아니다.
        st.markdown('<div class="af-drawer-title">문안 수정</div>',
                    unsafe_allow_html=True)
        st.markdown(
            '<div class="af-empty">이 슬라이드는 문안 수정 대상이 아니에요.'
            '<br>표·차트의 수치는 2단계의 [상세 보기]에서 고쳐 주세요.</div>',
            unsafe_allow_html=True)
        return

    st.markdown(f'<div class="af-drawer-title">{bd.label}</div>',
                unsafe_allow_html=True)
    st.caption('문안만 고쳐요 — 수치와 표는 그대로예요.')

    project_root = state.get(state.KEY_PROJECT_ROOT)
    ok, reason = R.api_available(project_root)

    # ── 입력창을 맨 위에 둔다. 이 패널에서 할 일은 '요청을 적는 것' 하나다.
    instr_key = f'instr_{block_id}'
    fill_key = f'instr_fill_{block_id}'
    # 예시 버튼이 넣어 둔 값을 **위젯 생성 전에** 옮긴다. 위젯이 만들어진
    # 뒤에 같은 키를 건드리면 Streamlit 이 StreamlitAPIException 을 던지고
    # (`cannot be modified after the widget ... is instantiated`) 값이
    # 조용히 반영되지 않는다.
    if fill_key in st.session_state:
        st.session_state[instr_key] = st.session_state.pop(fill_key)
    instruction = st.text_area(
        '지시문', key=instr_key, height=92,
        placeholder='어떻게 고칠지 적어 주세요',
        label_visibility='collapsed')

    text = (instruction or '').strip()

    # ── 예시는 눌러서 바로 채워지는 버튼이다. 정적 텍스트를 버튼처럼
    # 보이게 두면 눌러도 반응이 없어 '비활성'으로 읽힌다.
    st.markdown('<div class="af-sub">이렇게 지시해 보세요</div>',
                unsafe_allow_html=True)
    for n, ex in enumerate(EXAMPLES):
        if st.button(ex, key=f'ex_{block_id}_{n}', width='stretch'):
            st.session_state[fill_key] = ex
            st.rerun()

    # ── 지난 수정 이력
    log = _chat_log(block_id)
    if log:
        st.markdown('<div class="af-sub">수정 이력</div>',
                    unsafe_allow_html=True)
        for turn in log:
            if turn['role'] == 'ae':
                st.markdown(f'**요청** · {turn["text"]}')
            else:
                tag = ('Claude API' if turn.get('mode') == 'api'
                       else '프리셋(규칙)')
                st.caption(f'{tag} · {turn.get("note", "")}')
                st.text(turn['text'])

    if ok:
        # 전송 내용은 접지 않고 그대로 보여 준다. '무엇이 나가는지 보고
        # 누른다'는 조건(claude.md 1.2)은 펼쳐야 보이는 상자로는 지켜지지
        # 않는다. 접이식 UI 를 쓰지 않는다는 화면 원칙(claude.md 5)과도 맞다.
        st.markdown('<div class="af-sub">전송되는 내용 — 이것만 나가요</div>',
                    unsafe_allow_html=True)
        st.code(R.disclosure(R.ReviseRequest(
            bd.block_id, bd.label, R.extract_lines(slide),
            text or '(지시문 미입력)')), language=None)
        st.caption(f'· {reason}')
        send_label = '전송하고 수정'
    else:
        T.note(f'Claude API 미사용 — {reason} · '
               '규칙 기반 프리셋으로 동작해요 (외부 전송 없음).', 'info')
        send_label = '수정하기'

    if st.button(send_label, key=f'send_{block_id}', type='primary',
                 width='stretch'):
        if not text:
            st.warning('어떻게 고칠지 먼저 적어 주세요.')
        else:
            _revise_and_rerender(bd, slide, text, use_api=ok)
            st.rerun()

    # 키가 없을 때의 '외부 전송 없음'은 바로 위 안내가 이미 말했다. 같은 말을
    # 버튼 아래에서 한 번 더 하지 않는다.
    if ok:
        if st.button('전송 없이 프리셋으로', key=f'local_{block_id}',
                     width='stretch'):
            if text:
                _revise_and_rerender(bd, slide, text, use_api=False)
                st.rerun()

    if (slide.payload or {}).get('_original'):
        if st.button('원래 문안으로 되돌리기', key=f'undo_{block_id}',
                     width='stretch'):
            if R.restore_original(slide):
                _chat_log(block_id).clear()
            st.rerun()


# ═══════════════════════════ 생성

def _versioned_path(out_dir: Path, date: str, category: str) -> Path:
    """
    기존 파일 덮어쓰기 금지 — 같은 이름이 있으면 버전을 올린다.

    품목은 AE 가 직접 타이핑하는 값이라 'AV/VD' 처럼 경로 구분자가 들어올 수
    있다. 그대로 두면 없는 하위 폴더로 해석돼 **리포트를 다 만든 뒤 저장에서만**
    터진다. 이름 조각을 먼저 저장 가능한 형태로 다듬는다 (claude.md 1.4).
    """
    from utils.errors import safe_filename_part
    date = safe_filename_part(date, fallback='YYMMDD', max_len=12)
    category = safe_filename_part(category, fallback='미지정')
    v = 0
    while True:
        p = out_dir / f'{date}_{category}_결과리포트_v{v}_Cheil.pptx'
        if not p.exists():
            return p
        v += 1


def _build_spec(knowledge: CampaignKnowledge, dataset) -> Optional[Any]:
    from utils.report import ReportSpecBuilder
    try:
        # Stage 1.5 승인본을 재사용한다 (재도출하면 AE 교정이 사라진다)
        return ReportSpecBuilder.build(
            knowledge, dataset, state.get(state.KEY_INSIGHT_SET))
    except Exception as e:
        st.error(f'덱 구성 실패: {e}')
        return None


def render(project_root: Path) -> None:
    knowledge = state.get_knowledge()
    if knowledge is None:
        st.warning('먼저 1단계에서 자료를 올려 주세요.')
        if st.button('1단계로 이동'):
            state.goto_step(1)
            st.rerun()
        return

    dataset = state.get(state.KEY_DATASET)
    if dataset is None:
        st.warning('읽어 둔 데이터가 없어요. 1단계부터 다시 시작해 주세요.')
        return

    from utils.report import ReportSpecBuilder, ReportRenderer
    from utils.report.fonts import missing_fonts
    from dashboard import shell

    # 슬라이드 카드 스타일은 산출물 팔레트를 쓰므로 theme_css 가 아니라
    # 여기서 주입한다 (theme_css 는 utils.report 를 import 하지 않는다).
    st.markdown(f'<style>{SP.slide_css()}</style>', unsafe_allow_html=True)

    date = (knowledge.date_created or '').strip()
    category = (knowledge.category or '').strip()
    missing = missing_fonts()
    if missing:
        T.note('PPT 글꼴이 달라 보일 수 있어요 — ' + ', '.join(missing)
               + ' 미설치', 'info')

    # ── 덱 구성 (미리보기용) — PPTX 렌더는 최종 추출 때만 한다
    spec = state.get(KEY_SPEC)
    if spec is None:
        with st.spinner('슬라이드 초안을 구성하는 중...'):
            spec = _build_spec(knowledge, dataset)
        if spec is None:
            return
        state.put(KEY_SPEC, spec)

    if not spec.slides:
        T.note('만들어진 슬라이드가 없어요. 2단계에서 입력을 확인해 주세요.',
               'err')
        return

    # 제목은 덱을 만든 뒤에 쓴다 — 장수를 알아야 문장이 성립한다.
    shell.page_title(
        '리포트를 확인해 주세요',
        f'슬라이드 {len(spec.slides)}장을 만들었어요. 고칠 장을 골라 주세요.')

    registry = {bd.block_id: bd for bd in ReportSpecBuilder.registry()}

    # ── 썸네일 그리드 (고른 장 바로 아래에 수정 창이 열린다)
    _grid(spec, registry)

    # ── 집행 요약 차트 — 접지 않고 그대로 보여 준다 (claude.md 5)
    from dashboard import charts
    included = state.get('ax_media_included') or charts.media_names(dataset)
    st.markdown('#### 집행 요약')
    charts.panel(dataset, included, metric='노출')

    ins = getattr(spec, 'insights', None)
    if ins is not None and ins.excluded:
        st.markdown(f'#### 인사이트에서 제외한 항목 {len(ins.excluded)}건')
        for r in ins.excluded:
            st.markdown(f'- {r}')

    for w in spec.warnings:
        T.note(w, 'warn')

    # 파일명 규칙을 못 채워도 막지 않는다. 임시값으로 만들되 사실을 알린다.
    if not (date and category):
        T.note('작성 일자 또는 품목이 비어 있어 파일명이 규칙과 조금 달라요.',
               'warn')
    date = date or datetime.now().strftime('%y%m%d')
    category = category or '미지정'

    st.divider()

    # ── 최종 추출 — 화면에서 가장 강한 한 곳.
    # 강조 스타일은 위젯 key(`.st-key-ax_final_export`)로 건다.
    if st.button(f'최종 PPTX 추출  ·  {len(spec.slides)}장',
                 type='primary', width='stretch', key='ax_final_export'):
        out_dir = (project_root / 'Output'
                   / f'{date}_{knowledge.campaign_name}'.strip('_'))
        out_path = _versioned_path(out_dir, date, category)
        with st.spinner('슬라이드를 조립하는 중...'):
            try:
                result = ReportRenderer().render(spec, str(out_path))
            except Exception as e:
                st.error(f'PPTX 생성 실패: {e}')
                return
        state.put('ax_last_pptx', result)
        st.success(f'만들었어요 — 슬라이드 {len(spec.slides)}장')

    last = state.get('ax_last_pptx')
    if last:
        try:
            with open(last, 'rb') as f:
                st.download_button(
                    'PPTX 내려받기', data=f.read(), key='ax_final_dl',
                    file_name=Path(last).name, width='stretch',
                    mime='application/vnd.openxmlformats-officedocument.'
                         'presentationml.presentation')
            st.caption(Path(last).name)
        except OSError:
            st.caption('파일이 이미 정리되었어요. 다시 추출해 주세요.')

    T.spacer(10)
    c1, c2 = st.columns(2)
    with c1:
        if st.button('기본 정보 확인으로 돌아가기', width='stretch'):
            state.goto_step(2)
            st.rerun()
    with c2:
        if st.button('초안 다시 구성', width='stretch'):
            state.put(KEY_SPEC, None)
            state.put('ax_last_pptx', None)
            arm_scroll_top()
            st.rerun()

    # 화면을 다 그린 뒤에 부른다 — 썸네일이 DOM 에 있어야 잡을 수 있다.
    _scroll_to_first_slide()
