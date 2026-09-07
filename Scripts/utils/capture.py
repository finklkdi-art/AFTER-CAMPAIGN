# -*- coding: utf-8 -*-
"""
스레드 안전 출력 캡처.

`contextlib.redirect_stdout` 은 **전역** `sys.stdout` 을 바꾼다. 스레드 지역이
아니다. Streamlit Cloud 는 한 프로세스가 모든 접속자를 받고 세션마다 스레드를
쓰므로, 두 AE 가 동시에 분석을 돌리면 다음이 실제로 일어난다.

  · A 가 원본 stdout 을 저장 → B 가 자기 버퍼로 교체 → A 가 종료하며
    "원본"이라고 믿는 값(사실은 B 의 버퍼)으로 되돌린다.
  · 결과 ① A 의 파싱 로그가 B 의 버퍼로 새어 들어간다.
    → `KEY_SCAN_LOG` 는 파싱 실패 시 화면에 보여 주는 값이라,
      **다른 사람의 파일명이 내 화면에 뜨는** 세션 격리 위반이 된다
      (claude.md 1.2).
  · 결과 ② 모든 스레드가 끝난 뒤에도 전역 `sys.stdout` 이 남의 버퍼를 가리킨
    채 남는다. 그 버퍼가 이미 닫혔으면 이후 출력이 조용히 사라지거나 터진다.

  재현: 스레드 4개로 겹쳐 실행하면 한 워커의 출력이 터미널로 새고,
        종료 후 `sys.stdout is not 원본` 이 된다 (2026-09-08 실측).

해결 — 전역을 매번 갈아 끼우지 않는다.
  프록시를 **딱 한 번** 설치하고, 캡처는 스레드 지역 sink 를 세우고 내리는
  것으로만 한다. 스레드가 서로의 상태를 건드릴 일이 없어진다.
"""

import io
import sys
import threading
from contextlib import contextmanager
from typing import Optional, TextIO


class _ThreadRoutedStream(io.TextIOBase):
    """스레드 지역 sink 가 있으면 그쪽으로, 없으면 원본으로 흘려보낸다."""

    def __init__(self, original: Optional[TextIO]):
        self._original = original
        self._local = threading.local()

    # ---- sink 관리 (스레드 지역) ----
    def _get_sink(self):
        return getattr(self._local, 'sink', None)

    def _set_sink(self, sink):
        self._local.sink = sink

    # ---- TextIOBase ----
    def write(self, s: str) -> int:
        target = self._get_sink() or self._original
        if target is None:
            return 0
        try:
            return target.write(s)
        except (ValueError, OSError):
            # 이미 닫힌 버퍼로 쓰려는 경우 — 출력 하나 때문에 파이프라인을
            # 멈추지 않는다.
            return 0

    def flush(self) -> None:
        target = self._get_sink() or self._original
        if target is None:
            return
        try:
            target.flush()
        except (ValueError, OSError):
            pass

    def isatty(self) -> bool:
        try:
            return bool(self._original and self._original.isatty())
        except Exception:
            return False

    def writable(self) -> bool:
        return True

    @property
    def encoding(self):
        return getattr(self._original, 'encoding', 'utf-8')


_installed_out: Optional[_ThreadRoutedStream] = None
_installed_err: Optional[_ThreadRoutedStream] = None
_install_lock = threading.Lock()


def _install() -> None:
    """프록시를 한 번만 설치한다 (두 번 감싸면 출력이 중첩된다)."""
    global _installed_out, _installed_err
    if _installed_out is not None and _installed_err is not None:
        return
    with _install_lock:
        if _installed_out is None:
            _installed_out = _ThreadRoutedStream(sys.stdout)
            sys.stdout = _installed_out
        if _installed_err is None:
            _installed_err = _ThreadRoutedStream(sys.stderr)
            sys.stderr = _installed_err


@contextmanager
def capture_output(sink: Optional[io.StringIO] = None):
    """
    이 스레드의 stdout/stderr 만 `sink` 로 모은다.

    다른 스레드의 출력은 영향을 받지 않으며, 전역 `sys.stdout` 도 바뀌지 않는다.

    Usage:
        log = io.StringIO()
        with capture_output(log):
            noisy_pipeline()
        text = log.getvalue()
    """
    if sink is None:
        sink = io.StringIO()
    _install()
    out, err = _installed_out, _installed_err
    prev_out = out._get_sink() if out else None
    prev_err = err._get_sink() if err else None
    try:
        if out:
            out._set_sink(sink)
        if err:
            err._set_sink(sink)
        yield sink
    finally:
        # 중첩 캡처를 지원하려면 '원래대로'가 아니라 '직전 값'으로 되돌려야 한다
        if out:
            out._set_sink(prev_out)
        if err:
            err._set_sink(prev_err)
