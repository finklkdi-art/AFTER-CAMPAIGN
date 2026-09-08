# -*- coding: utf-8 -*-
"""
피봇 차트 — 매체별 예산·노출 시각화 (Altair)

Step 2 의 토글 패널과 짝을 이루며, 토글이 바뀌면 '적용' 버튼 없이
즉시 다시 그려진다 (호출부가 `st.fragment` 안에서 부른다).

원칙
  · 원본 `CampaignDataset` 을 절대 바꾸지 않는다. 여기서 하는 일은
    읽기 → 필터 → 집계뿐이다 (claude.md 3.1 데이터 보존).
  · 값이 없는 매체를 0 으로 채우지 않는다. 차트에서 빼되 화면에
    '데이터 없음'으로 명시한다. 조용한 누락은 금지 (3.1).
  · 외부 CDN 을 쓰지 않는다. Altair 는 Streamlit 동봉 렌더러로 그린다.
"""

from typing import Any, Dict, List, Optional, Sequence, Tuple

import altair as alt
import pandas as pd
import streamlit as st

from dashboard import theme_css as T

# 라이트 배경용 계열 — 삼성 블루 코어에서 출발해 명도로 벌린다.
# 첫 두 칸이 브랜드 계열이라 상위 매체가 자연히 강조된다 (토스: 강조는 색이 아니라 위계).
SERIES = [T.BRAND, T.BRAND_LIGHT, '#8FA9F5', '#5B9E8A',
          '#C3893B', '#B0679A', '#6C7480', '#A9AFB9']

# 토스 차트 규칙 — 축선(domain)을 두지 않고, 그리드만 아주 옅게 남긴다.
_AXIS = dict(labelColor=T.TEXT_DIM, titleColor=T.TEXT_DIM,
             gridColor=T.GREY_150, domainColor=T.GREY_200, domain=False,
             tickColor=T.GREY_200, ticks=False,
             labelFontSize=12, titleFontSize=12, labelPadding=6)


def _base(chart: alt.Chart, height: int) -> alt.Chart:
    """공통 테마 — 배경 투명, 라이트 캔버스 축·범례"""
    return (chart
            .properties(height=height, background='rgba(0,0,0,0)')
            .configure_view(strokeWidth=0)
            .configure_axis(**_AXIS)
            .configure_legend(labelColor=T.TEXT_SOFT, titleColor=T.TEXT_DIM,
                              labelFontSize=12, titleFontSize=12,
                              symbolType='circle', symbolSize=90)
            .configure_title(color=T.TEXT_HI, fontSize=14, anchor='start'))


# ═══════════════════════════ 집계 (읽기 전용)

def media_frame(dataset, selected: Optional[Sequence[str]] = None
                ) -> Tuple[pd.DataFrame, List[str]]:
    """
    매체별 실적을 한 프레임으로 모은다.

    '매체 집행 계획'은 애초에 정량값으로 존재하지 않는다 — 미디어믹스의
    예상치는 제안 시점 값이라 부킹 뒤 실집행과 대조할 근거가 못 된다
    (2026.09.09 계획 대비 비교를 화면·PPTX 양쪽에서 전면 제거). 그래서 이
    프레임은 **실집행 실적만** 담는다.

    Returns:
        (프레임, 값이 없어 차트에서 빠진 매체명 목록)

        프레임 컬럼: 매체 / 실집행비 / 노출 / 조회 / 클릭 / VTR / CPC / CPV
    """
    agg: Dict[str, Dict[str, float]] = {}

    def bucket(name: str) -> Dict[str, float]:
        return agg.setdefault(
            (name or '(매체 미상)').strip(),
            {'실집행비': 0.0, '노출': 0.0, '조회': 0.0, '클릭': 0.0,
             'VTR': 0.0, 'CPC': 0.0, 'CPV': 0.0})

    if dataset is not None:
        dr = getattr(dataset, 'daily_report', None)
        if dr is not None:
            # 매체 간 비교 기준은 media_totals (축 혼재로 인한 이중 계상 방지)
            # — 매체당 한 행이라 비율 지표(VTR·CPC·CPV)도 그대로 옮기면 된다.
            for perf in (dr.media_totals or []):
                b = bucket(perf.media)
                m = perf.metrics
                b['실집행비'] += float(perf.budget or m.spend or m.billed or 0)
                b['노출'] += float(m.impressions or 0)
                b['조회'] += float(m.views or 0)
                b['클릭'] += float(m.clicks or 0)
                if m.vtr:
                    b['VTR'] = float(m.vtr)
                if m.cpc:
                    b['CPC'] = float(m.cpc)
                if m.cpv:
                    b['CPV'] = float(m.cpv)

    rows, empty = [], []
    for name, v in agg.items():
        if selected is not None and name not in selected:
            continue
        if sum(v.values()) <= 0:
            empty.append(name)          # 0 으로 채우지 않고 빼되 기록한다
            continue
        rows.append({'매체': name, **v})

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values('노출', ascending=False, ignore_index=True)
    return df, empty


