# -*- coding: utf-8 -*-
"""
STEP 2 확장 탭 — 데이터 원천 / 로드맵 / 결손 관리

결손 항목마다 기획자가 [직접 입력] / [건너뛰기] 를 고르게 한다.
AI 는 빈칸을 추정해 채우지 않는다 (Rule Book 2.2).
"""

from typing import List

import pandas as pd
import streamlit as st

from models.campaign_data import (
    CampaignDataset, DataGap, GAP_FILLED, GAP_PENDING, GAP_SKIPPED,
)
from dashboard import state, theme_css as T


# 결손 입력 표의 기본 컬럼
_GAP_TABLE_COLUMNS = {
    'kpi_target': ['매체', '상품', 'KPI', '목표치'],
    'reach_freq': ['매체', '상품', 'Reach', 'Freq', 'CPR'],
    'analytics': ['매체', 'Visit', 'Entries', 'Cart Add', 'Order'],
    'roadmap_period': ['매체', '상품', '시작일', '종료일'],
    'plan_lines': ['매체', '상품', '기간', '예산'],
    'daily_actuals': ['일자', '노출', '조회', '클릭', '집행금액'],
}


# ===================== 원천 요약 =====================

def render_sources(dataset: CampaignDataset) -> None:
    """어떤 문서에서 무엇을 얼마나 뽑았는지"""
    st.subheader("데이터 원천")

    s = dataset.summary()
    # 'Full / Lite' 는 내부 모드 이름이다. AE 에게는 '무엇이 있고 없는지'만
    # 말하면 된다 — 제품 내부 용어를 화면에 노출하지 않는다.
    if dataset.mode == 'full':
        T.note('포스트바이가 있어서 확정 KPI까지 확보했어요.', 'ok')
    else:
        T.note('포스트바이가 없어서 미디어믹스와 데일리리포트로 구성했어요 — '
               '확정 목표치는 [결손 항목]에서 직접 넣으실 수 있어요.', 'warn')

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("계획 라인", f"{s['plan_lines']:,}")
    c2.metric("일자별 실적", f"{s['daily_rows']:,}")
    c3.metric("운영 이벤트", f"{s['events']:,}")
    c4.metric("매체 실적", f"{s['media_performance']:,}")

    # 파서별 상세
    rows = []
    if dataset.media_mix:
        m = dataset.media_mix
        t = m.plan_totals()
        rows.append({
            '원천': '미디어믹스 (계획)', '파일': m.source_file,
            '추출': f"{len(m.lines)}개 라인",
            '요약': f"예산 {t['budget']:,.0f}원 · 예상노출 {t['impressions']:,.0f}",
        })
    for extra in dataset.extra_mixes:
        rows.append({
            '원천': '미디어믹스 (보조)', '파일': extra.source_file,
            '추출': f"{len(extra.lines)}개 라인", '요약': '-',
        })
    if dataset.daily_report:
        d = dataset.daily_report
        rows.append({
            '원천': '데일리리포트 (실적)', '파일': d.source_file,
            '추출': f"{len(d.daily_rows)}일 · 이벤트 {len(d.events)}건",
            '요약': (f"집행 {d.total.spend or 0:,.0f}원 · "
                     f"노출 {d.total.impressions or 0:,.0f} · "
                     f"클릭 {d.total.clicks or 0:,.0f}"),
        })
    if dataset.postbuy:
        p = dataset.postbuy
        rows.append({
            '원천': '포스트바이', '파일': p.source_file,
            '추출': f"슬라이드 {len(p.sections)}장 · KPI {len(p.kpi_targets)}건",
            '요약': p.summary_headline[:70] or '-',
        })

    if rows:
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    else:
        T.note("읽어 온 표가 없어요 — 1단계에서 파일이 열렸는지 확인해 주세요.", "warn")

    if dataset.warnings:
        st.markdown(f"###### 읽는 중 생긴 문제 {len(dataset.warnings)}건")
        for w in dataset.warnings:
            # 예외 원문에는 절대 경로와 `_`·`$` 가 섞여 들어온다. 경로는 파일명만
            # 남기고, 마크다운 특수문자는 무해화한 뒤에 그린다.
            st.caption('· ' + T.safe_md(T.strip_paths(w)))


