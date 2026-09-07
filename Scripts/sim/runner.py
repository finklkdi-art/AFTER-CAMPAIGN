# -*- coding: utf-8 -*-
"""
시뮬레이션 실행기 — 파이프라인에 태우고 결과를 등급으로 분류한다.

등급은 '예외가 났는가'가 아니라 **사용자가 무엇을 보게 되는가**로 매긴다.
조용히 성공을 반환하는 실패(SILENT_FAILURE)를 SYSTEM_ERROR 보다 나쁘게 보는
이유가 그것이다 — 터지는 실패는 고칠 기회라도 주지만, 성공을 가장한 실패는
AE 가 빈 리포트를 광고주에게 보낼 때까지 아무도 모른다.
"""

import contextlib
import io
import shutil
import tempfile
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# 등급 (나쁜 순)
CRITICAL = 'CRITICAL'          # 프로세스가 죽거나 데이터가 오염됨
SILENT_FAILURE = 'SILENT'      # 실패했는데 성공이라고 보고함
SYSTEM_ERROR = 'SYSTEM_ERROR'  # 예외가 사용자에게 그대로 노출됨
LOGIC_ISSUE = 'LOGIC'          # 결과가 논리적으로 틀림
QUALITY_ISSUE = 'QUALITY'      # 동작은 하나 결과가 쓸 만하지 않음
MINOR = 'MINOR'
PASS = 'PASS'

SEVERITY_ORDER = [CRITICAL, SILENT_FAILURE, SYSTEM_ERROR, LOGIC_ISSUE,
                  QUALITY_ISSUE, MINOR, PASS]

# 이 시간을 넘기면 사용자가 '멈췄다'고 느낀다 (업로드 1건 기준)
SLOW_SECONDS = 20.0


@dataclass
class Result:
    scenario: str
    grade: str = PASS
    seconds: float = 0.0
    notes: List[str] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)

    def fail(self, grade: str, note: str) -> None:
        """더 나쁜 등급으로만 내려간다 (한 시나리오에 여러 문제가 겹칠 때)."""
        if SEVERITY_ORDER.index(grade) < SEVERITY_ORDER.index(self.grade):
            self.grade = grade
        self.notes.append(f'[{grade}] {note}')


@contextlib.contextmanager
def temp_campaign(fixtures, name: str = 'sim'):
    """픽스처를 임시 캠페인 폴더로 실체화한다."""
    root = Path(tempfile.mkdtemp(prefix=f'axsim_{name}_'))
    try:
        for fname, data in fixtures:
            # 경로 탈출 시도는 여기서 무력화한다 — 하네스가 실제로 상위
            # 디렉터리를 건드리면 테스트가 아니라 사고다.
            safe = Path(fname).name or 'unnamed'
            try:
                (root / safe).write_bytes(data)
            except OSError:
                # Windows 예약어(con 등)는 만들 수 없다. 건너뛰되 기록한다.
                pass
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def run_parser_only(path: Path) -> Dict[str, Any]:
    """파일 하나를 파서에만 태운다 (빠른 단위 확인)."""
    from utils.file_parser import FileParser
    return FileParser.parse_file(str(path))


def run_pipeline(folder: Path) -> Dict[str, Any]:
    """
    Stage 1~3 전체를 태운다.

    엔진이 stdout 으로 진행 상황을 찍기 때문에 삼켜 두지 않으면 결과 표가
    로그에 파묻힌다. 삼킨 로그는 실패 분석용으로 돌려준다.
    """
    from utils.capture import capture_output
    from data_scanning import run_step1
    from utils.dataset_builder import CampaignDatasetBuilder
    from utils.checklist_manager import ChecklistManager

    log = io.StringIO()
    out: Dict[str, Any] = {'log': '', 'error': None}
    try:
        with capture_output(log):
            knowledge = run_step1(str(folder))
            dataset = CampaignDatasetBuilder.build(knowledge)
            ChecklistManager.deduplicate_checklist(knowledge)
        out['knowledge'] = knowledge
        out['dataset'] = dataset
    except Exception as e:
        out['error'] = f'{type(e).__name__}: {e}'
        out['traceback'] = traceback.format_exc()
    out['log'] = log.getvalue()
    return out


def run_insights(knowledge, dataset) -> Dict[str, Any]:
    from utils.capture import capture_output
    from utils.insight import InsightEngine
    log = io.StringIO()
    out: Dict[str, Any] = {'error': None}
    try:
        with capture_output(log):
            out['insights'] = InsightEngine().generate(knowledge, dataset)
    except Exception as e:
        out['error'] = f'{type(e).__name__}: {e}'
        out['traceback'] = traceback.format_exc()
    return out


def run_report(knowledge, dataset) -> Dict[str, Any]:
    """Stage 4 덱 구성까지 (PPTX 파일 렌더는 하지 않는다 — 느리고 디스크를 씀)."""
    from utils.capture import capture_output
    from utils.report import ReportSpecBuilder
    log = io.StringIO()
    out: Dict[str, Any] = {'error': None}
    try:
        with capture_output(log):
            out['spec'] = ReportSpecBuilder.build(knowledge, dataset)
    except Exception as e:
        out['error'] = f'{type(e).__name__}: {e}'
        out['traceback'] = traceback.format_exc()
    return out


def summarize(results: List[Result]) -> Dict[str, int]:
    counts = {g: 0 for g in SEVERITY_ORDER}
    for r in results:
        counts[r.grade] += 1
    return counts


def render_table(results: List[Result]) -> str:
    rows = []
    width = max((len(r.scenario) for r in results), default=10)
    for r in results:
        rows.append(f'  {r.grade:<8} {r.seconds:6.2f}s  {r.scenario:<{width}}  '
                    + (r.notes[0] if r.notes else ''))
        for n in r.notes[1:]:
            rows.append(' ' * (10 + 9 + width + 4) + n)
    return '\n'.join(rows)
