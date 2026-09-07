# -*- coding: utf-8 -*-
"""
STEP 3 - 리포트 생성

검증 결과를 요약해 보여주고, Stage 2(블록 구성) → Stage 3(인사이트 도출)
→ Stage 4(PPTX 렌더)를 실행해 결과보고서를 만든다.
Stage 3 는 ReportSpecBuilder.build() 안에서 실행되며 도출 건수와 제외 사유를
이 화면에 표시한다 (제외 사유는 PPT 1페이지 Checklist 에도 실림).
"""

from pathlib import Path

import pandas as pd
import streamlit as st

from models.campaign_knowledge import CampaignKnowledge
from dashboard import state


def _output_filename(knowledge: CampaignKnowledge) -> str:
    """
    출력물 파일명을 규칙에 맞게 조합합니다.

    규칙: YYMMDD_품목_자료명_v0_Cheil
    """
    from utils.errors import safe_filename_part
    date = safe_filename_part(knowledge.date_created, fallback='YYMMDD',
                              max_len=12)
    category = safe_filename_part(knowledge.category, fallback='품목')
    return f"{date}_{category}_결과리포트_v0_Cheil"


def _render_summary(knowledge: CampaignKnowledge) -> None:
    """검증 완료된 데이터를 요약해 보여줍니다."""
    st.subheader("검증 완료 내용")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**캠페인명** · {knowledge.campaign_name or '-'}")
        st.markdown(f"**품목** · {knowledge.category or '-'}")
    with col2:
        proposal_meta = knowledge.proposal.get('metadata', {}) or {}
        postbuy_meta = knowledge.postbuy.get('metadata', {}) or {}
        st.markdown(f"**제안 기간** · {proposal_meta.get('campaign_period') or '-'}")
        st.markdown(f"**실집행 기간** · {postbuy_meta.get('report_period') or '-'}")

    st.markdown(f"**출력 예정 파일명** · `{_output_filename(knowledge)}.pptx`")

    # 정리된 KPI
    kpi = getattr(knowledge, 'verified_kpi', None) or []
    st.markdown("**정리된 KPI**")
    if kpi:
        st.dataframe(pd.DataFrame(kpi), width="stretch", hide_index=True)
    else:
        st.caption("입력하신 KPI가 없어요.")

    # 크리에이티브
    creative = getattr(knowledge, 'creative_info', None) or {}
    filled = {k: v for k, v in creative.items() if str(v).strip()}
    if filled:
        labels = {
            'horizontal_video': '가로형 영상',
            'vertical_shortform': '세로형 숏폼',
            'banner': '디지털 배너',
            'etc': '기타',
        }
        st.markdown("**크리에이티브**")
        for key, value in filled.items():
            st.markdown(f"- **{labels.get(key, key)}** · {value}")

    # 데이터 구성 모드와 결손 처리 결과
    dataset = state.get(state.KEY_DATASET)
    if dataset is not None:
        st.markdown("**데이터 구성**")
        mode = '포스트바이 포함 (Full)' if dataset.mode == 'full' else '포스트바이 없음 (Lite)'
        s = dataset.summary()
        st.markdown(
            f"- 모드 · {mode}\n"
            f"- 계획 라인 {s['plan_lines']:,}건 · 일자별 실적 {s['daily_rows']:,}일 · "
            f"운영 이벤트 {s['events']:,}건"
        )
        skipped = [g for g in dataset.gaps if g.resolution == 'skipped']
        filled = [g for g in dataset.gaps if g.resolution == 'filled']
        if filled:
            st.markdown("- 직접 입력 · " + ", ".join(g.label for g in filled))
        if skipped:
            st.markdown("- 건너뜀 · " + ", ".join(g.label for g in skipped))
            st.caption("건너뛴 항목의 슬라이드는 비어 있고, 그 사유는 Checklist 슬라이드에 남겨요.")

    # Checklist 잔여 항목 — 최종 PPT 1페이지에 실릴 내용
    items = knowledge.get_checklist_items()
    if items:
        with st.expander(f"Checklist 슬라이드에 실릴 항목 {len(items)}건", expanded=False):
            for item in items:
                st.markdown(f"- **[{item.severity}]** {item.message}")


