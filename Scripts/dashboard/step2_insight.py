# -*- coding: utf-8 -*-
"""
Stage 1.5 — 인사이트 · 레슨런 검증

Stage 3 규칙 엔진이 뽑은 Lesson Learned 초안을 기획자(AE)가 눈으로 확인하고
직접 고친 뒤 [승인]해야 리포트 생성으로 넘어간다.

원칙
  - AI가 먼저 제안하고 AE 는 확인·수정만 한다 (빈 칸을 채우게 하지 않는다).
  - 근거·출처는 항상 옆에 보인다. 근거가 안 보이면 검증이 아니라 그냥 타이핑이다.
  - 접이식으로 본문을 숨기지 않는다 (claude.md 5장).
  - 승인하지 않은 항목은 확정으로 처리하지 않고 Checklist 에 남긴다.
"""

from typing import List, Optional

import streamlit as st

from models.campaign_data import InsightSet
from models.campaign_knowledge import CampaignKnowledge

from dashboard import state, theme_css as T

_PREFIX = 'ax_ins'


def _bid(ins, idx: int) -> str:
    """
    위젯 키로 쓸 블록 식별자.

    구버전 Insight 객체(block_id 없음)가 세션에 남아 있어도 화면이 죽지 않게
    getattr 로 접근한다 — 필드 추가 이전에 만들어진 객체가 섞일 수 있다.
    """
    return getattr(ins, 'block_id', '') or f'idx{idx}'


# ═══════════════════════════ 도출

def _generate(knowledge: CampaignKnowledge, dataset) -> InsightSet:
    """규칙 엔진 실행 — 실패해도 화면이 죽지 않게 빈 세트를 돌려준다"""
    try:
        from utils.insight import InsightEngine
    except Exception as e:
        st.warning(f'인사이트 엔진을 불러오지 못했어요: {e}')
        return InsightSet()
    try:
        engine = InsightEngine()
        result = engine.generate(knowledge, dataset)
        for item in engine.to_checklist_items(result):
            knowledge.add_checklist_item(item)
        return result
    except Exception as e:
        st.warning(f'인사이트를 도출하지 못했어요: {e}')
        return InsightSet()


def ensure(knowledge: CampaignKnowledge, dataset) -> InsightSet:
    """세션에 없으면 한 번 도출해 캐시한다 (매 렌더마다 재계산 방지)"""
    cached = state.get(state.KEY_INSIGHT_SET)
    if cached is None:
        cached = _generate(knowledge, dataset)
        state.put(state.KEY_INSIGHT_SET, cached)
    return cached


def _regenerate(knowledge: CampaignKnowledge, dataset) -> None:
    """다시 도출 — 편집 내용은 사라지므로 승인도 함께 해제한다"""
    state.put(state.KEY_INSIGHT_SET, _generate(knowledge, dataset))
    state.put(state.KEY_INSIGHT_APPROVED, False)


# ═══════════════════════════ 편집 내용 반영

def _apply_edits(insight_set: InsightSet) -> int:
    """
    화면에서 고친 값을 InsightSet 에 반영하고, 제외된 항목을 걷어낸다.

    Returns:
        AE 가 실제로 문구를 고친 건수
    """
    edited = 0
    keep = []
    for idx, ins in enumerate(insight_set.insights, 1):
        bid = _bid(ins, idx)
        if st.session_state.get(f'{_PREFIX}_{bid}_drop'):
            continue
        changed = False
        for field in ('finding', 'context', 'recommendation'):
            new = st.session_state.get(f'{_PREFIX}_{bid}_{field}')
            if new is None:
                continue
            new = str(new).strip()
            if new and new != getattr(ins, field):
                setattr(ins, field, new)
                changed = True
        if changed:
            ins.origin = 'ae'
            edited += 1
        ins.approved = True
        keep.append(ins)

    dropped = len(insight_set.insights) - len(keep)
    if dropped:
        insight_set.excluded.append(f'기획자가 제외한 인사이트 {dropped}건')
    insight_set.insights = keep
    return edited


# ═══════════════════════════ 화면

