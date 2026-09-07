# -*- coding: utf-8 -*-
"""
백엔드 파이프라인 시뮬레이션

    python Scripts/test_pipeline_sim.py              # 전체
    python Scripts/test_pipeline_sim.py --quick      # 파서 단위만 (빠름)
    python Scripts/test_pipeline_sim.py --only char_stress

정상 입력 하나가 통과하는지가 아니라, **이상한 입력이 들어왔을 때 사용자가
무엇을 보게 되는지**를 본다. 그래서 '예외 없이 끝남'을 합격으로 치지 않는다.
실패했는데 성공이라고 보고하면(SILENT) 예외로 죽는 것보다 나쁜 등급을 준다.
"""

import argparse
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from sim import fixtures as F                                    # noqa: E402
from sim import runner as R                                      # noqa: E402
from sim.runner import (CRITICAL, LOGIC_ISSUE, MINOR, PASS,      # noqa: E402
                        QUALITY_ISSUE, SILENT_FAILURE,
                        SYSTEM_ERROR, Result)


# ═══════════════════════════ 파서 단위 시뮬레이션

# (파일명, 바이트 생성기, 파서가 반드시 '실패'로 보고해야 하는가)
PARSER_CASES = [
    ('정상 xlsx',      '믹스.xlsx',  lambda: F.xlsx({'s': F.media_mix_rows()}), False),
    ('정상 docx',      '브리프.docx', lambda: F.docx(['목표', '타겟']),          False),
    ('정상 pptx',      '보고.pptx',  lambda: F.pptx([['제목']]),                False),
    ('0바이트 xlsx',   '빈.xlsx',    F.zero_bytes,                              True),
    ('0바이트 pptx',   '빈.pptx',    F.zero_bytes,                              True),
    ('0바이트 docx',   '빈.docx',    F.zero_bytes,                              True),
    ('0바이트 pdf',    '빈.pdf',     F.zero_bytes,                              True),
    ('잘린 xlsx',      '잘림.xlsx',  lambda: F.truncated(F.xlsx({'s': F.media_mix_rows()})), True),
    ('잘린 pptx',      '잘림.pptx',  lambda: F.truncated(F.pptx([['a']])),      True),
    ('내용위조 xlsx',  '위조.xlsx',  lambda: F.wrong_magic('xlsx'),             True),
    ('내용위조 pdf',   '위조.pdf',   lambda: F.wrong_magic('pdf'),              True),
    ('깨진 zip xlsx',  '깨짐.xlsx',  F.corrupt_zip,                             True),
    ('깨진 zip pptx',  '깨짐.pptx',  F.corrupt_zip,                             True),
    ('랜덤 바이트',    '랜덤.xlsx',  lambda: F.random_bytes(8192),              True),
    ('지원안함 확장자', '메모.txt',   lambda: b'hello',                          True),
]


def simulate_parsers() -> list:
    """파서가 실패를 '실패'라고 보고하는지 본다."""
    results = []
    for label, fname, make, must_fail in PARSER_CASES:
        r = Result(scenario=f'parser/{label}')
        t0 = time.time()
        try:
            with R.temp_campaign([(fname, make())], 'parser') as root:
                out = R.run_parser_only(root / fname)
        except Exception as e:
            r.fail(CRITICAL, f'파서가 예외를 그대로 던짐: {type(e).__name__}: {e}')
            r.seconds = time.time() - t0
            results.append(r)
            continue
        r.seconds = time.time() - t0

        status = out.get('status')
        err = (out.get('error_msg') or '').strip()
        tables = out.get('tables') or []
        text = out.get('text_content') or ''
        r.stats = {'status': status, 'tables': len(tables), 'text': len(text)}

        if must_fail:
            if status != 'error':
                # 핵심 검사: 못 읽었으면서 success 라고 하는가
                if err:
                    r.fail(SILENT_FAILURE,
                           f"실패했는데 status='{status}' — error_msg 는 있음: "
                           f'{err[:70]}')
                elif not tables and not text.strip():
                    r.fail(SILENT_FAILURE,
                           f"못 읽었는데 status='{status}' 이고 오류 메시지도 없음")
                else:
                    r.fail(LOGIC_ISSUE,
                           f"깨진 파일에서 내용이 나옴 (tables={len(tables)})")
        else:
            if status != 'success':
                r.fail(SYSTEM_ERROR, f'정상 파일이 실패로 처리됨: {err[:70]}')
            elif not tables and not text.strip():
                r.fail(LOGIC_ISSUE, '정상 파일인데 아무 내용도 못 뽑음')

        # 사용자에게 내부 경로가 노출되는가
        if err and ('\\' in err or '/' in err) and ('Users' in err or 'home' in err):
            r.fail(QUALITY_ISSUE, '오류 메시지에 서버 절대 경로가 들어 있음')

        results.append(r)
    return results


