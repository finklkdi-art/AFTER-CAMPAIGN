# -*- coding: utf-8 -*-
"""
STEP 2 - 검증 대시보드 (Stage 1.5 핵심)

기획자(휴먼 터치)가 파싱 결과를 확인하고 교정하는 화면.
수정 내용은 session_state의 CampaignKnowledge 객체에 직접 반영됨.

구성:
  [B] Checklist 경고      - 먼저 봐야 할 정보이므로 최상단
  [A] 메타데이터
  [C] 원본 데이터 좌우 비교
  [D] KPI 수동 매핑
  [E] 크리에이티브 정보
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from models.campaign_knowledge import CampaignKnowledge
from models.checklist import ChecklistItem
from utils.checklist_manager import ChecklistManager
from utils.knowledge_export import KnowledgeValidator
from dashboard import state, step2_dataset


# KPI 수동 매핑 표의 컬럼 정의
KPI_COLUMNS = ['KPI명', '목표치', '달성치', '단위', '비고']


# ========== 공통 유틸 ==========

def _cell_to_text(value: Any) -> str:
    """
    표 셀을 화면 표시용 문자열로 변환합니다.

    엑셀 원본 표는 한 열에 숫자·날짜·문자가 뒤섞여 있어 그대로 두면
    Arrow 직렬화가 매번 실패한다. 표시용이므로 전부 문자열로 통일한다.
    """
    if value is None:
        return ''
    if isinstance(value, float):
        if pd.isna(value):
            return ''
        return f'{value:,.0f}' if float(value).is_integer() else f'{value:,.2f}'
    if isinstance(value, (int,)) and not isinstance(value, bool):
        return f'{value:,}'
    if hasattr(value, 'strftime'):
        try:
            return value.strftime('%Y-%m-%d')
        except Exception:
            pass
    try:
        if pd.isna(value):
            return ''
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _to_display_df(data: Any) -> Optional[pd.DataFrame]:
    """
    파싱된 원본 표 데이터를 화면 표시용 DataFrame으로 변환합니다.

    추출 데이터에는 병합셀/여백으로 인한 NaN이 다수 포함되므로
    빈 행·열을 정리하되, 값 자체는 임의로 가공하지 않음.

    Args:
        data: 원본 표 데이터 (list of dict 또는 list of list)

    Returns:
        정리된 DataFrame (표시할 내용이 없으면 None)
    """
    if data is None:
        return None

    try:
        df = pd.DataFrame(data)
    except Exception:
        return None

    if df.empty:
        return None

    # 전부 비어있는 행·열 제거
    df = df.dropna(axis=0, how='all').dropna(axis=1, how='all')
    if df.empty:
        return None

    # 열 타입 혼재를 없애기 위해 표시용 문자열로 통일
    return df.map(_cell_to_text)


def _parse_number(value: Any) -> Optional[float]:
    """
    입력값에서 숫자를 추출합니다.

    '1,000', '95%', '3.5%' 등 기획자가 흔히 입력하는 형태를 허용함.
    파싱 불가 시 None을 반환하여 달성률 계산에서 제외함.
    """
    if value is None:
        return None
    text = str(value).strip().replace(',', '').replace('%', '')
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


# ========== [B] Checklist 경고 영역 ==========

def _render_checklist(knowledge: CampaignKnowledge) -> None:
    """파싱 중 발견된 예외 사항을 심각도별로 보여 드려요."""
    st.subheader("Checklist — 확인이 필요한 항목")
    st.caption("아래 항목은 최종 PPT 1페이지 [Checklist] 슬라이드의 원천 데이터가 돼요.")

    items = ChecklistManager.sort_checklist(knowledge)

    # 심각도별 렌더러 매핑
    renderers = [
        ('error', st.error, '필수 확인'),
        ('warning', st.warning, '권장 확인'),
        ('info', st.info, '참고'),
    ]

    log = knowledge.pipeline_log
    c1, c2, c3 = st.columns(3)
    c1.metric("오류", log.get('errors_count', 0))
    c2.metric("경고", log.get('warnings_count', 0))
    c3.metric("정보", log.get('info_count', 0))

    if not items:
        st.success("파싱 중 발견된 예외 사항이 없어요.")
    else:
        for severity, renderer, label in renderers:
            group = [i for i in items if i.severity == severity]
            if not group:
                continue
            for item in group:
                body = f"**[{label}] {item.message}**"
                if item.detail:
                    body += f"\n\n{item.detail}"
                if item.source:
                    body += f"\n\n`출처: {item.source}`"
                renderer(body)

    # 데이터 정합성 이슈 (validator가 별도로 수집한 항목)
    coherence = knowledge.validation.get('data_coherence', {}) or {}
    issue_labels = {
        'kpi_matching_issues': 'KPI 항목 불일치',
        'time_range_issues': '기간 불일치',
        'data_anomalies': '이상치 의심',
    }
    found = {k: coherence.get(k) or [] for k in issue_labels}

    if any(found.values()):
        with st.expander("데이터 정합성 상세", expanded=True):
            for key, label in issue_labels.items():
                if found[key]:
                    st.markdown(f"**{label}**")
                    for issue in found[key]:
                        st.markdown(f"- {issue}")


# ========== [A] 메타데이터 영역 ==========

def _render_metadata(knowledge: CampaignKnowledge) -> Dict[str, str]:
    """
    캠페인 메타데이터 입력 폼을 렌더링합니다.

    Returns:
        입력된 값들의 딕셔너리
    """
    st.subheader("캠페인 기본 정보")
    st.caption("여기 적으신 품목명과 일자는 출력 파일명(YYMMDD_품목_자료명_v0_Cheil)에 쓰여요.")

    col1, col2 = st.columns(2)

    with col1:
        campaign_name = st.text_input(
            "캠페인명 *",
            value=knowledge.campaign_name or '',
            help="꼭 필요한 항목이에요. 비워 두면 다음 단계로 넘어갈 수 없어요.",
        )
        date_created = st.text_input(
            "생성 일자 (YYMMDD)",
            value=knowledge.date_created or '',
            help="출력 파일명 앞부분에 쓰여요.",
        )

    with col2:
        category = st.text_input(
            "품목 / 카테고리",
            value=knowledge.category or '',
            help="예: 에어컨, 냉장고, 세탁건조기",
        )
        st.text_input(
            "캠페인 ID (자동 생성)",
            value=knowledge.campaign_id or '',
            disabled=True,
        )

    st.caption(f"원본 폴더: `{knowledge.folder_path}`")

    # 기간 정보 — 제안 기간과 실집행 기간이 다른 사례가 잦아 나란히 배치
    st.markdown("**캠페인 기간**")
    col3, col4 = st.columns(2)

    proposal_meta = knowledge.proposal.get('metadata', {}) or {}
    postbuy_meta = knowledge.postbuy.get('metadata', {}) or {}

    with col3:
        campaign_period = st.text_input(
            "제안서 기준 기간",
            value=proposal_meta.get('campaign_period') or '',
            help="제안서에 명시된 계획 기간",
        )
    with col4:
        report_period = st.text_input(
            "포스트바이 기준 기간 (실집행)",
            value=postbuy_meta.get('report_period') or '',
            help="실제 집행 기간. 제안 기간과 다를 경우 리포트에 사유를 함께 기재하세요.",
        )

    if campaign_period and report_period and campaign_period.strip() != report_period.strip():
        st.info("제안 기간과 실집행 기간이 달라요. 의도한 변경인지 확인해 주세요.")

    return {
        'campaign_name': campaign_name,
        'category': category,
        'date_created': date_created,
        'campaign_period': campaign_period,
        'report_period': report_period,
    }


# ========== [C] 원본 데이터 좌우 비교 ==========

def _render_source_panel(doc: Dict[str, Any], kpi_key: str, title: str) -> None:
    """제안서 또는 포스트바이 한 쪽의 원본 데이터를 렌더링합니다."""
    st.markdown(f"**{title}**")

    status = doc.get('status', 'missing')
    if status != 'found':
        st.warning(f"문서를 찾지 못했어요 (상태: {status})")
        if doc.get('error_msg'):
            st.caption(f"사유: {doc['error_msg']}")
        return

    st.caption(
        f"파일: `{doc.get('file_name', '-')}` · 형식: {doc.get('file_type', '-')} · "
        f"인코딩: {doc.get('encoding', '-')}"
    )

    confidence = doc.get('confidence')
    if isinstance(confidence, (int, float)) and confidence < 0.6:
        st.warning(
            f"문서 역할 추론 신뢰도가 낮아요 ({confidence:.0%}). "
            f"이 문서가 '{title}'가 맞는지 확인하세요."
        )

    entries = doc.get(kpi_key) or []
    if not entries:
        st.info("뽑아낸 표 데이터가 없어요. 원본 문서를 직접 보시고 아래 KPI 표에 입력해 주세요.")
        return

    for idx, entry in enumerate(entries):
        source = entry.get('source', f'표 {idx + 1}')
        df = _to_display_df(entry.get('data'))

        # 첫 번째 표만 펼쳐 두고 나머지는 접어 화면을 정리
        with st.expander(f"{source}", expanded=(idx == 0)):
            if df is None:
                st.caption("표시할 데이터가 없어요.")
            else:
                st.dataframe(df, width="stretch", hide_index=True)


def _render_comparison(knowledge: CampaignKnowledge) -> None:
    """제안서와 포스트바이의 원본 추출 데이터를 좌우로 비교합니다."""
    st.subheader("원본 데이터 대조")
    st.caption(
        "읽어 온 원본 표를 그대로 보여 드려요. 아래 KPI 정리 표에 값을 옮겨 적으실 때 참고해 주세요."
    )

    col1, col2 = st.columns(2)
    with col1:
        _render_source_panel(knowledge.proposal, 'kpi_plan', '제안서 (Proposal)')
    with col2:
        _render_source_panel(knowledge.postbuy, 'kpi_actual', '포스트바이 (PostBuy)')

    # 보조 문서 (미디어브리프, 데일리리포트 등)
    supporting = knowledge.supporting_documents or []
    if supporting:
        with st.expander(f"보조 문서 {len(supporting)}건", expanded=False):
            for doc in supporting:
                st.markdown(
                    f"- `{doc.get('file_name', '-')}` "
                    f"(추론 역할: {doc.get('detected_role', '-')})"
                )


# ========== [D] KPI 수동 매핑 ==========

def _initial_kpi_df(knowledge: CampaignKnowledge) -> pd.DataFrame:
    """KPI 편집 표의 초기 데이터를 구성합니다."""
    existing = getattr(knowledge, 'verified_kpi', None) or []
    if existing:
        df = pd.DataFrame(existing)
        # 누락 컬럼 보강
        for col in KPI_COLUMNS:
            if col not in df.columns:
                df[col] = ''
        return df[KPI_COLUMNS]

    # 빈 행 3개로 시작
    return pd.DataFrame(
        [{col: '' for col in KPI_COLUMNS} for _ in range(3)]
    )


def _render_kpi_editor(knowledge: CampaignKnowledge) -> List[Dict[str, Any]]:
    """
    KPI 수동 매핑 표를 렌더링합니다.

    자동 매칭을 시도하지 않고 기획자 입력에 위임합니다.
    (문서 간 KPI 명칭·단위가 상이해 임의 판단 시 오매칭 위험)

    Returns:
        입력된 KPI 레코드 리스트
    """
    st.subheader("KPI 정리")
    st.caption(
        "위 원본 표를 보면서 목표치와 달성치를 직접 입력하세요. "
        "행을 더하거나 지울 수 있고, 달성률은 아래에서 자동으로 계산해 드려요."
    )

    edited = st.data_editor(
        _initial_kpi_df(knowledge),
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        column_config={
            'KPI명': st.column_config.TextColumn("KPI명", help="예: 노출수, 조회수, 클릭률"),
            '목표치': st.column_config.TextColumn("목표치", help="제안서 기준 목표"),
            '달성치': st.column_config.TextColumn("달성치", help="포스트바이 기준 실적"),
            '단위': st.column_config.TextColumn("단위", help="예: 회, %, 원"),
            '비고': st.column_config.TextColumn("비고", help="증감 사유, 특이사항 등"),
        },
        key='kpi_editor',
    )

    records = edited.fillna('').to_dict('records')
    # 완전히 빈 행 제외
    records = [r for r in records if any(str(v).strip() for v in r.values())]

    _render_achievement(records)
    return records


def _render_achievement(records: List[Dict[str, Any]]) -> None:
    """목표치·달성치가 모두 숫자인 항목의 달성률을 계산해 표시합니다."""
    rows = []
    for r in records:
        target = _parse_number(r.get('목표치'))
        actual = _parse_number(r.get('달성치'))

        if target and actual is not None:
            rate = f"{actual / target * 100:.1f}%"
        else:
            # 숫자로 해석되지 않으면 추정하지 않고 미산출로 표기
            rate = '-'

        rows.append({
            'KPI명': r.get('KPI명', ''),
            '목표치': r.get('목표치', ''),
            '달성치': r.get('달성치', ''),
            '단위': r.get('단위', ''),
            '달성률': rate,
        })

    if rows:
        st.markdown("**달성률 (자동 계산)**")
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        st.caption("목표치와 달성치가 모두 숫자로 읽힐 때만 계산하고, 그 밖에는 '-'로 표기해요.")


# ========== [E] 크리에이티브 정보 ==========

def _render_creative(knowledge: CampaignKnowledge) -> Dict[str, str]:
    """
    크리에이티브(광고 소재) 히스토리를 입력받습니다.

    커뮤니케이션 활동 아카이빙이 본 솔루션의 목적이므로
    파싱으로 확보되지 않는 소재 정보를 여기서 수집합니다.
    """
    st.subheader("크리에이티브 정보")
    st.caption("제안·제작한 광고 소재 히스토리를 적어 주세요. 리포트의 크리에이티브 섹션에 반영돼요.")

    saved = getattr(knowledge, 'creative_info', None) or {}

    col1, col2 = st.columns(2)
    with col1:
        horizontal = st.text_area(
            "가로형 영상",
            value=saved.get('horizontal_video', ''),
            height=90,
            placeholder="예: 15초 메인 필름 2종, 6초 범퍼 3종",
        )
        banner = st.text_area(
            "디지털 배너",
            value=saved.get('banner', ''),
            height=90,
            placeholder="예: GDN 배너 5종, 카카오 비즈보드 2종",
        )
    with col2:
        vertical = st.text_area(
            "세로형 숏폼",
            value=saved.get('vertical_shortform', ''),
            height=90,
            placeholder="예: 릴스/쇼츠 9:16 4종",
        )
        etc = st.text_area(
            "기타 소재 및 특이사항",
            value=saved.get('etc', ''),
            height=90,
            placeholder="예: 인플루언서 협업 콘텐츠, 소재 교체 이력",
        )

    return {
        'horizontal_video': horizontal,
        'vertical_shortform': vertical,
        'banner': banner,
        'etc': etc,
    }


# ========== 저장 및 진행 ==========

def _apply_to_knowledge(
    knowledge: CampaignKnowledge,
    meta: Dict[str, str],
    kpi_records: List[Dict[str, Any]],
    creative: Dict[str, str],
) -> None:
    """
    화면 입력값을 메모리의 CampaignKnowledge 객체에 반영합니다.

    원본 추출 데이터(kpi_plan/kpi_actual)는 추적성을 위해 보존하고,
    기획자가 정리한 KPI는 verified_kpi에 별도 저장합니다.
    """
    knowledge.campaign_name = meta['campaign_name'].strip()
    knowledge.category = meta['category'].strip()
    knowledge.date_created = meta['date_created'].strip()

    knowledge.proposal.setdefault('metadata', {})['campaign_period'] = \
        meta['campaign_period'].strip() or None
    knowledge.postbuy.setdefault('metadata', {})['report_period'] = \
        meta['report_period'].strip() or None

    knowledge.verified_kpi = kpi_records
    knowledge.creative_info = creative

    knowledge.pipeline_log['stage1_5_completed'] = True


def render(project_root: Path) -> None:
    """STEP 2 화면을 렌더링합니다."""
    knowledge = state.get_knowledge()
    if knowledge is None:
        st.warning("먼저 1단계에서 캠페인 폴더를 읽어 주세요.")
        if st.button("STEP 1로 이동"):
            state.goto_step(1)
            st.rerun()
        return

    dataset = state.get(state.KEY_DATASET)

    # [B] Checklist — 가장 먼저 확인해야 할 정보
    _render_checklist(knowledge)
    st.divider()

    # ===== 파싱된 데이터 (원천 / 로드맵 / KPI / 결손) =====
    if dataset is not None:
        step2_dataset.render(dataset)
        st.divider()

    # [A] 메타데이터
    meta = _render_metadata(knowledge)
    st.divider()

    # [C] 원본 데이터 대조
    _render_comparison(knowledge)
    st.divider()

    # [D] KPI 수동 매핑
    kpi_records = _render_kpi_editor(knowledge)
    st.divider()

    # [E] 크리에이티브
    creative = _render_creative(knowledge)
    st.divider()

    # ===== 진행 전 유효성 검증 =====
    blocking: List[str] = []
    advisory: List[str] = []

    if not meta['campaign_name'].strip():
        blocking.append("캠페인명이 비어 있습니다.")

    if (knowledge.proposal.get('status') == 'missing'
            and knowledge.postbuy.get('status') == 'missing'):
        blocking.append("제안서와 포스트바이 중 최소 하나는 있어야 합니다.")

    if not meta['category'].strip():
        advisory.append("품목이 비어 있어 출력 파일명 규칙을 완성할 수 없습니다.")
    if not meta['date_created'].strip():
        advisory.append("생성 일자가 비어 있어 출력 파일명 규칙을 완성할 수 없습니다.")
    if not kpi_records:
        advisory.append("정리된 KPI가 없습니다. 성과 요약 없이 진행됩니다.")

    # 결손 항목 — 미결정 상태는 진행 전에 처리 방법을 정해야 한다
    if dataset is not None:
        undecided = dataset.pending_gaps()
        if undecided:
            names = ", ".join(g.label for g in undecided)
            blocking.append(
                f"[결손 항목] 탭에서 처리 방법(직접 입력/건너뛰기)을 정하세요 — {names}")

    for msg in blocking:
        st.error(msg)
    for msg in advisory:
        st.warning(msg)

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("STEP 1로 돌아가기", width="stretch"):
            state.goto_step(1)
            st.rerun()

    with col2:
        if st.button(
            "수정 완료 및 Stage 2 진행",
            type="primary",
            width="stretch",
            disabled=bool(blocking),
        ):
            # 검증 실패 시 원본이 오염되지 않도록 되돌릴 값을 먼저 확보
            rollback = {
                'campaign_name': knowledge.campaign_name,
                'category': knowledge.category,
                'date_created': knowledge.date_created,
                'verified_kpi': knowledge.verified_kpi,
                'creative_info': knowledge.creative_info,
            }

            _apply_to_knowledge(knowledge, meta, kpi_records, creative)

            # 메타데이터 최종 검증 (기존 유틸 재사용)
            errors = KnowledgeValidator.validate_metadata(knowledge)
            if errors:
                # 잘못된 입력을 메모리에 남기지 않고 이전 상태로 복원
                for key, value in rollback.items():
                    setattr(knowledge, key, value)
                knowledge.pipeline_log.pop('stage1_5_completed', None)

                for err in errors:
                    st.error(f"검증 실패: {err}")
                return

            # 결손 항목의 처리 결과를 Checklist 에 남긴다 (조용한 소실 금지)
            if dataset is not None:
                _record_gap_decisions(knowledge, dataset)
                state.put(state.KEY_DATASET, dataset)

            state.set_knowledge(knowledge)
            state.save_backup(knowledge, project_root)
            state.goto_step(3)
            st.rerun()


def _record_gap_decisions(knowledge: CampaignKnowledge, dataset) -> None:
    """
    기획자가 내린 결손 처리 결정을 Checklist 항목으로 기록합니다.

    건너뛴 항목은 최종 PPT 의 [Checklist] 슬라이드에 사유가 실려,
    보고 받는 사람이 왜 해당 페이지가 비었는지 알 수 있게 한다.
    """
    from models.campaign_data import GAP_FILLED, GAP_SKIPPED

    for gap in dataset.gaps:
        if gap.resolution == GAP_SKIPPED:
            knowledge.add_checklist_item(ChecklistItem(
                type=f'gap_skipped:{gap.key}',
                severity='warning',
                message=f'[기획자 확인] {gap.label} 미포함',
                detail=(f'기획자가 건너뛰기로 결정했어요. '
                        f'영향 블록: {", ".join(gap.affected_slides) or "-"} / 사유: {gap.reason}'),
                source='step2_verify:_record_gap_decisions',
            ))
        elif gap.resolution == GAP_FILLED:
            preview = str(gap.filled_value)
            knowledge.add_checklist_item(ChecklistItem(
                type=f'gap_filled:{gap.key}',
                severity='info',
                message=f'[기획자 입력] {gap.label} 직접 입력됨',
                detail=f'입력 내용: {preview[:180]}',
                source='step2_verify:_record_gap_decisions',
            ))