def media_names(dataset) -> List[str]:
    """토글 패널이 쓸 매체 목록 (계획 + 실적 합집합, 등장 순서 보존)"""
    seen: List[str] = []

    def add(name: str) -> None:
        n = (name or '(매체 미상)').strip()
        if n and n not in seen:
            seen.append(n)

    if dataset is not None:
        for line in dataset.plan_lines():
            add(line.media)
        dr = getattr(dataset, 'daily_report', None)
        if dr is not None:
            for perf in (dr.media_totals or []):
                add(perf.media)
            for n in (dr.media_names or []):
                add(n)
    return seen


# 매체별로 비교해 볼 수 있는 지표.
# 값 = df 컬럼에서 바로 읽는다 (media_frame 이 집계). 단위는 표기·서식에 쓴다.
#   count — 그대로 합산된 값 (노출·조회·클릭)
#   pct   — 0~1 비율 (VTR)
#   won   — 원 단위 비용 (CPC·CPV)
# '50% 재생완료' 계열은 파서가 아직 그 값을 읽지 않아 데이터가 없다
# (COLUMN_ALIASES 에 대응 헤더가 없음 — 실 파일의 정확한 표기를 확인한
# 뒤에 넣을 것. 임의로 헤더를 추정해 매칭하지 않는다, claude.md 3.3).
METRIC_UNITS = {
    '노출': 'count', '조회': 'count', '클릭': 'count',
    'VTR': 'pct', 'CPC': 'won', 'CPV': 'won',
    '50% 재생완료': None, '50% 재생완료율': None, '50% 재생완료 CPV': None,
}


# ═══════════════════════════ 차트

def budget_pie(df: pd.DataFrame, column: str = '실집행비',
               height: int = 300) -> None:
    """
    매체별 집행 비중 도넛.

    기본값이 '계획예산'이었는데, 그건 제안 시점 미디어믹스의 값이라 집행
    결과 화면에 실을 근거가 못 된다. 실제로 집행된 금액 기준으로 바꿨다.
    """
    data = df[df[column] > 0][['매체', column]]
    if data.empty:
        T.note(f'{column} 데이터가 없어 비중 차트는 그리지 않았어요.', 'warn')
        return

    total = float(data[column].sum())
    data = data.assign(비중=lambda d: d[column] / total)

    theta = alt.Theta(f'{column}:Q', stack=True)
    color = alt.Color('매체:N',
                      scale=alt.Scale(range=SERIES),
                      # 범례를 우측에 두면 좁은 칼럼에서 도넛과 겹쳐 라벨이
                      # 잘리고, 2열로 접으면 둘째 열이 칼럼 밖으로 밀린다.
                      # 아래 1열이 어떤 폭에서도 안전하다.
                      legend=alt.Legend(title=None, orient='bottom',
                                        columns=1, labelLimit=180,
                                        symbolType='circle'))
    tooltip = ['매체:N', alt.Tooltip(f'{column}:Q', format=',.0f'),
               alt.Tooltip('비중:Q', format='.1%')]

    # cornerRadius 를 stroke 와 같이 쓰면 두 조각이 만나는 자리마다 흰
    # 테두리가 둥글게 겹쳐 그려져, 두 조각이 비슷한 크기일 때 도넛 위쪽이
    # 실제로 이빨 빠진 것처럼 '잘려' 보인다 — 실측 재현. 모서리를 세우고
    # (cornerRadius 제거) 테두리를 얇게 줄이면 이 흰 틈이 사라진다.
    arc = (alt.Chart(data)
           .mark_arc(innerRadius=64, outerRadius=118,
                     stroke='#FFFFFF', strokeWidth=1)
           .encode(theta=theta, color=color, tooltip=tooltip))

    # 조각마다 비중을 표기한다. 너무 얇은 조각(5% 미만)은 숫자끼리 겹치므로
    # 글자를 비워 둔다 — 툴팁으로는 여전히 확인된다. 행을 걸러내지 않고
    # 텍스트만 비우는 이유: arc 층과 행 수·순서가 같아야 누적각(theta)이
    # 서로 어긋나지 않는다(라벨이 다른 조각 위에 얹히는 사고를 막는다).
    label_text = data['비중'].map(lambda v: f'{v:.0%}' if v >= 0.05 else '')
    label = (alt.Chart(data.assign(라벨=label_text))
             .mark_text(radius=91, fontSize=12, fontWeight='bold',
                        color='#FFFFFF')
             .encode(theta=theta, text='라벨:N'))

    st.altair_chart(_base(arc + label, height), width='stretch')


