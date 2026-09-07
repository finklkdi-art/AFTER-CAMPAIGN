# -*- coding: utf-8 -*-
"""
STEP 1 — 파일 업로드 (Stage 0 + Stage 1)

2026.09.05 개편
  · 탭(업로드 / 폴더 선택) 구조를 폐기했다. 업로드 슬롯 하나를 화면 폭
    전체로 두고, 폴더 선택과 이어하기는 하단 접이식으로 강등한다.
  · 파싱 진행은 화면 중앙 팝업(`st.dialog`)에 띄운다.

업로드본은 `Output/Temp/Uploads/<세션>/` 에 실체화한 뒤 기존 폴더 기반
파이프라인을 그대로 태운다 (`Input/` 은 읽기 전용).

진행 문구 원칙
  타이머로 문구를 순환시키지 않는다. 엔진(`Progress` 콜백)이 실제로
  보고한 단계만 AE 언어로 번역해 노출한다 (claude.md 5 — 추측성 포장 금지).
  번역 규칙은 `Config/progress_labels.json` 에 외부화되어 있다.

안내 문구는 실측 근거를 따른다 (Rule Book 8.3).
  확장자별 파싱 속도 실측(2026.09.03, 샘플 32개 파일):
    pptx 0.01초/MB · pdf 0.46 · xlsx 0.54
  → 원본(PPTX/EXCEL)이 PDF보다 느리지 않으며 표 구조가 보존되어 인식률이 높다.
"""

import contextlib
import io
import json
from pathlib import Path
from typing import List, Optional, Tuple

import streamlit as st

from data_scanning import run_step1
from utils.checklist_manager import ChecklistManager
from utils.dataset_builder import CampaignDatasetBuilder
from utils import dataset_snapshot
from ingest import UploadWorkspace, Progress
from dashboard import state, theme_css as T

UPLOAD_HINT = (
    'PDF보다 원본 파일(PPTX · XLSX)을 올리시면 인식이 더 정확해요. '
    '용량이 크면 읽는 데 시간이 꽤 걸릴 수 있어요.'
)

ACCEPTED = ['pdf', 'xlsx', 'xls', 'pptx', 'docx',
            'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp']

KEY_WORKSPACE = state.KEY_WORKSPACE


# ═══════════════════════════ 진행 문구 번역

_LABEL_RULES: Optional[List[Tuple[str, str]]] = None


def _label_rules(project_root: Path) -> List[Tuple[str, str]]:
    """Config/progress_labels.json 을 1회 읽어 (match, label) 목록으로."""
    global _LABEL_RULES
    if _LABEL_RULES is not None:
        return _LABEL_RULES

    rules: List[Tuple[str, str]] = []
    try:
        path = Path(project_root) / 'Config' / 'progress_labels.json'
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for r in data.get('rules', []):
            m, l = str(r.get('match', '')), str(r.get('label', ''))
            if m and l:
                rules.append((m.lower(), l))
    except Exception:
        # 설정이 없거나 깨져도 진행에는 지장이 없다 — 엔진 원문을 그대로 쓴다
        rules = []
    _LABEL_RULES = rules
    return rules


def _friendly(message: str, project_root: Path) -> str:
    """엔진 진행 메시지 → AE 언어. 규칙에 없으면 원문을 그대로 둔다."""
    text = (message or '').strip()
    if not text:
        return '처리 중…'
    low = text.lower()
    for match, label in _label_rules(project_root):
        if match in low:
            return label
    return text


# ═══════════════════════════ 분석 팝업

