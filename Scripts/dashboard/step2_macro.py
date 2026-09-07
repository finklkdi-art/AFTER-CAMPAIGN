# -*- coding: utf-8 -*-
"""
STEP 2 — 필수 메타데이터 교정 + 피봇 제어 (거시 검증, Rule Book 2.3)

2026.09.05 개편
  · 강제 확인(Hard-stop) 장치를 모두 제거했다. 확인 체크박스도, 입력이
    비었다고 다음 단계를 막는 게이트도 없다. 값이 비면 자동 기본값을
    넣고 그 사실을 Checklist 에 남긴다.
  · 타이핑은 캠페인명 · 품목 · 작성일자 3개로 줄였다. 나머지는 파서
    추정값을 보여주고 필요할 때만 펼쳐서 고친다.
  · 엑셀 피봇처럼 매체를 토글로 켜고 끄면, '적용' 버튼 없이 우측 차트가
    즉시 다시 그려진다 (`st.fragment`).

🔴 부담 경감이 '조용한 통과'가 되지 않도록:
  - 상세 수치 편집 UI 는 제거하지 않고 접이식으로 보존한다
  - AE 가 손대지 않은 항목·제외한 매체는 Checklist 에 남긴다
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st

from models.campaign_knowledge import CampaignKnowledge
from models.checklist import ChecklistItem
from dashboard import state, theme_css as T
from dashboard import charts

# 거시 확정 대상 (Rule Book 2.3) — 확인 여부를 Checklist 기재에 쓴다
MACRO_ITEMS = [
    ('overview', '캠페인 개요'),
    ('media', '매체 종류'),
    ('period', '집행 기간 · 스케줄'),
    ('creative', '소재 리스트'),
    ('strategy', '전략 · 목적'),
]

KEY_TOUCHED = 'ax_macro_touched'  # AE 가 실제로 건드린 항목 집합

# 입력 위젯 키 (프래그먼트 재실행과 무관하게 값을 유지하기 위해 세션에 둔다)
K_NAME, K_CAT, K_DATE, K_ADV = ('macro_name', 'macro_cat',
                                'macro_date', 'macro_adv')


# ═══════════════════════════ 수집 (원본을 바꾸지 않고 읽기만)

def _creative_names(dataset) -> List[str]:
    out: List[str] = []
    seen = set()
    if dataset is None:
        return out
    dr = dataset.daily_report
    for mp in (dr.media_performance if dr else []):
        v = (mp.creative or '').strip()
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    for pl in dataset.plan_lines():
        v = (pl.creative or '').strip()
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _purposes(dataset) -> List[str]:
    out, seen = [], set()
    if dataset is None:
        return out
    dr = dataset.daily_report
    for mp in (dr.media_performance if dr else []):
        v = (mp.purpose or '').strip()
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    for pl in dataset.plan_lines():
        v = (pl.purpose or '').strip()
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _periods(knowledge: CampaignKnowledge, dataset) -> Dict[str, str]:
    prop = (knowledge.proposal.get('metadata') or {}).get('campaign_period') or ''
    post = (knowledge.postbuy.get('metadata') or {}).get('report_period') or ''
    daily = ''
    if dataset is not None and dataset.daily_report:
        dr = dataset.daily_report
        daily = dr.period_raw or ''
        if not daily and dr.daily_rows:
            daily = f'{dr.daily_rows[0].date} ~ {dr.daily_rows[-1].date}'
    return {'제안 기간': prop, '실집행(포스트바이)': post, '데일리리포트': daily}


def _touch(key: str) -> None:
    st.session_state.setdefault(KEY_TOUCHED, set()).add(key)


def _touched() -> set:
    return st.session_state.setdefault(KEY_TOUCHED, set())


# ═══════════════════════════ 집행 요약 차트 (읽기 전용)

def _summary_charts(dataset) -> None:
    """
    매체별 요약 차트.

    2026.09.07 — 매체 on/off 토글과 지표 선택으로 이뤄진 '피봇 제어'를
    제거했다. 화면을 단순하게 유지하려는 결정이며, 이제 **전체 매체가 항상
    보고서에 들어간다.** 그 결과 '피봇에서 제외한 매체' 자체가 생기지
    않으므로 Checklist 의 제외 기재(claude.md 3.4)도 대상이 없어진다.
    """
    names = charts.media_names(dataset)
    if not names:
        st.caption('매체를 찾지 못했어요.')
        return
    st.markdown('##### 집행 요약')
    st.caption(f'매체 {len(names)}개 전부가 보고서에 들어가요. '
               '아래 차트에는 값이 있는 매체만 그려져요.')
    charts.panel(dataset, names, metric='노출')


# ═══════════════════════════ 필수 메타 (타이핑 3개)

def _render_meta(knowledge: CampaignKnowledge, dataset) -> None:
    st.markdown('### 이 캠페인의 기본 정보만 확인해 주세요')
    st.caption('보고서 표지와 파일명에 그대로 쓰여요. '
               '나머지 값은 아래에서 자동으로 정리해 드려요.')

    if K_NAME not in st.session_state:
        st.session_state[K_NAME] = knowledge.campaign_name or ''
    if K_CAT not in st.session_state:
        st.session_state[K_CAT] = knowledge.category or ''
    if K_DATE not in st.session_state:
        st.session_state[K_DATE] = (knowledge.date_created
                                    or datetime.now().strftime('%y%m%d'))
    if K_ADV not in st.session_state:
        st.session_state[K_ADV] = knowledge.advertiser or ''

    c1, c2, c3 = st.columns([2.2, 1, 1])
    with c1:
        st.text_input('캠페인명', key=K_NAME,
                      placeholder='예) 2025 무빙스타일 캠페인',
                      on_change=_touch, args=('overview',))
    with c2:
        st.text_input('품목', key=K_CAT, placeholder='예) 냉장고',
                      help='출력 파일명의 [품목] 자리',
                      on_change=_touch, args=('overview',))
    with c3:
        st.text_input('작성 일자 (YYMMDD)', key=K_DATE,
                      on_change=_touch, args=('overview',))

    # 파서가 읽은 표기는 '참고'로만 (임의 확정 금지 — Rule Book 2.1)
    hints = []
    if dataset is not None:
        if dataset.media_mix and dataset.media_mix.campaign:
            hints.append(f'미디어믹스: {dataset.media_mix.campaign}')
        if dataset.media_mix and dataset.media_mix.advertiser:
            hints.append(f'광고주(믹스): {dataset.media_mix.advertiser}')
        if dataset.daily_report and dataset.daily_report.campaign:
            hints.append(f'데일리리포트: {dataset.daily_report.campaign}')
        if dataset.postbuy and dataset.postbuy.campaign:
            hints.append(f'포스트바이: {dataset.postbuy.campaign}')

    st.markdown('###### 광고주 · 기간 · 소재 · 전략')
    st.caption('문서에서 자동으로 정리한 값이에요. 그대로 두셔도 돼요.')
    if True:
        st.text_input('광고주', key=K_ADV, placeholder='예) 삼성전자',
                      on_change=_touch, args=('overview',))
        if hints:
            st.caption('문서에서 읽은 표기(참고) · ' + '  |  '.join(hints))
        # 표지에 찍힐 이름이라 문서와 다르면 한 번은 짚어 준다. AE 가 일부러
        # 보고용 명칭을 따로 쓰는 경우도 많으므로 막지 않고 알리기만 한다.
        typed = (st.session_state.get(K_NAME) or '').strip()
        if typed and hints and not any(typed in h for h in hints):
            T.note(f'입력하신 캠페인명 "{typed}" 이 문서 표기와 달라요. '
                   '의도한 이름이면 그대로 두셔도 돼요 — 표지와 파일명에 '
                   '이 이름이 쓰여요.', 'warn')

        st.markdown('##### 집행 기간')
        periods = _periods(knowledge, dataset)
        T.table(['원천', '기간 표기'], [[k, v or '—'] for k, v in periods.items()])
        vals = [v for v in periods.values() if v]
        # 비어 있는 원천을 그냥 '—' 로 두면 AE 가 '없구나' 하고 넘어간다.
        # 제안 vs 실집행 대조는 이 솔루션의 핵심 산출물 3가지 중 하나라
        # (claude.md 정체성), 어디서 채우는지까지 알려 줘야 한다.
        missing = [k for k, v in periods.items() if not v]
        if missing:
            T.note(f'{" · ".join(missing)}을 못 읽었어요 — '
                   '아래 [수치 · KPI · 결손 항목]의 결손 탭에서 직접 넣으시면 '
                   '제안 대비 실집행 대조가 완성돼요.', 'warn')
        if len(set(vals)) > 1:
            T.note('원천별 기간 표기가 서로 달라요 — 양쪽 모두 보고서에 함께 싣고 '
                   'Checklist 에도 남겨요.', 'warn')
        elif not missing:
            _touch('period')

        st.markdown('##### 소재 리스트')
        creatives = _creative_names(dataset)
        if creatives:
            st.caption(f'{len(creatives)}종 확인 — 전부 보고서에 반영돼요')
            T.table(['#', '소재 표기'],
                    [[i, n] for i, n in enumerate(creatives[:20], 1)])
            if len(creatives) > 20:
                st.caption(f'외 {len(creatives) - 20}종')
            _touch('creative')
        else:
            st.caption('소재 표기를 찾지 못했어요. 소재 축 슬라이드는 만들지 않고 '
                       'Checklist 에 남겨요.')

        st.markdown('##### 전략 · 목적')
        purposes = _purposes(dataset)
        if purposes:
            T.table(['목적 표기'], [[p] for p in purposes])
            _touch('strategy')
        else:
            st.caption('목적 컬럼이 없어서 목적 축 슬라이드는 만들지 않아요.')


# ═══════════════════════════ 반영

def _record_soft_notes(knowledge: CampaignKnowledge, dataset,
                       meta: Dict[str, str], dropped: List[str]) -> int:
    """
    막지 않은 대신 남긴다.

    비어서 자동 기본값이 들어간 항목, AE 가 보지 않은 거시 항목, 그리고
    피봇에서 제외한 매체를 전부 Checklist 에 기재한다. 강제 확인을 없앤
    만큼 이 기록이 유일한 안전장치다 (Rule Book 2.3).
    """
    count = 0

    def add(type_: str, severity: str, message: str, detail: str) -> None:
        nonlocal count
        knowledge.add_checklist_item(ChecklistItem(
            type=type_, severity=severity, message=message, detail=detail,
            source='step2_macro:_record_soft_notes'))
        count += 1

    if not meta['campaign_name']:
        add('macro_autofilled:campaign_name', 'warning',
            '[미입력] 캠페인명 — 기획자가 입력하지 않아 임시 표기로 진행됨',
            '보고서 표지와 파일명에 임시값이 쓰였어요. 배포 전에 고쳐 주세요.')
    if not meta['category']:
        add('macro_autofilled:category', 'warning',
            '[미입력] 품목 — 파일명 규칙의 [품목] 자리에 임시값 사용',
            '출력 파일명이 규칙(YYMMDD_품목_자료명_v0_Cheil)에 맞지 않아요.')

    touched = _touched()
    for key, label in MACRO_ITEMS:
        if key in touched:
            continue
        add(f'macro_unconfirmed:{key}', 'warning',
            f'[미확인] {label} — 기획자가 화면에서 확인하지 않고 진행됨',
            '확인 화면에서 이 항목을 열어 보신 적이 없어요.')

    if dropped:
        add('macro_media_dropped', 'warning',
            f'[제외] 피봇에서 제외한 매체 {len(dropped)}건 — '
            + ', '.join(dropped[:8]) + (' 외' if len(dropped) > 8 else ''),
            '기획자가 보고서 범위에서 제외했어요. 매체 드랍과는 구분해 주세요.')

    if dataset is not None:
        undecided = dataset.pending_gaps()
        if undecided:
            add('macro_gaps_pending', 'warning',
                f'[미결정] 결손 항목 {len(undecided)}건 — '
                + ', '.join(g.label for g in undecided[:8]),
                '상세 확인에서 처리하지 않아 해당 슬라이드에 사유가 실려요.')
    return count


def _apply(knowledge: CampaignKnowledge, meta: Dict[str, str]) -> None:
    """빈 값은 막지 않고 임시값으로 채운다 (기재는 _record_soft_notes 가 담당)"""
    knowledge.campaign_name = meta['campaign_name'] or '(캠페인명 미입력)'
    knowledge.category = meta['category'] or '미지정'
    knowledge.date_created = (meta['date_created']
                              or datetime.now().strftime('%y%m%d'))
    knowledge.advertiser = meta['advertiser']
    knowledge.pipeline_log['stage1_5_completed'] = True


def _collect_meta() -> Dict[str, str]:
    return {
        'campaign_name': str(st.session_state.get(K_NAME, '')).strip(),
        'category': str(st.session_state.get(K_CAT, '')).strip(),
        'date_created': str(st.session_state.get(K_DATE, '')).strip(),
        'advertiser': str(st.session_state.get(K_ADV, '')).strip(),
    }


# ═══════════════════════════ 진입점

def render(project_root: Path) -> None:
    knowledge = state.get_knowledge()
    if knowledge is None:
        st.warning('먼저 1단계에서 자료를 올려 주세요.')
        if st.button('1단계로 이동'):
            state.goto_step(1)
            st.rerun()
        return

    dataset = state.get(state.KEY_DATASET)

    flash = state.get(state.KEY_FLASH)
    if flash:
        st.success(flash)
        state.put(state.KEY_FLASH, None)   # 한 번만 보여준다

    warns = state.get('ax_upload_warnings') or []
    if warns:
        st.markdown(f'###### 업로드 경고 {len(warns)}건')
        for w in warns:
            T.note(w, 'warn')

    _render_meta(knowledge, dataset)

    T.spacer(10)
    st.divider()
    _summary_charts(dataset)

    st.divider()

    # ── Checklist 미리보기 (막지 않고 보여주기만)
    items = knowledge.get_checklist_items()
    if items:
        # 심각도 순으로 세운다. 13건이 같은 무게로 나열되면 error 2건이
        # info 사이에 묻혀, 정작 손봐야 할 것을 지나치게 된다.
        rank = {'error': 0, 'warning': 1, 'info': 2}
        ordered = sorted(items, key=lambda x: rank.get(x.severity, 3))
        n_err = sum(1 for x in items if x.severity == 'error')
        n_warn = sum(1 for x in items if x.severity == 'warning')

        st.markdown(f'#### 확인 필요 사항 {len(items)}건')
        head = []
        if n_err:
            head.append(f'꼭 확인 {n_err}건')
        if n_warn:
            head.append(f'권고 {n_warn}건')
        head.append(f'참고 {len(items) - n_err - n_warn}건')
        st.caption(' · '.join(head) + ' — 보고서 1페이지 Checklist 에 그대로 실려요.')

        # 영문 severity 는 실무자에게 바로 읽히지 않는다.
        korean = {'error': '꼭 확인', 'warning': '권고', 'info': '참고'}
        for it in ordered[:40]:
            lvl = {'error': 'err', 'warning': 'warn'}.get(it.severity, 'ok')
            tag = korean.get(it.severity, it.severity)
            T.note(f'[{tag}] {it.message}', lvl)
            # 왜 그런지가 있어야 손을 댈 수 있다. message 만으로는 부족하다.
            detail = (getattr(it, 'detail', '') or '').strip()
            if detail and it.severity in ('error', 'warning'):
                st.caption(f'　{detail[:220]}')
        if len(items) > 40:
            st.caption(f'… 외 {len(items) - 40}건')

    # ── 상세 검증 — 제거하지 않고 보존 (Rule Book 2.3 안전장치 1)
    st.markdown('#### 수치 · KPI · 결손 항목')
    st.caption('위 확인만으로 충분하시면 그냥 지나치셔도 돼요. '
               '여기서 고치신 값은 바로 반영돼요.')
    if True:
        try:
            from dashboard import step2_dataset
            if dataset is not None:
                step2_dataset.render(dataset)
                _touch('detail')
        except Exception as e:
            st.warning(f'상세 화면을 여는 중 문제가 생겼어요: {e}')

    st.divider()

    # ── Part 1 캠페인 개요(기획 의도) 검증
    try:
        from dashboard import step2_overview
        step2_overview.render(knowledge, project_root)
    except Exception as e:
        st.warning(f'캠페인 개요 화면을 여는 중 문제가 생겼어요: {e}')

    st.divider()

    # ── 인사이트 · 레슨런 검증 (승인해야 리포트 생성으로 넘어간다)
    insight_ok = True
    try:
        from dashboard import step2_insight
        insight_ok = step2_insight.render(knowledge, dataset)
    except Exception as e:
        st.warning(f'인사이트 검증 화면을 여는 중 문제가 생겼어요: {e}')

    T.spacer(10)

    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        if st.button('자료 다시 올리기', width='stretch'):
            state.goto_step(1)
            st.rerun()
    with c2:
        # Lesson Learned 초안 승인 전에는 생성으로 넘기지 않는다
        if st.button('리포트 만들기', type='primary', width='stretch',
                     disabled=not insight_ok):
            meta = _collect_meta()
            # 피봇이 사라져 제외 매체가 없다. 전체를 그대로 넘긴다.
            names = charts.media_names(dataset)

            _apply(knowledge, meta)
            n = _record_soft_notes(knowledge, dataset, meta, [])
            state.put('ax_media_included', names)

            if dataset is not None:
                try:
                    from dashboard.step2_verify import _record_gap_decisions
                    _record_gap_decisions(knowledge, dataset)
                except Exception:
                    pass
                state.put(state.KEY_DATASET, dataset)

            from utils.checklist_manager import ChecklistManager
            ChecklistManager.deduplicate_checklist(knowledge)
            state.set_knowledge(knowledge)
            state.put(state.KEY_SPEC, None)   # 개요가 바뀌었으므로 초안 폐기
            state.save_backup(knowledge, project_root)
            if n:
                state.put(state.KEY_FLASH,
                          f'확인이 필요한 {n}건을 Checklist 에 남겼어요.')
            state.goto_step(3)
            st.rerun()
    with c3:
        names = charts.media_names(dataset)
        if names:
            T.seal((f'매체 {len(names)}개 반영',))