def _card(ins, idx: int) -> None:
    from utils.insight import axes

    bid = _bid(ins, idx)
    axis_label = axes.label(ins.axis)
    axis_code = axes.code(ins.axis)
    pattern = axes.pattern_label(getattr(ins, 'pattern', ''))

    from utils.insight import composer
    conf = getattr(ins, 'confidence', 'medium')
    conf_label = composer.CONFIDENCE_LABEL.get(conf, '')

    head = f'{axis_code} · {axis_label}'
    if pattern:
        head += f'　|　{pattern}'
    if conf_label:
        head += f'　|　{conf_label}'
    st.markdown(f'###### {idx}. {head}')
    if conf == 'low':
        st.caption('격차가 기준을 겨우 넘은 건이에요.')

    left, right = st.columns([1.35, 1], gap='medium')

    with left:
        st.text_area(
            '발견 — 수치로 확인된 사실', value=ins.finding,
            key=f'{_PREFIX}_{bid}_finding', height=80)
        st.text_area(
            '평가 — 그 수치의 기획적 해석', value=getattr(ins, 'context', '') or '',
            key=f'{_PREFIX}_{bid}_context', height=80)
        st.text_area(
            '제언 — 차기 캠페인 실행 액션', value=ins.recommendation,
            key=f'{_PREFIX}_{bid}_recommendation', height=80)

    with right:
        st.markdown('**근거**')
        if ins.evidence:
            for e in ins.evidence:
                st.markdown(f'- {e}')
        else:
            st.caption('근거 수치 없음')
        if ins.sources:
            st.markdown('**출처**')
            for s in ins.sources[:2]:
                st.caption(s)
        intent = getattr(ins, 'intent', '')
        if intent:
            st.markdown('**원래 의도**')
            st.caption(intent)
        st.checkbox('이 항목은 빼기', key=f'{_PREFIX}_{bid}_drop')

    st.divider()


def render(knowledge: CampaignKnowledge, dataset) -> bool:
    """
    인사이트 검증 화면.

    Returns:
        승인 여부 (False 면 리포트 생성을 막는다)
    """
    st.markdown('### Lesson Learned 초안을 확인해 주세요')
    st.markdown(
        '<p class="ax-lead">'
        '<span class="kbr">실집행 데이터에서 자동으로 뽑은 초안이에요.</span> '
        '<span class="kbr">고치거나 뺀 뒤 승인해 주세요.</span></p>',
        unsafe_allow_html=True)

    if dataset is None:
        T.note('데이터셋이 없어 인사이트를 도출할 수 없어요.', 'warn')
        return False

    insight_set = ensure(knowledge, dataset)
    approved = bool(state.get(state.KEY_INSIGHT_APPROVED))

    if not insight_set.insights:
        T.note('초안을 만들 만한 데이터가 없어 포스트바이 원문을 그대로 써요.',
               'warn')
        for reason in insight_set.excluded[:8]:
            st.caption(f'· {reason}')
        # 도출이 0건이면 막지 않는다 (폴백 경로가 있으므로)
        return True

    from utils.insight import axes
    covered = sorted({i.axis for i in insight_set.insights}, key=axes.sort_key)
    weak = sum(1 for i in insight_set.insights
               if getattr(i, 'confidence', '') == 'low')
    st.caption(
        f'{len(insight_set.insights)}건 · '
        + ' · '.join(f'{axes.code(a)} {axes.label(a)}' for a in covered)
        + (f'　|　근거 약함 {weak}건' if weak else '')
        + ('　|　승인 완료' if approved else '　|　승인 전'))

    T.spacer(6)
    for idx, ins in enumerate(insight_set.insights, 1):
        _card(ins, idx)

    if insight_set.excluded:
        st.markdown('###### 도출에서 빠진 항목')
        st.caption('Checklist 에 그대로 실려요.')
        for reason in insight_set.excluded[:10]:
            st.caption(f'· {reason}')
        T.spacer(6)

    c1, c2 = st.columns([1, 1.6])
    with c1:
        if st.button('초안 다시 뽑기', width='stretch'):
            _regenerate(knowledge, dataset)
            st.rerun()
    with c2:
        label = '승인 완료 — 다시 승인하기' if approved else '이 내용으로 승인하기'
        if st.button(label, type='primary', width='stretch'):
            edited = _apply_edits(insight_set)
            state.put(state.KEY_INSIGHT_SET, insight_set)
            state.put(state.KEY_INSIGHT_APPROVED, True)
            _record(knowledge, insight_set, edited)
            state.put(state.KEY_FLASH,
                      f'인사이트 {len(insight_set.insights)}건을 승인했어요'
                      + (f' (문구 수정 {edited}건)' if edited else ''))
            st.rerun()

    if not approved:
        T.note('승인하시면 리포트 생성으로 넘어갈 수 있어요.', 'warn')
    return approved


def _record(knowledge: CampaignKnowledge, insight_set: InsightSet,
            edited: int) -> None:
    """승인 사실을 Checklist 에 남긴다 (claude.md 3.4 · 3.5)"""
    from models.checklist import ChecklistItem
    untouched = len(insight_set.insights) - edited
    knowledge.add_checklist_item(ChecklistItem(
        type='insight_approved',
        severity='info' if edited else 'warning',
        message=(f'인사이트 {len(insight_set.insights)}건 기획자 승인 — '
                 f'문구 수정 {edited}건 · 원문 유지 {untouched}건'),
        detail=('자동 도출 문구를 그대로 승인한 항목은 수치 인용은 검증되었으나 '
                '표현은 기계 생성임' if untouched else
                '전 항목을 기획자가 검토·수정함'),
        source='Stage 1.5 인사이트 검증',
    ))