@st.dialog('캠페인 자료 분석 중', width='large')
def _analyze_dialog(folder: Path, project_root: Path, *, label: str,
                    uploads=None) -> None:
    """
    화면 중앙 팝업에서 업로드 실체화 + Stage 1 파싱을 수행한다.

    팝업 안에서 작업을 직접 돌리므로, 진행률과 단계 문구가 실시간으로
    갱신된다. 완료 시 `st.rerun()` 이 팝업을 닫고 STEP 2 로 넘긴다.
    """
    bar = st.progress(0.0, text='준비 중…')
    status = st.empty()
    detail = st.empty()
    status.markdown('##### 준비 중…')

    log = io.StringIO()
    warns: List[str] = []

    def show(ratio: float, message: str) -> None:
        text = _friendly(message, project_root)
        bar.progress(min(max(ratio, 0.0), 1.0), text='')
        status.markdown(f'##### {text}')
        if message and message.strip() != text:
            detail.caption(message.strip())

    # ── Stage 0: 업로드 실체화
    if uploads:
        ws = UploadWorkspace(folder)
        saved, warns = ws.materialize(uploads, progress=Progress(show))
        if not saved:
            st.error('저장된 파일이 없어요.')
            for w in warns:
                T.note(w, 'err')
            if st.button('닫기', width='stretch'):
                st.rerun()
            return
        state.put(KEY_WORKSPACE, str(ws.root))
        folder = ws.root

    # ── Stage 1: 파싱 + 데이터셋 구성
    try:
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            knowledge = run_step1(str(folder), on_progress=show)
            show(0.97, '캠페인 지식 구조화')
            dataset = CampaignDatasetBuilder.build(knowledge)
            ChecklistManager.deduplicate_checklist(knowledge)
    except Exception as e:
        bar.empty()
        status.markdown('##### 분석하지 못했어요')
        st.error(f'파일을 읽지 못했어요: {e}')
        st.markdown('###### 파싱 로그')
        st.code(log.getvalue()[-4000:] or '(로그 없음)')
        if st.button('닫기', width='stretch'):
            st.rerun()
        return

    outcome = _outcome(knowledge, dataset)

    bar.progress(1.0, text='')
    status.markdown(f'##### {outcome["headline"]}')
    detail.empty()

    state.set_knowledge(knowledge)
    state.put(state.KEY_DATASET, dataset)
    state.put(state.KEY_FOLDER, str(folder))
    state.put(state.KEY_SCAN_LOG, log.getvalue())
    state.put(state.KEY_SPEC, None)   # 새 파싱 — 이전 초안 폐기

    if warns:
        # 업로드 경고를 조용히 버리지 않는다 (claude.md 3.1)
        state.put('ax_upload_warnings', warns)
        outcome['detail'] += f' · 업로드 경고 {len(warns)}건'

    state.put(state.KEY_FLASH, outcome)
    state.goto_step(2)
    st.rerun()


# ═══════════════════════════ 분석 결과 등급

def _outcome(knowledge, dataset) -> dict:
    """
    분석 결과를 **사람 기준**으로 등급화한다.

    기존에는 결과와 무관하게 초록색 '분석 완료' 를 띄웠다. 파일이 전부
    사내 문서보안(DRM)에 걸려 한 글자도 못 읽은 경우조차 '완료 — 계획 라인
    0건' 이라고 말해서, AE 는 잘 된 줄 알고 빈 리포트까지 갔다. 성공처럼
    보이는 실패가 가장 나쁜 실패다 — 숫자를 하나도 못 건졌으면 그렇다고
    말한다 (claude.md 3.3 · 추측성 긍정 포장 금지).

    Returns:
        {'level': ok|warn|err, 'headline': 한 줄, 'detail': 보조 한 줄,
         'hint': 다음 행동(있을 때만)}
    """
    s = dataset.summary()
    docs = list(getattr(knowledge, 'documents', []) or [])
    failed = [d for d in docs if getattr(d, 'status', '') == 'error']
    n_all, n_bad = len(docs), len(failed)

    # '쓸 수 있는 숫자를 건졌는가' 가 성공의 기준이다. 문서를 몇 개 열었는지가
    # 아니라 — 리포트에 들어갈 값이 나왔는지가 AE 에게 중요한 사실이다.
    numbers = (s['plan_lines'] + s['daily_rows']
               + s['media_performance'] + s['kpi_targets'])

    detail = (f'계획 라인 {s["plan_lines"]:,}건 · '
              f'일자별 실적 {s["daily_rows"]:,}일 · '
              f'매체 실적 {s["media_performance"]:,}건')

    if numbers == 0:
        hint = _fail_hint(failed)
        if n_bad and n_bad == n_all:
            head = f'{n_all}개 파일을 모두 읽지 못했어요'
        elif n_bad:
            head = f'읽을 수 있는 수치가 없어요 — 파일 {n_bad}건이 열리지 않았어요'
        else:
            head = '파일은 열렸지만 성과 수치를 찾지 못했어요'
        return {'level': 'err', 'headline': head, 'detail': detail, 'hint': hint}

    if n_bad:
        return {'level': 'warn',
                'headline': f'문서 {n_all - n_bad}건을 읽었어요 · {n_bad}건은 열지 못했어요',
                'detail': detail, 'hint': _fail_hint(failed)}

    return {'level': 'ok',
            'headline': f'문서 {n_all}건을 읽었어요',
            'detail': detail, 'hint': ''}