# ===================== 로드맵 =====================

def render_roadmap(dataset: CampaignDataset) -> None:
    """집행 로드맵 — 계획 라인을 표로 확인하고 기간을 보완"""
    st.subheader("집행 로드맵")
    st.caption("미디어믹스에서 뽑은 계획이에요. 기간이 빈 행은 아래에서 채우거나 건너뛰셔도 돼요.")

    lines = dataset.plan_lines()
    if not lines:
        T.note("계획 라인이 없어요 — [결손 항목]에서 직접 넣으실 수 있어요.", "warn")
        return

    df = pd.DataFrame([{
        '매체': l.media,
        '상품': l.product,
        '구분': l.category,
        '기간(원본)': l.period_raw,
        '시작': l.period_start or '',
        '종료': l.period_end or '',
        '소재': l.creative,
        '예산': l.budget,
        '예상노출': l.expected_impressions,
        '출처': l.source.label(),
    } for l in lines])

    filled = int(df['시작'].astype(bool).sum())
    st.caption(f"기간 확보 {filled}/{len(df)}건")
    st.dataframe(df, width="stretch", hide_index=True)


# ===================== KPI =====================

def render_kpi(dataset: CampaignDataset) -> None:
    """KPI 목표 대비 실적"""
    st.subheader("KPI 목표")

    if dataset.mode == 'full' and dataset.postbuy:
        T.note("포스트바이의 확정 목표치를 쓰고 있어요.", "ok")
        rows = [{
            '구분': k.scope, '매체': k.media, '상품': k.product, 'KPI': k.kpi_name,
            '목표': k.target, '실적': k.actual,
            '달성률': f"{k.achievement_rate:.0%}" if k.achievement_rate else '-',
            '출처': k.source.label(),
        } for k in dataset.postbuy.kpi_targets]
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        return

    # 네 문장짜리 경고를 한 문장으로. 왜 위험한지는 바로 아래 표의 컬럼명
    # ('제안 기준(참고)')과 캡션이 이미 말하고 있다.
    T.note("확정 목표치가 없어서 아래는 제안 시점의 예상 성과예요 — "
           "[결손 항목]에서 확정 목표를 넣으실 수 있어요.", "warn")

    if dataset.media_mix:
        t = dataset.media_mix.plan_totals()
        d = dataset.daily_report.total if dataset.daily_report else None
        st.dataframe(pd.DataFrame([
            {'지표': '노출', '제안 기준(참고)': t['impressions'],
             '실적': d.impressions if d else None},
            {'지표': '조회', '제안 기준(참고)': t['views'],
             '실적': d.views if d else None},
            {'지표': '클릭', '제안 기준(참고)': t['clicks'],
             '실적': d.clicks if d else None},
            {'지표': '예산', '제안 기준(참고)': t['budget'],
             '실적': d.spend if d else None},
        ]), width="stretch", hide_index=True)
        st.caption("'제안 기준'은 확정 목표가 아니라서 달성률을 자동으로 계산하지 않아요.")


# ===================== 결손 관리 =====================

def _render_gap_input(gap: DataGap, key_prefix: str):
    """결손 항목별 입력 위젯"""
    if gap.input_kind == 'table':
        cols = _GAP_TABLE_COLUMNS.get(gap.key, ['항목', '값'])
        seed = gap.filled_value if isinstance(gap.filled_value, list) and gap.filled_value \
            else [{c: '' for c in cols} for _ in range(3)]
        edited = st.data_editor(
            pd.DataFrame(seed),
            num_rows="dynamic", width="stretch", hide_index=True,
            key=f'{key_prefix}_tbl',
        )
        records = edited.fillna('').to_dict('records')
        return [r for r in records if any(str(v).strip() for v in r.values())]

    if gap.input_kind == 'textarea':
        return st.text_area(
            "내용", value=gap.filled_value or '', height=130,
            key=f'{key_prefix}_txt',
            placeholder="확보하신 내용을 붙여넣거나 직접 적어 주세요.",
        ).strip()

    return st.text_input(
        "값", value=gap.filled_value or '', key=f'{key_prefix}_in').strip()