def _versioned_path(out_dir: Path, date: str, category: str) -> Path:
    """
    파일명 규칙 YYMMDD_품목_결과리포트_v{N}_Cheil.pptx
    기존 파일 덮어쓰기 금지 — 같은 이름이 있으면 버전을 올린다.
    """
    v = 0
    while True:
        p = out_dir / f"{date}_{category}_결과리포트_v{v}_Cheil.pptx"
        if not p.exists():
            return p
        v += 1


def _run_stage2(knowledge: CampaignKnowledge, project_root: Path) -> None:
    """결과보고서 PPTX 생성 (campaign-report-pptx 스킬 디자인 적용)"""
    from utils.report import ReportSpecBuilder, ReportRenderer
    from utils.report.fonts import missing_fonts

    st.subheader("결과보고서 생성")

    dataset = state.get(state.KEY_DATASET)
    if dataset is None:
        st.warning("읽어 둔 데이터가 없어서 리포트를 만들 수 없어요. 1단계부터 다시 시작해 주세요.")
        return

    missing = missing_fonts()
    if missing:
        st.warning(
            "다음 폰트가 이 PC에 설치되어 있지 않아요 — "
            "PPT가 다른 글꼴로 보일 수 있어요.\n\n"
            + "\n".join(f"- {f}" for f in missing)
            + "\n\n`Fonts/` 폴더의 파일을 더블클릭해서 설치하신 뒤 다시 만들어 주세요."
        )

    date = (knowledge.date_created or '').strip()
    category = (knowledge.category or '').strip()
    ready = bool(date and category)
    if not ready:
        st.error("생성 일자(YYMMDD)와 품목이 있어야 파일명 규칙에 맞아요. 2단계에서 입력해 주세요.")

    if st.button("결과보고서 PPTX 생성", type="primary",
                 width="stretch", disabled=not ready):
        out_dir = project_root / 'Output' / f"{date}_{knowledge.campaign_name}".strip('_')
        out_path = _versioned_path(out_dir, date, category)
        with st.spinner("스킬 디자인 시스템으로 슬라이드를 조립하는 중..."):
            try:
                # Stage 1.5 에서 기획자가 승인·교정한 인사이트를 그대로 쓴다.
                # 여기서 다시 도출하면 AE 의 수정이 조용히 사라진다.
                spec = ReportSpecBuilder.build(
                    knowledge, dataset, state.get(state.KEY_INSIGHT_SET))
                result = ReportRenderer().render(spec, str(out_path))
            except Exception as e:
                st.error(f"PPTX 생성 실패: {e}")
                return
        ins = getattr(spec, 'insights', None)
        if ins is not None:
            st.info(
                f"Stage 3 자동 도출 — 인사이트 {len(ins.insights)}건 · "
                f"차기 전략 {len(ins.strategies)}건 "
                f"(제외 {len(ins.excluded)}건은 Checklist 슬라이드에 기재)")
            if ins.excluded:
                with st.expander("인사이트 제외 사유", expanded=False):
                    for reason in ins.excluded:
                        st.markdown(f"- {reason}")
        st.success(f"생성 완료 — 슬라이드 {len(spec.slides)}장")
        st.code(result, language=None)
        try:
            with open(result, 'rb') as f:
                st.download_button(
                    "PPTX 내려받기", data=f.read(),
                    file_name=Path(result).name,
                    mime="application/vnd.openxmlformats-officedocument."
                         "presentationml.presentation")
        except OSError:
            pass
        for w in spec.warnings:
            st.caption(f"· {w}")

    backup = state.get(state.KEY_BACKUP_PATH)
    if backup:
        st.caption(f"검증 결과 스냅샷: `{backup}`")


def render(project_root: Path) -> None:
    """STEP 3 화면을 렌더링합니다."""
    knowledge = state.get_knowledge()
    if knowledge is None:
        st.warning("먼저 STEP 1에서 캠페인 폴더를 파싱하세요.")
        if st.button("1단계로 이동"):
            state.goto_step(1)
            st.rerun()
        return

    st.success("확인이 끝났어요.")
    _render_summary(knowledge)
    st.divider()

    _run_stage2(knowledge, project_root)
    st.divider()

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("검증 화면으로 돌아가기", width="stretch"):
            state.goto_step(2)
            st.rerun()
    with col2:
        if st.button("다른 캠페인 분석하기", width="stretch"):
            state.set_knowledge(None)
            state.goto_step(1)
            st.rerun()
