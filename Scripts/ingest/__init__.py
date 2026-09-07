# -*- coding: utf-8 -*-
"""
Stage 0 — 업로드 인제스트

업로드된 파일을 세션 작업 폴더에 실체화하여, 기존 폴더 기반 파이프라인이
그대로 동작하게 한다. 파서를 스트림 방식으로 재작성하지 않는 이유는
검증이 끝난 파서 계층을 건드리지 않기 위해서다.
"""

from .progress import Progress, NullProgress
from .workspace import UploadWorkspace

__all__ = ['Progress', 'NullProgress', 'UploadWorkspace']
