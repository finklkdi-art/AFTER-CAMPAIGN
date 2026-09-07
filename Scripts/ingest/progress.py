# -*- coding: utf-8 -*-
"""
진행률 콜백 프로토콜

Stage 0(업로드)과 Stage 1(파싱)이 UI 에 진행 상황을 알리는 통로.
엔진 계층이 streamlit 을 직접 import 하지 않도록 콜백으로 분리한다
(CLI 폴백과 테스트에서도 같은 코드가 동작해야 함).
"""

from typing import Callable, Optional


class Progress:
    """
    진행률 보고자.

    Args:
        sink: (완료비율 0.0~1.0, 메시지) 를 받는 콜백. None 이면 조용히 무시한다.
        total: 전체 작업 수 (모르면 나중에 set_total 로 지정)
    """

    def __init__(self, sink: Optional[Callable[[float, str], None]] = None,
                 total: int = 0):
        self._sink = sink
        self._total = max(total, 0)
        self._done = 0

    def set_total(self, total: int) -> None:
        self._total = max(total, 0)

    def step(self, message: str = '') -> None:
        """작업 1건 완료를 보고한다."""
        self._done += 1
        self.report(message)

    def report(self, message: str = '') -> None:
        """현재 비율로 메시지를 보고한다 (카운트는 올리지 않음)."""
        if self._sink is None:
            return
        ratio = (self._done / self._total) if self._total else 0.0
        try:
            self._sink(min(max(ratio, 0.0), 1.0), message)
        except Exception:
            # 진행률 표시 실패가 파이프라인을 막지 않는다 (claude.md 3.3)
            pass

    def done(self, message: str = '') -> None:
        self._done = self._total
        self.report(message)


class NullProgress(Progress):
    """아무것도 보고하지 않는 기본 구현 (CLI·테스트용)"""

    def __init__(self):
        super().__init__(sink=None, total=0)
