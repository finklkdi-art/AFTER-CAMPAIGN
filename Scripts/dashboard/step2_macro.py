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
from dashboard import step3_preview

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


# 캠페인명 비교에서 걸러낼 흔한 낱말. 이런 것만 겹치는 건 '같은 캠페인'의
# 근거가 못 된다 — 거의 모든 캠페인명에 들어 있기 때문이다.
_NAME_STOPWORDS = frozenset({
    '캠페인', '런칭', '삼성', '삼성전자', '비스포크', 'bespoke', 'ai',
    '2025', '2026', '25년', '26년', '통합', '디지털', 'imc',
})


def _name_tokens(text: str) -> set:
    """비교용 낱말 집합 — 괄호·기호를 떼고 흔한 낱말을 제외한다."""
    import re
    raw = re.split(r'[\s()\[\]{}·,/_\-]+', (text or '').lower())
    return {t for t in raw if len(t) >= 2 and t not in _NAME_STOPWORDS}


def _name_overlaps(typed: str, hints: List[str]) -> bool:
    """
    입력된 캠페인명이 문서 표기와 '같은 캠페인'으로 보이는가.

    글자 단위 포함(`typed in hint`) 검사는 너무 빡빡했다. 폴더명
    '(에어컨) 2025 AI 무풍콤보 런칭 캠페인' 과 문서 표기
    '비스포크 AI 무풍콤보' 는 같은 캠페인인데도 불일치로 잡혔다.
    특징적인 낱말이 하나라도 겹치면 같은 캠페인으로 본다.
    """
    t = _name_tokens(typed)
    if not t:
        return True          # 비교할 낱말이 없으면 경고하지 않는다
    return any(t & _name_tokens(h) for h in hints)


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
    st.caption(f'매체 {len(names)}개 전부가 보고서에 들어가요.')
    charts.panel(dataset, names, metric='노출')


# ═══════════════════════════ 필수 메타 (타이핑 3개)

def _render_meta(knowledge: CampaignKnowledge, dataset) -> None:
    st.markdown('### 이 캠페인의 기본 정보만 확인해 주세요')
    st.caption('보고서 표지와 파일명에 그대로 쓰여요.')

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
    st.caption('문서에서 자동으로 정리한 값이에요.')
    if True:
        st.text_input('광고주', key=K_ADV, placeholder='예) 삼성전자',
                      on_change=_touch, args=('overview',))
        if hints:
            st.caption('문서에서 읽은 표기(참고) · ' + '  |  '.join(hints))
        # 표지에 찍힐 이름이라 문서와 크게 다르면 한 번은 짚어 준다.
        #
        # 예전엔 "입력하신 캠페인명 …" 이라고 했는데, 그 값은 AE 가 넣은 게
        # 아니라 **앱이 폴더명에서 자동으로 채운 값**이었다. 손도 대지 않은
        # 사용자에게 책임을 돌리는 문장이었던 셈이다. 게다가 폴더명과 문서
        # 표기가 글자까지 똑같은 경우는 드물어서 정상 캠페인마다 경고가 떴다.
        # 이제 낱말이 하나도 안 겹칠 때만, 사람을 탓하지 않는 문장으로 알린다.
        typed = (st.session_state.get(K_NAME) or '').strip()
        if typed and hints and not _name_overlaps(typed, hints):
            T.note('표지에 쓸 캠페인명이 문서 표기와 달라요 — '
                   '의도한 이름이면 그대로 두셔도 돼요.', 'warn')

        st.markdown('##### 집행 기간')
        periods = _periods(knowledge, dataset)
        T.table(['원천', '기간 표기'], [[k, v or '—'] for k, v in periods.items()])
        vals = [v for v in periods.values() if v]
        # 비어 있는 원천을 그냥 '—' 로 두면 AE 가 '없구나' 하고 넘어간다.
        # 제안 vs 실집행 대조는 이 솔루션의 핵심 산출물 3가지 중 하나라
        # (claude.md 정체성), 어디서 채우는지까지 알려 줘야 한다.
        missing = [k for k, v in periods.items() if not v]
        if missing:
            # 조사는 앞 낱말 받침에 따라 달라진다 — 박아 두지 않는다
            T.note(f'{T.josa(" · ".join(missing), "을/를")} 못 읽었어요 — '
                   '아래 [수치 · KPI · 결손 항목]에서 넣으실 수 있어요.', 'warn')
        if len(set(vals)) > 1:
            T.note('원천별 기간 표기가 서로 달라요 — 양쪽 모두 보고서에 실어요.',
                   'warn')
        elif not missing:
            _touch('period')

        st.markdown('##### 소재 리스트')
        creatives = _creative_names(dataset)
        if creatives:
            st.caption(f'{len(creatives)}종')
            T.table(['#', '소재 표기'],
                    [[i, n] for i, n in enumerate(creatives[:20], 1)])
            if len(creatives) > 20:
                st.caption(f'외 {len(creatives) - 20}종')
            _touch('creative')
        else:
            # 슬라이드를 못 만든 사실은 Checklist 로 전달된다. 화면에서는
            # '못 찾았다'까지만 말하고 그 뒷일은 설명하지 않는다.
            st.caption('소재 표기를 찾지 못했어요.')

        st.markdown('##### 전략 · 목적')
        purposes = _purposes(dataset)
        if purposes:
            T.table(['목적 표기'], [[p] for p in purposes])
            _touch('strategy')
        else:
            st.caption('목적 표기를 찾지 못했어요.')


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


# ═══════════════════════════ 분석 결과 배너

