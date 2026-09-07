# -*- coding: utf-8 -*-
"""
Session State 관리 헬퍼

Streamlit의 session_state는 동일 프로세스의 메모리이므로
CampaignKnowledge 객체를 직렬화 없이 그대로 보관함.
(JSON 왕복으로 인한 데이터 손실 구간 제거)
"""

from pathlib import Path
from typing import Optional, Any

import streamlit as st

from models.campaign_knowledge import CampaignKnowledge


# ========== Session State 키 상수 ==========
# 문자열 오타 방지를 위해 상수로 관리
KEY_STEP = 'ax_step'                    # 현재 단계 (1, 2, 3)
KEY_KNOWLEDGE = 'ax_knowledge'          # CampaignKnowledge 메모리 객체
KEY_FOLDER = 'ax_folder'                # 선택된 캠페인 폴더 경로
KEY_BACKUP_PATH = 'ax_backup_path'      # 검증 후 백업 JSON 경로
KEY_SCAN_LOG = 'ax_scan_log'            # Stage 1 파싱 로그
KEY_DATASET = 'ax_dataset'              # CampaignDataset (Stage 2 입력)
KEY_DATASET_PATH = 'ax_dataset_path'    # 데이터셋 스냅샷 JSON 경로
KEY_SPEC = 'ax_spec'                    # ReportSpec (미리보기·부분 리렌더링)
KEY_WORKSPACE = 'ax_workspace'          # 업로드 작업 폴더 경로
KEY_FLASH = 'ax_flash'                  # 다음 화면 상단에 한 번 보여줄 안내
KEY_PROJECT_ROOT = 'ax_project_root'    # 프로젝트 루트 (.env 탐색용)
KEY_INSIGHT_SET = 'ax_insight_set'      # InsightSet — Stage 1.5 에서 AE 가 교정한 원본
KEY_INSIGHT_APPROVED = 'ax_insight_ok'  # 인사이트 승인 여부 (미승인 시 Stage 4 차단)


def init_state() -> None:
    """Session state 기본값을 초기화합니다 (최초 1회)."""
    defaults = {
        KEY_STEP: 1,
        KEY_KNOWLEDGE: None,
        KEY_FOLDER: None,
        KEY_BACKUP_PATH: None,
        KEY_SCAN_LOG: '',
        KEY_DATASET: None,
        KEY_SPEC: None,
        KEY_WORKSPACE: None,
        KEY_FLASH: None,
        KEY_PROJECT_ROOT: None,
        KEY_INSIGHT_SET: None,
        KEY_INSIGHT_APPROVED: False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# ========== Step 이동 ==========

def get_step() -> int:
    """현재 단계를 반환합니다."""
    return st.session_state.get(KEY_STEP, 1)


def goto_step(step: int) -> None:
    """지정한 단계로 이동합니다."""
    st.session_state[KEY_STEP] = step


# ========== Knowledge 접근 ==========

def get_knowledge() -> Optional[CampaignKnowledge]:
    """
    메모리에 보관 중인 CampaignKnowledge 객체를 반환합니다.

    Returns:
        CampaignKnowledge 객체 (Stage 1 미실행 시 None)
    """
    return st.session_state.get(KEY_KNOWLEDGE)


def set_knowledge(knowledge: CampaignKnowledge) -> None:
    """CampaignKnowledge 객체를 메모리에 보관합니다."""
    st.session_state[KEY_KNOWLEDGE] = knowledge


def has_knowledge() -> bool:
    """Stage 1 파싱이 완료되었는지 확인합니다."""
    return st.session_state.get(KEY_KNOWLEDGE) is not None


# ========== 범용 헬퍼 ==========

def get(key: str, default: Any = None) -> Any:
    """Session state 값을 조회합니다."""
    return st.session_state.get(key, default)


def put(key: str, value: Any) -> None:
    """Session state 값을 저장합니다."""
    st.session_state[key] = value


# ========== 백업 스냅샷 ==========

def save_backup(knowledge: CampaignKnowledge, project_root: Path) -> Optional[str]:
    """
    검증 완료된 Knowledge와 파싱 데이터셋을 JSON 스냅샷으로 저장합니다.

    파이프라인 진행에는 메모리 객체를 그대로 사용하되, 브라우저를 닫으면
    파싱 결과와 기획자가 채운 결손 값이 사라지므로 '이어하기' 용도로 함께 남긴다.
    두 파일은 같은 타임스탬프로 짝을 맞춘다.

    Args:
        knowledge: 검증 완료된 CampaignKnowledge 객체
        project_root: 프로젝트 루트 경로

    Returns:
        저장된 Knowledge 파일 경로 (실패 시 None)
    """
    from utils.knowledge_export import KnowledgeExport

    temp_dir = Path(project_root) / 'Output' / 'Temp'
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        path = KnowledgeExport.export_to_json(knowledge, str(temp_dir))
        st.session_state[KEY_BACKUP_PATH] = path
    except Exception as e:
        # 백업 실패가 파이프라인을 막지 않도록 경고만 표시
        st.warning(f"백업 스냅샷 저장 실패 (파이프라인은 계속 진행): {e}")
        return None

    # 데이터셋 스냅샷 — Knowledge 파일명의 타임스탬프를 그대로 사용해 짝을 맞춤
    dataset = get(KEY_DATASET)
    if dataset is not None:
        try:
            from utils import dataset_snapshot
            stamp = Path(path).stem.replace('Draft_Knowledge_', '')
            st.session_state[KEY_DATASET_PATH] = dataset_snapshot.save(
                dataset, str(temp_dir), timestamp=stamp)
        except Exception as e:
            st.warning(f"데이터셋 스냅샷 저장 실패 (파이프라인은 계속 진행): {e}")

    return path
