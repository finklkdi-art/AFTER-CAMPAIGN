# -*- coding: utf-8 -*-
"""
업로드 작업 폴더

업로드된 파일을 `Output/Temp/Uploads/<세션>/` 에 실체화한다.

- `Input/` 은 읽기 전용이므로 업로드본을 그 아래에 쓰지 않는다 (Rule Book 1.2)
- 실체화 후에는 기존 폴더 기반 파이프라인(`run_step1(folder)`)이 그대로 동작한다
- 외부로 나가는 경로가 없다. 전부 로컬 파일시스템 내에서만 처리한다 (1.1)
"""

import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from .progress import Progress, NullProgress

# 파싱 대상 확장자 — 그 외(이미지·영상)는 보관만 하고 파서를 태우지 않는다
PARSABLE_SUFFIXES = {'.pdf', '.xlsx', '.xls', '.pptx', '.docx'}
IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}

# 업로드 1건 상한 (실측: 샘플 최대 29.9MB) — 초과분은 거르지 않고 경고만 남긴다
LARGE_FILE_MB = 50

_UNSAFE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def safe_name(name: str) -> str:
    """
    업로드 파일명을 파일시스템에 안전하게 만든다.

    한글은 그대로 보존한다 (역할 추론이 한글 파일명 패턴에 의존하므로
    로마자로 바꾸면 판정이 무너진다).
    """
    cleaned = _UNSAFE.sub('_', name).strip().strip('.')
    return cleaned or 'unnamed'


class UploadWorkspace:
    """
    한 캠페인의 업로드 작업 폴더.

    Args:
        project_root: 프로젝트 루트
        session_id: 세션 식별자 (없으면 타임스탬프)
    """

    def __init__(self, project_root: Path, session_id: Optional[str] = None):
        self.project_root = Path(project_root)
        self.session_id = session_id or datetime.now().strftime('%y%m%d_%H%M%S')
        self.root = (self.project_root / 'Output' / 'Temp' / 'Uploads'
                     / self.session_id)

    # ------------------------------------------------------------------

    def materialize(self, uploads: Iterable, *,
                    progress: Optional[Progress] = None
                    ) -> Tuple[List[Path], List[str]]:
        """
        업로드 객체들을 작업 폴더에 파일로 저장한다.

        Args:
            uploads: Streamlit UploadedFile 처럼 `.name` 과 `.getbuffer()`
                     (또는 `.read()`) 를 가진 객체들
            progress: 진행률 보고자

        Returns:
            (저장된 경로 리스트, 경고 메시지 리스트)
        """
        items = list(uploads)
        prog = progress or NullProgress()
        prog.set_total(len(items))

        self.root.mkdir(parents=True, exist_ok=True)
        saved: List[Path] = []
        warnings: List[str] = []
        seen: dict = {}

        for up in items:
            name = safe_name(getattr(up, 'name', '') or 'unnamed')

            # 같은 이름이 여러 번 올라와도 덮어쓰지 않는다 (데이터 보존 2.0)
            stem, suffix = Path(name).stem, Path(name).suffix
            n = seen.get(name, 0)
            seen[name] = n + 1
            if n:
                name = f'{stem}({n}){suffix}'
                warnings.append(f'동일 파일명 중복 업로드 — "{name}" 으로 보존')

            dest = self.root / name
            try:
                data = self._read(up)
                with open(dest, 'wb') as f:
                    f.write(data)
                saved.append(dest)

                mb = len(data) / 1048576
                if mb > LARGE_FILE_MB:
                    warnings.append(f'{name} — {mb:.0f}MB, 파싱에 시간이 걸릴 수 있음')
                if suffix.lower() not in PARSABLE_SUFFIXES | IMAGE_SUFFIXES:
                    warnings.append(f'{name} — 파싱 대상 확장자가 아님 (보관만 함)')
            except Exception as e:
                # 한 건 실패로 전체를 중단하지 않는다 (claude.md 3.3)
                warnings.append(f'{name} 저장 실패: {e}')
            finally:
                prog.step(f'{name} 저장')

        prog.done('업로드 완료')
        return saved, warnings

    @staticmethod
    def _read(upload) -> bytes:
        """UploadedFile / 파일 객체 / bytes 를 모두 받아 bytes 로 만든다."""
        if isinstance(upload, (bytes, bytearray)):
            return bytes(upload)
        for attr in ('getbuffer', 'getvalue', 'read'):
            fn = getattr(upload, attr, None)
            if callable(fn):
                return bytes(fn())
        raise TypeError(f'읽을 수 없는 업로드 객체: {type(upload).__name__}')

    # ------------------------------------------------------------------

    def summary(self) -> dict:
        """작업 폴더 구성 요약 (화면 표시용)"""
        if not self.root.is_dir():
            return {'files': 0, 'parsable': 0, 'images': 0, 'mb': 0.0}
        files = [p for p in self.root.iterdir() if p.is_file()]
        return {
            'files': len(files),
            'parsable': sum(1 for p in files
                            if p.suffix.lower() in PARSABLE_SUFFIXES),
            'images': sum(1 for p in files
                          if p.suffix.lower() in IMAGE_SUFFIXES),
            'mb': sum(p.stat().st_size for p in files) / 1048576,
        }

    def cleanup(self) -> bool:
        """
        작업 폴더를 지운다.

        업로드본은 원본이 아니라 사본이지만, 지우기 전 반드시 호출자가
        의도를 확인해야 한다 (조용한 삭제 금지).
        """
        if not self.root.is_dir():
            return False
        shutil.rmtree(self.root, ignore_errors=True)
        return not self.root.exists()

    @classmethod
    def list_sessions(cls, project_root: Path, limit: int = 10
                      ) -> List[Tuple[str, Path, int]]:
        """
        기존 업로드 세션 목록 (최신순).

        Returns: (세션ID, 경로, 파일 수)
        """
        base = Path(project_root) / 'Output' / 'Temp' / 'Uploads'
        if not base.is_dir():
            return []
        out = []
        for d in sorted(base.iterdir(), key=lambda p: p.name, reverse=True):
            if d.is_dir():
                out.append((d.name, d, sum(1 for f in d.iterdir() if f.is_file())))
        return out[:limit]