def _render_flash(flash) -> None:
    """
    1단계 분석 결과를 한 덩어리로 보여 준다.

    예전에는 결과와 무관하게 `st.success`(초록)를 띄웠다. 한 글자도 못 읽은
    경우까지 초록이면 색이 정보를 잃는다. 이제 등급(ok/warn/err)에 따라
    색과 문장이 같이 바뀌고, 실패했을 때는 '무엇을 하면 되는지'까지 붙인다.
    """
    if not flash:
        return
    # 하위 호환 — 예전 형식(문자열)도 그대로 받는다
    if isinstance(flash, str):
        T.note(flash, 'ok')
        return

    level = flash.get('level', 'ok')
    head = flash.get('headline', '')
    detail = (flash.get('detail') or '').strip()
    hint = (flash.get('hint') or '').strip()

    body = head
    if detail:
        body += f' · {detail}'
    T.note(body, {'ok': 'ok', 'warn': 'warn'}.get(level, 'err'))
    if hint:
        # 다음 행동은 경고 상자 안에 밀어 넣지 않고 바로 밑에 둔다 —
        # 상자가 길어질수록 정작 '무엇을 하면 되는지' 가 안 읽힌다.
        st.caption(hint)


# ═══════════════════════════ Checklist (표시용 묶음)

# 화면에 한 번에 펼칠 최대 줄 수. 이 아래로는 '외 N건'으로 접는 게 아니라
# 개수만 알리고 나머지는 보고서 Checklist 슬라이드가 받는다 (claude.md 3.4).
_CHECKLIST_SHOWN = 12

_SEV_KO = {'error': '꼭 확인', 'warning': '권고', 'info': '참고'}
_SEV_LVL = {'error': 'err', 'warning': 'warn'}


def _group_items(items) -> List[dict]:
    """
    같은 원인의 항목을 한 줄로 묶는다.

    실제로 겪은 화면: 파일 6개가 전부 사내 문서보안에 걸리자 200자짜리 같은
    안내가 여섯 번 반복돼 1,200자가 깔렸다. 원인은 하나인데 여섯 줄을 읽혀선
    안 된다. 묶는 건 **표시**만이고 원본 항목은 그대로 남아 보고서 Checklist
    슬라이드에 전부 실린다 (claude.md 3.1 — 화면 축약과 저장 원본의 분리).

    묶음 키는 (심각도, 유형, 상세문구)다. 상세가 같으면 같은 사건으로 본다.
    """
    groups: Dict[tuple, dict] = {}
    order: List[tuple] = []
    for it in items:
        detail = (getattr(it, 'detail', '') or '').strip()
        key = (it.severity, getattr(it, 'type', ''), detail)
        if key not in groups:
            groups[key] = {'severity': it.severity, 'detail': detail,
                           'messages': [], 'subjects': []}
            order.append(key)
        g = groups[key]
        g['messages'].append(it.message)
        # '파일 파싱 실패: a.pdf' → 'a.pdf' 만 뽑아 대상 목록을 만든다
        subject = it.message.split(':', 1)[1].strip() if ':' in it.message else ''
        if subject:
            g['subjects'].append(subject)
    return [groups[k] for k in order]


def _render_checklist(items) -> None:
    if not items:
        return

    rank = {'error': 0, 'warning': 1, 'info': 2}
    groups = sorted(_group_items(items),
                    key=lambda g: rank.get(g['severity'], 3))

    n_err = sum(1 for x in items if x.severity == 'error')
    n_warn = sum(1 for x in items if x.severity == 'warning')
    n_info = len(items) - n_err - n_warn

    st.markdown(f'#### 확인 필요 사항 {len(items)}건')
    head = []
    if n_err:
        head.append(f'꼭 확인 {n_err}건')
    if n_warn:
        head.append(f'권고 {n_warn}건')
    if n_info:
        head.append(f'참고 {n_info}건')
    st.caption(' · '.join(head) + ' — 보고서 1페이지 Checklist 에 실려요.')

    for g in groups[:_CHECKLIST_SHOWN]:
        tag = _SEV_KO.get(g['severity'], g['severity'])
        # 참고(info)는 라임이 아니라 조용한 면으로 — 라임은 '잘 됐다'는
        # 뜻이라 단순 참고 항목에 쓰면 신호가 뒤집힌다.
        lvl = _SEV_LVL.get(g['severity'], 'info')
        n = len(g['messages'])

        if n == 1:
            T.note(f'[{tag}] {g["messages"][0]}', lvl)
        else:
            # 대표 문구에서 뒤쪽 대상만 떼어내고 앞부분을 제목으로 쓴다
            headline = g['messages'][0].split(':', 1)[0].strip()
            T.note(f'[{tag}] {headline} — {n}건', lvl)
            if g['subjects']:
                st.caption('　' + T.safe_md(' · '.join(g['subjects'])))

        detail = g['detail']
        if detail and g['severity'] in ('error', 'warning'):
            st.caption('　' + T.safe_md(T.strip_paths(detail))[:260])

    hidden = len(groups) - _CHECKLIST_SHOWN
    if hidden > 0:
        st.caption(f'외 {hidden}건은 보고서 Checklist 슬라이드에 실려요.')


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

    _render_flash(state.get(state.KEY_FLASH))
    state.put(state.KEY_FLASH, None)       # 한 번만 보여준다

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
    _render_checklist(knowledge.get_checklist_items())

    # ── 상세 검증 — 제거하지 않고 보존 (Rule Book 2.3 안전장치 1)
    st.markdown('#### 수치 · KPI · 결손 항목')
    st.caption('여기서 고치신 값은 바로 반영돼요.')
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
            step3_preview.arm_scroll_top()
            state.goto_step(3)
            st.rerun()
    with c3:
        names = charts.media_names(dataset)
        if names:
            T.seal((f'매체 {len(names)}개 반영',))