def render_gaps(dataset: CampaignDataset) -> None:
    """
    결손 항목 관리 — 항목마다 [직접 입력] / [건너뛰기] 선택

    건너뛴 항목은 해당 슬라이드를 비우고 Checklist 에 사유를 남긴다.
    """
    st.subheader("결손 항목")
    st.caption(
        "자동으로 채우지 못한 항목이에요. AI가 임의로 추정하지 않으니 "
        "직접 입력하실지 건너뛰실지 골라 주세요.")

    if not dataset.gaps:
        T.note("자동으로 모두 채워졌어요. 따로 입력하실 게 없어요.", "ok")
        return

    pending = dataset.pending_gaps()
    blocking = dataset.blocking_gaps()
    c1, c2, c3 = st.columns(3)
    c1.metric("전체", len(dataset.gaps))
    c2.metric("미결정", len(pending))
    c3.metric("진행 차단", len(blocking))

    if blocking:
        T.note("다음 항목은 보고서 품질에 직접 영향을 줘요 — "
               + ", ".join(g.label for g in blocking), "warn")

    st.divider()

    for i, gap in enumerate(dataset.gaps):
        badge = '필수' if gap.severity == 'blocking' else '권고'
        icon = {'pending': '○', 'filled': '●', 'skipped': '—'}[gap.resolution]
        header = f"{icon} [{badge}] {gap.label} · {gap.status_label()}"

        # 접이식 대신 테두리 컨테이너로 항상 펼쳐 둔다 (claude.md 5).
        # 결손 항목은 '열어야 보이는' 순간 그냥 지나쳐지기 쉬운 정보다.
        with st.container(border=True):
            st.markdown(f"**{header}**")
            st.caption(gap.reason)
            if gap.affected_slides:
                st.caption(f"영향받는 슬라이드: {' · '.join(gap.affected_slides)}")

            prefix = f'gap_{gap.key}'
            options = ['미결정', '직접 입력', '건너뛰기']
            current = {GAP_PENDING: 0, GAP_FILLED: 1, GAP_SKIPPED: 2}[gap.resolution]
            choice = st.radio(
                "처리 방법", options, index=current,
                key=f'{prefix}_choice', horizontal=True,
                label_visibility='collapsed',
            )

            if choice == '직접 입력':
                value = _render_gap_input(gap, prefix)
                gap.filled_value = value
                gap.resolution = GAP_FILLED if value else GAP_PENDING
                if not value:
                    st.caption("내용을 적으시면 '직접 입력함'으로 기록돼요.")
            elif choice == '건너뛰기':
                gap.resolution = GAP_SKIPPED
                gap.filled_value = None
                st.info(
                    f"이 항목을 건너뛰어요. 해당 슬라이드는 비워지고 "
                    f"Checklist 에 사유를 남겨요.")
            else:
                gap.resolution = GAP_PENDING
                gap.filled_value = None

    state.put(state.KEY_DATASET, dataset)


# ===================== 진입점 =====================

def render(dataset: CampaignDataset) -> None:
    """STEP 2 의 데이터 관련 탭들을 렌더링합니다"""
    tabs = st.tabs(["데이터 원천", "집행 로드맵", "KPI 목표", "결손 항목"])
    with tabs[0]:
        render_sources(dataset)
    with tabs[1]:
        render_roadmap(dataset)
    with tabs[2]:
        render_kpi(dataset)
    with tabs[3]:
        render_gaps(dataset)