def _fail_hint(failed) -> str:
    """
    실패 사유가 한 가지로 모이면 그 한 가지만 말한다.

    같은 사유 여섯 줄보다 '여섯 건 다 같은 이유' 한 줄이 훨씬 빨리 읽힌다.
    """
    if not failed:
        return ''
    reasons = [(getattr(d, 'error_msg', '') or '') for d in failed]
    if any('문서보안' in r or 'DRM' in r.upper() or 'NASCA' in r.upper()
           for r in reasons):
        return ('사내 문서보안(DRM)이 걸린 파일이에요. '
                '파일 우클릭 → 문서보안 해제 후 다시 올려 주세요.')
    return '파일이 손상됐거나 지원하지 않는 형식일 수 있어요.'


# ═══════════════════════════ 업로드 (주 동선)

def _render_upload(project_root: Path) -> None:
    st.markdown('### 캠페인 자료를 올려 주세요')
    # 절 단위로 묶어 문장 중간에서 줄이 바뀌지 않게 한다 (claude.md 5)
    st.markdown(
        '<p class="ax-lead">'
        '<span class="kbr">제안서, 미디어믹스, 데일리리포트, 포스트바이,</span> '
        '<span class="kbr">게재보고 등 캠페인 관련 파일을</span> '
        '<span class="kbr">한번에 올려주세요.</span></p>',
        unsafe_allow_html=True)
    T.spacer(6)

    # 라벨은 지우지 않고 숨긴다 — 회색 점선 영역이 이미 '떨어뜨리는 자리'라고
    # 말하고 있어 화면에는 군더더기지만, 스크린리더에는 남아야 한다.
    files = st.file_uploader(
        '파일을 끌어다 놓거나 눌러서 선택해 주세요',
        type=ACCEPTED, accept_multiple_files=True, key='ax_uploader',
        label_visibility='collapsed')

    T.note(UPLOAD_HINT, 'ok')

    if not files:
        return

    # 올린 파일은 접지 않고 칩으로 그대로 보여 준다 (claude.md 5).
    # 무엇을 올렸는지는 '분석 시작' 직전에 가장 확인하고 싶은 정보다.
    total_mb = sum(getattr(f, 'size', 0) for f in files) / 1048576
    st.markdown(f'###### 올린 파일 {len(files)}개 · 합계 {total_mb:.1f}MB')
    chips = ''.join(
        f'<span class="ax-file">{T._esc(f.name)}'
        f'<span class="sz">{getattr(f, "size", 0) / 1048576:.1f}MB</span>'
        f'</span>' for f in files)
    st.markdown(f'<div class="ax-files">{chips}</div>', unsafe_allow_html=True)

    T.spacer(8)
    _, mid, _ = st.columns([1, 1.6, 1])
    with mid:
        if st.button('분석 시작하기', type='primary', width='stretch'):
            _analyze_dialog(project_root, project_root,
                            label='업로드 분석 완료', uploads=files)


# ═══════════════════════════ 폴더 선택 (보조 동선)

def _list_campaign_folders(input_dir: Path) -> List[Tuple[str, Path]]:
    """Input 폴더 하위의 캠페인 폴더 목록"""
    candidates: List[Tuple[str, Path]] = []
    samples_dir = input_dir / 'Samples'
    search_dirs = [samples_dir] if samples_dir.is_dir() else []
    if input_dir.is_dir():
        search_dirs.append(input_dir)

    seen = set()
    for base in search_dirs:
        for child in sorted(base.iterdir()):
            if not child.is_dir() or child.name.startswith(('_', '.')):
                continue
            if child.name == 'Samples' or child.resolve() in seen:
                continue
            seen.add(child.resolve())
            count = sum(1 for f in child.iterdir()
                        if f.is_file()
                        and f.suffix.lower() in ('.pdf', '.xlsx', '.xls',
                                                 '.pptx', '.docx'))
            candidates.append((f'{child.name}  ({count}개 문서)', child))
    return candidates