def media_metric_bar(df: pd.DataFrame, metric: str = '노출',
                     height: int = 320) -> None:
    """
    매체별 단일 지표 막대 — 고른 지표를 매체끼리 비교한다.

    예전에는 '계획 vs 실집행'을 나란히 그렸는데, 캠페인 시작부터 '매체
    집행 계획'이란 게 정량값으로 존재하지 않는다 (미디어믹스 예상치는
    제안 시점 값이라 부킹 뒤 실집행과 비교할 근거가 못 된다). 계획축을
    걷어내고, 매체 간 실적 비교 하나로 단순화했다 — PPTX 쪽도 이미 같은
    이유로 계획 대비 비교가 없다(`utils/report/blocks.py`).
    """
    unit = METRIC_UNITS.get(metric)
    if unit is None:
        T.note(f"'{metric}'는 아직 데이터를 못 읽어 와요 — 원본 문서의 "
               f"컬럼 표기를 확인한 뒤 붙일게요.", 'info')
        return
    if metric not in df.columns or df.empty:
        T.note('비교할 매체 데이터가 없어요.', 'warn')
        return

    data = df[df[metric] > 0][['매체', metric]]
    if data.empty:
        T.note(f'{metric} 기준으로 비교할 값이 없어요.', 'warn')
        return

    fmt = {'count': '~s', 'pct': '.1%', 'won': ',.0f'}[unit]
    chart = (alt.Chart(data)
             .mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6,
                       color=T.BRAND)
             .encode(
                 x=alt.X('매체:N', sort='-y', title=None,
                         axis=alt.Axis(labelAngle=-25)),
                 y=alt.Y(f'{metric}:Q', title=None,
                         axis=alt.Axis(format=fmt)),
                 tooltip=['매체:N', alt.Tooltip(f'{metric}:Q', format=fmt)]))
    st.altair_chart(_base(chart, height), width='stretch')


def korean_amount(v: float) -> str:
    """
    큰 수를 한국식 억·만 단위로 줄여 읽히게 만든다.

    요약 타일은 폭이 100px 남짓이라 `498,877,173` 같은 9~11 자리가 그대로는
    잘린다. 잘린 숫자는 없는 숫자와 같으므로 단위로 접는다. 정확한 원값은
    버리지 않고 타일의 help 툴팁에 그대로 병기한다 (claude.md 5 근거 수치).
    """
    a = abs(v)
    if a >= 1e8:
        return f'{v / 1e8:,.1f}억'
    if a >= 1e4:
        return f'{v / 1e4:,.0f}만'
    return f'{v:,.0f}'


def campaign_actuals(dataset) -> Dict[str, Optional[float]]:
    """
    캠페인 전체 실집행 총계(데일리리포트 total).

    매체별 합계와 구분해서 들고 있어야 한다. `media_totals` 는 매체 단위로
    쪼개진 행만 담고 있어, 쪼개지지 않은 집행분이 빠진다 (실측: 19개 매체 중
    10개만 media_totals 에 존재, 1억원이 누락됐다). 그 부분합을 캠페인 계획과
    나란히 놓으면 **거의 다 집행한 캠페인이 미집행으로 보고된다.**
    """
    dr = getattr(dataset, 'daily_report', None)
    if dr is None or getattr(dr, 'total', None) is None:
        return {'spend': None, 'impressions': None}
    t = dr.total
    return {'spend': float(t.spend or t.billed or 0) or None,
            'impressions': float(t.impressions or 0) or None}


def media_spend_of(dataset):
    """
    집행 이후 문서에서 확정한 매체비 총합 (없으면 None).

    값의 정의는 `CampaignDataset.media_spend()` 한 곳에만 둔다 — 화면과
    보고서가 서로 다른 방식으로 합계를 만들어 숫자가 갈라졌던 게 이 버그의
    출발점이었다.
    """
    if dataset is None:
        return None
    getter = getattr(dataset, 'media_spend', None)
    return getter() if callable(getter) else None


