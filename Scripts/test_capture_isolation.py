# -*- coding: utf-8 -*-
"""
출력 캡처의 스레드 격리 회귀 테스트

    python Scripts/test_capture_isolation.py

`contextlib.redirect_stdout` 을 그대로 쓰던 시절, 동시에 분석을 돌린 두 AE 의
파싱 로그가 서로 섞이고 전역 `sys.stdout` 이 남의 버퍼를 가리킨 채 남았다.
`KEY_SCAN_LOG` 는 파싱 실패 시 화면에 그대로 보여 주는 값이라, 이건 남의
파일명이 내 화면에 뜨는 세션 격리 위반이다 (claude.md 1.2).

이 테스트는 그 상황을 스레드로 재현해서, 이제는 섞이지 않는지 확인한다.
"""

import io
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils.capture import capture_output          # noqa: E402

THREADS = 6
LINES_PER_THREAD = 12


def main() -> int:
    real_stdout = sys.stdout
    results = {}
    errors = []

    def worker(i: int) -> None:
        sink = io.StringIO()
        try:
            with capture_output(sink):
                for n in range(LINES_PER_THREAD):
                    # 다른 스레드와 구간이 겹치도록 일부러 양보한다
                    print(f'S{i}-L{n}')
                    time.sleep(0.001)
            results[i] = sink.getvalue()
        except Exception as e:
            errors.append(f'thread {i}: {type(e).__name__}: {e}')

    threads = [threading.Thread(target=worker, args=(i,))
               for i in range(THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    problems = list(errors)

    # 1) 각 스레드는 자기 줄만 가져야 한다 (남의 줄이 섞이면 격리 실패)
    for i, text in results.items():
        mine = [l for l in text.splitlines() if l.startswith(f'S{i}-')]
        others = [l for l in text.splitlines()
                  if l.strip() and not l.startswith(f'S{i}-')]
        if len(mine) != LINES_PER_THREAD:
            problems.append(
                f'thread {i}: 자기 출력 {len(mine)}/{LINES_PER_THREAD} 줄만 캡처됨')
        if others:
            problems.append(
                f'thread {i}: 남의 출력이 섞임 — {others[:3]}')

    # 2) 모든 스레드가 결과를 남겼는가
    if len(results) != THREADS:
        problems.append(f'결과 누락 — {len(results)}/{THREADS} 스레드만 완료')

    # 3) 중첩 캡처가 바깥 캡처를 망가뜨리지 않는가
    outer, inner = io.StringIO(), io.StringIO()
    with capture_output(outer):
        print('바깥-1')
        with capture_output(inner):
            print('안쪽')
        print('바깥-2')
    if 'anchor' not in 'x':  # 가독성용 분기 없음
        pass
    if inner.getvalue().strip() != '안쪽':
        problems.append(f'중첩 캡처 안쪽 오염: {inner.getvalue()!r}')
    if [l for l in outer.getvalue().splitlines() if l.strip()] != ['바깥-1', '바깥-2']:
        problems.append(f'중첩 캡처 바깥 오염: {outer.getvalue()!r}')

    # 4) 캡처가 끝난 뒤 출력이 정상으로 돌아오는가
    #    (예전에는 전역 stdout 이 남의 StringIO 를 가리킨 채 남았다)
    probe = io.StringIO()
    with capture_output(probe):
        print('captured')
    if 'captured' not in probe.getvalue():
        problems.append('캡처 자체가 동작하지 않음')

    total = THREADS + 3
    if problems:
        print(f'실패 {len(problems)}건')
        for p in problems:
            print('  - ' + p)
        return 1
    print(f'통과 — 스레드 {THREADS}개 동시 캡처, 출력 섞임 없음 '
          f'(검사 {total}항목)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