def _render_folder(project_root: Path) -> None:
    try:
        folders = _list_campaign_folders(_source_root(project_root) / 'Input')
    except OSError:
        folders = []
    if not folders:
        return

    labels = [x for x, _ in folders]
    idx = next((i for i, x in enumerate(labels) if '★' in x), 0)
    chosen = st.selectbox('캠페인 폴더', labels, index=idx,
                          label_visibility='collapsed')
    path = dict(zip(labels, [p for _, p in folders]))[chosen]

    if st.button('이 폴더로 시작하기', width='stretch'):
        _analyze_dialog(path, _source_root(project_root),
                        label='폴더 분석 완료')


# ═══════════════════════════ 이어하기

def _render_resume(project_root: Path) -> None:
    """이전 작업 스냅샷 복원 — 파싱과 결손 입력을 다시 하지 않도록"""
    temp_dir = project_root / 'Output' / 'Temp'
    try:
        snaps = dataset_snapshot.list_snapshots(str(temp_dir), limit=5)
    except Exception:
        snaps = []
    if not snaps:
        st.caption('이어서 할 이전 작업이 없어요.')
        return

    options = {label: path for label, path in snaps}
    pick = st.selectbox('스냅샷', list(options.keys()), key='ax_snap_pick')
    if st.button('이 스냅샷으로 복원', width='stretch'):
        _restore(options[pick])


def _restore(dataset_path: str) -> None:
    from utils.knowledge_export import KnowledgeExport
    try:
        kpath = dataset_snapshot.knowledge_pair(dataset_path)
        if not kpath:
            st.error('짝이 되는 Knowledge 스냅샷을 찾지 못했어요.')
            return
        knowledge = KnowledgeExport.import_from_json(kpath)
        dataset = dataset_snapshot.load(dataset_path)
    except Exception as e:
        st.error(f'복원 실패: {e}')
        return

    state.set_knowledge(knowledge)
    state.put(state.KEY_DATASET, dataset)
    state.put(state.KEY_FOLDER, knowledge.folder_path)
    state.put(state.KEY_BACKUP_PATH, kpath)
    state.put(state.KEY_FLASH, '이전 작업을 불러왔어요.')
    state.goto_step(2)
    st.rerun()


# ═══════════════════════════ 진입점

def _source_root(project_root: Path) -> Path:
    """
    `Input/` 을 찾을 기준 경로.

    호출부가 넘기는 `project_root` 는 세션 샌드박스다(web_main). 샌드박스에는
    `Input/` 심볼릭 링크를 걸어 두게 되어 있는데, Windows 에서는 링크 생성에
    권한이 필요해 조용히 실패한다(WinError 1314). 그래서 링크에 기대지 않고
    실제 프로젝트 루트를 직접 본다 — `Input/` 은 읽기 전용 원본이라
    샌드박스 격리(디스크 '쓰기' 를 가두는 장치)와 어긋나지 않는다.
    """
    real = state.get(state.KEY_PROJECT_ROOT)
    return Path(real) if real else Path(project_root)


def _has_local_campaigns(project_root: Path) -> bool:
    """`Input/` 에 실제로 캠페인 폴더가 있는지 — 조건부 노출의 기준."""
    try:
        return bool(_list_campaign_folders(_source_root(project_root) / 'Input'))
    except OSError:
        return False


def render(project_root: Path) -> None:
    """
    자료 업로드 화면.

    2026.09.07 — 업로드를 주 동선으로 단일화했다. 보조 동선인 `Input/` 캠페인
    폴더 선택(claude.md 2 의 지원 입력 경로)은 **폴더가 실제로 있을 때만**
    화면에 나타난다. 호스팅 서버에는 `Input/` 이 없으므로 배포 화면은 업로드
    하나로 유지되고, 로컬에서 도는 AE 만 폴더 선택을 보게 된다.
    조건부로 두는 이유는 단순함 때문이다 — 쓸 수 없는 선택지를 늘 띄워 두면
    화면만 복잡해지고 '이건 왜 안 되지' 하는 질문을 만든다.
    '이전 작업 이어하기'(`_render_resume`)는 되살릴 수 있도록 남겨만 둔다.
    """
    _render_upload(project_root)

    if _has_local_campaigns(project_root):
        T.spacer(28)
        st.markdown('<div class="ax-alt-sep"><span>또는</span></div>',
                    unsafe_allow_html=True)
        st.markdown('<div class="ax-sec-h">이 PC의 캠페인 폴더에서 고르기</div>',
                    unsafe_allow_html=True)
        _render_folder(project_root)