def totals_row(df: pd.DataFrame, dataset=None) -> None:
    """
    차트 위 요약 수치 — 근거 수치·출처 병기 (claude.md 3.2 · 5)

    2026.09.08 개편 — '계획 예산 vs 실집행비' 대조를 걷어냈다.
      · 계획 예산은 **제안 시점** 미디어믹스에서 온 값이라 부킹 뒤 값과 다르다.
        집행 결과 보고서에 그 대비 증감을 실으면 사실과 어긋난다.
      · 실집행비는 매체별 행을 더해 만들었는데, 병합셀로 매체명이 빈 행이
        누락돼 실측 캠페인에서 총합이 62,555,145원 모자랐다.
    이제 매체비 총합은 데일리리포트 `Media Mix` 시트의 총계 행에서 직접 읽고,
    포스트바이 `Campaign Summary` 총계와 대조해 표시한다.
    """
    if df.empty:
        return
    act_i = float(df['실집행노출'].sum())

    camp = campaign_actuals(dataset) if dataset is not None else {}
    show_i = camp.get('impressions') or act_i
    spend = media_spend_of(dataset)

    a1, a2 = st.columns(2)
    a1.metric('차트 표시 매체', f'{len(df)}개',
              help='값이 있어 차트에 그린 매체 수예요. '
                   '보고서에는 전체 매체가 들어가요.')

    if spend is not None and spend.total:
        tip = f'정확한 값 · {spend.total:,.0f}원'
        if spend.source_label:
            tip += f' · 출처 {spend.source_label}'
        if spend.verified_value:
            tip += f' · 포스트바이 총계 {spend.verified_value:,.0f}원'
        a2.metric('매체비 총합', korean_amount(spend.total), help=tip)
    else:
        a2.metric('매체비 총합', '—',
                  help='데일리리포트의 Media Mix 시트나 포스트바이 총계에서 '
                       '매체비를 찾지 못했어요.')

    b1, _ = st.columns(2)
    b1.metric('실집행 노출', korean_amount(show_i) if show_i else '—',
              help=f'정확한 값 · {show_i:,.0f}회' if show_i else None)

    _spend_provenance(spend)


def _spend_provenance(spend) -> None:
    """매체비 총합이 어디서 왔고 검증됐는지 한 줄로."""
    if spend is None or not spend.total:
        return
    if spend.confidence == 'low' and spend.note:
        # 두 문서가 다르면 한쪽을 고르지 않고 둘 다 알린다 (claude.md 3.2)
        T.note(f'매체비 총합이 문서마다 달라요 — {spend.note}', 'warn')
        return
    src = spend.source_label or '집행 결과 문서'
    if spend.is_verified():
        st.caption(f'매체비 총합은 {src} 기준이며, 포스트바이 총계와 일치해요.')
    else:
        st.caption(f'매체비 총합은 {src} 기준이에요.')


def panel(dataset, selected: Sequence[str], *, metric: str = '노출',
          show_pie: bool = True, show_bar: bool = True) -> pd.DataFrame:
    """
    토글 선택 상태를 받아 차트 묶음을 그린다.

    호출부가 `st.fragment` 안에서 부르므로, 토글이 바뀌면 이 함수만
    다시 실행되어 차트가 즉시 갱신된다 ('적용' 버튼 없음).
    """
    df, empty = media_frame(dataset, selected)

    if df.empty:
        T.note('선택하신 매체에 표시할 예산·노출 값이 없어요. '
               '좌측에서 매체를 켜 보세요.', 'warn')
        return df

    totals_row(df, dataset)
    T.spacer(6)

    if show_pie and show_bar:
        left, right = st.columns([1, 1.25], gap='large')
        with left:
            st.markdown('##### 매체별 집행 비중')
            budget_pie(df)
        with right:
            st.markdown(f'##### 계획 vs 실집행 · {metric}')
            plan_vs_actual_bar(df, metric)
    elif show_pie:
        st.markdown('##### 매체별 집행 비중')
        budget_pie(df)
    elif show_bar:
        st.markdown(f'##### 계획 vs 실집행 · {metric}')
        plan_vs_actual_bar(df, metric)

    if empty:
        T.note('데이터가 없어 차트에서 제외된 매체 — ' + ', '.join(empty)
               + ' (제외한 사실은 Checklist 에 남겨요)', 'warn')
    return df