# ═══════════════════════════ 파이프라인 통합 시뮬레이션

# 시나리오별 기대 — (수치가 나와야 하는가)
EXPECT_NUMBERS = {
    'normal_full': True,
    'normal_minimal': True,
    'huge_sheet': True,
    'many_sheets': True,
    'char_stress': True,
    'adversarial_injection': True,
    'numeric_extremes': True,
    'duplicate_roles': True,
    'renamed_files': True,
    'weird_filenames': True,
    'header_only': False,
    'empty_folder': False,
    'only_images': False,
    'zero_byte_files': False,
    'truncated_files': False,
    'wrong_content_type': False,
    'corrupt_zip': False,
    'random_garbage': False,
    'empty_sheets': False,
}


def simulate_pipeline(only: str = '') -> list:
    results = []
    names = [n for n in F.all_scenarios() if not only or only == n]
    for name in names:
        r = Result(scenario=f'pipeline/{name}')
        t0 = time.time()
        try:
            fx = F.build(name)
        except Exception as e:
            r.fail(CRITICAL, f'픽스처 생성 실패: {type(e).__name__}: {e}')
            results.append(r)
            continue

        with R.temp_campaign(fx, name) as root:
            out = R.run_pipeline(root)
            r.seconds = time.time() - t0

            if out['error']:
                r.fail(CRITICAL, f'파이프라인이 죽음 — {out["error"]}')
                results.append(r)
                continue

            k, ds = out['knowledge'], out['dataset']
            s = ds.summary()
            docs = list(getattr(k, 'documents', []) or [])
            bad = [d for d in docs if getattr(d, 'status', '') == 'error']
            numbers = (s['plan_lines'] + s['daily_rows']
                       + s['media_performance'] + s['kpi_targets'])
            r.stats = {'docs': len(docs), 'failed': len(bad),
                       'numbers': numbers, 'mode': ds.mode,
                       'checklist': len(k.get_checklist_items())}

            # 1) 못 읽은 파일을 '못 읽었다'고 기록하는가
            if name in ('zero_byte_files', 'truncated_files',
                        'wrong_content_type', 'corrupt_zip', 'random_garbage'):
                if not bad:
                    r.fail(SILENT_FAILURE,
                           f'전부 깨진 파일인데 실패로 기록된 문서가 0건 '
                           f'(문서 {len(docs)}건 모두 정상 처리로 보고)')

            # 2) 수치 기대와 맞는가
            want = EXPECT_NUMBERS.get(name)
            if want is True and numbers == 0:
                r.fail(LOGIC_ISSUE, '정상 입력인데 수치를 하나도 못 뽑음')
            if want is False and numbers > 0:
                r.fail(LOGIC_ISSUE, f'빈/깨진 입력인데 수치가 나옴 ({numbers})')

            # 3) 느린가
            if r.seconds > R.SLOW_SECONDS:
                r.fail(QUALITY_ISSUE, f'처리에 {r.seconds:.1f}초 — 체감상 멈춤')

            # 4) 로그에 스택트레이스가 새는가
            if 'Traceback' in out['log']:
                r.fail(QUALITY_ISSUE, '엔진 로그에 스택트레이스가 찍힘')

            # 5) 인사이트·리포트까지 살아남는가
            if numbers > 0:
                ins = R.run_insights(k, ds)
                if ins['error']:
                    r.fail(CRITICAL, f'인사이트 단계에서 죽음 — {ins["error"]}')
                rep = R.run_report(k, ds)
                if rep['error']:
                    r.fail(CRITICAL, f'리포트 구성에서 죽음 — {rep["error"]}')
                elif rep.get('spec') is not None:
                    n_slides = len(getattr(rep['spec'], 'slides', []) or [])
                    r.stats['slides'] = n_slides
                    if n_slides == 0:
                        r.fail(LOGIC_ISSUE, '슬라이드가 0장 생성됨')

        results.append(r)
    return results


# ═══════════════════════════ 진입점

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--quick', action='store_true', help='파서 단위만')
    ap.add_argument('--only', default='', help='특정 파이프라인 시나리오만')
    args = ap.parse_args()

    started = time.time()
    results = simulate_parsers()
    if not args.quick:
        results += simulate_pipeline(args.only)

    print('\n' + '=' * 78)
    print('시뮬레이션 결과')
    print('=' * 78)
    print(R.render_table(results))

    counts = R.summarize(results)
    print('\n' + '-' * 78)
    total = len(results)
    parts = [f'{g} {counts[g]}' for g in R.SEVERITY_ORDER if counts[g]]
    print(f'전체 {total}건 · ' + ' · '.join(parts))
    print(f'소요 {time.time() - started:.1f}초')

    bad = total - counts[PASS] - counts[MINOR]
    print(f'조치 필요 {bad}건')
    return 1 if bad else 0


if __name__ == '__main__':
    raise SystemExit(main())
