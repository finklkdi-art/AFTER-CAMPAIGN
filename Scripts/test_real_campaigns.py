# -*- coding: utf-8 -*-
"""
실제 캠페인 회귀 테스트 — 골든 베이스라인 대조

    python Scripts/test_real_campaigns.py            # 베이스라인과 대조
    python Scripts/test_real_campaigns.py --record   # 현재 결과를 베이스라인으로 기록

`Input/Samples/` 의 실제 캠페인을 파이프라인에 태우고, 뽑아낸 수치가 이전과
같은지 본다. 합성 픽스처가 잡지 못하는 회귀 — 파서가 실제 엑셀의 병합셀·다중
헤더·시트 이름 변형을 여전히 읽어 내는지 — 를 여기서 잡는다.

⚠️ 사내 문서보안(DRM) 주의
  NASCA 는 보안 에이전트가 활성일 때만 읽기 시점에 복호화해 준다. 에이전트가
  잠겨 있으면 **같은 파일이 암호문으로 읽혀** 전부 파싱 실패가 된다. 그건 코드
  회귀가 아니므로, 그 상태면 실패로 처리하지 않고 SKIP 한다.
  (실측 2026-09-08: 동일 파일이 오전 전부 DRM → 오후 전부 정상)
"""

import argparse
import contextlib
import io
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

BASELINE = HERE / 'baseline_real_campaigns.json'
SAMPLES = ROOT / 'Input' / 'Samples'

# 이 숫자들이 리포트 내용을 좌우한다. 줄어들면 회귀다.
METRICS = ('plan_lines', 'daily_rows', 'media_performance', 'kpi_targets')

# 매체비 총합은 보고서에서 가장 많이 인용되는 값이라 따로 고정한다.
# 값이 바뀌면(특히 사라지면) 즉시 회귀로 잡아야 한다.
SPEND_KEYS = ('media_spend', 'media_spend_verified')


def measure(folder: Path) -> dict:
    from utils.capture import capture_output
    from data_scanning import run_step1
    from utils.dataset_builder import CampaignDatasetBuilder
    from utils.checklist_manager import ChecklistManager

    log = io.StringIO()
    t0 = time.time()
    with capture_output(log):
        knowledge = run_step1(str(folder))
        dataset = CampaignDatasetBuilder.build(knowledge)
        ChecklistManager.deduplicate_checklist(knowledge)

    s = dataset.summary()
    docs = list(getattr(knowledge, 'documents', []) or [])
    failed = [d for d in docs if getattr(d, 'status', '') == 'error']
    drm = sum(1 for d in failed
              if '문서보안' in (getattr(d, 'error_msg', '') or ''))
    spend = dataset.media_spend()
    return {
        'media_spend': round(spend.total) if spend else None,
        'media_spend_verified': bool(spend and spend.is_verified()) if spend else False,
        'media_spend_source': (spend.source_label if spend else ''),
        'docs': len(docs),
        'failed': len(failed),
        'drm_locked': drm,
        'mode': dataset.mode,
        'seconds': round(time.time() - t0, 1),
        **{m: s[m] for m in METRICS},
    }


def run_all() -> dict:
    out = {}
    if not SAMPLES.is_dir():
        return out
    for d in sorted(SAMPLES.iterdir()):
        if not d.is_dir() or d.name.startswith(('_', '.')):
            continue
        try:
            out[d.name] = measure(d)
        except Exception as e:
            out[d.name] = {'error': f'{type(e).__name__}: {e}'}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--record', action='store_true',
                    help='현재 결과를 베이스라인으로 저장')
    args = ap.parse_args()

    if not SAMPLES.is_dir():
        print('SKIP — Input/Samples 가 없어요 (배포 환경에서는 정상)')
        return 0

    current = run_all()
    if not current:
        print('SKIP — 캠페인 폴더가 없어요')
        return 0

    if args.record:
        BASELINE.write_text(
            json.dumps(current, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8')
        print(f'베이스라인 기록: {BASELINE.name} ({len(current)}개 캠페인)')
        for name, m in current.items():
            print(f'  {name[:40]:42} ' + ' '.join(
                f'{k}={m.get(k)}' for k in METRICS))
        return 0

    if not BASELINE.is_file():
        print('베이스라인이 없어요. 먼저 --record 로 기록해 주세요.')
        return 1

    base = json.loads(BASELINE.read_text(encoding='utf-8'))
    problems, skipped = [], []

    for name, want in base.items():
        got = current.get(name)
        if got is None:
            problems.append(f'{name} — 폴더가 사라졌어요')
            continue
        if got.get('error'):
            problems.append(f'{name} — 파이프라인 예외: {got["error"]}')
            continue

        # DRM 잠금은 환경 상태지 코드 회귀가 아니다
        if got['drm_locked'] and not want.get('drm_locked'):
            skipped.append(f'{name} — 문서보안 잠김({got["drm_locked"]}건), 비교 생략')
            continue

        for m in METRICS:
            if got[m] < want[m]:
                problems.append(
                    f'{name} — {m} 감소: {want[m]} → {got[m]}')
        # 매체비 총합 — 사라지거나 값이 달라지면 회귀
        if want.get('media_spend') is not None:
            if got.get('media_spend') is None:
                problems.append(f'{name} — 매체비 총합을 못 읽게 됨 '
                                f'({want["media_spend"]:,} → None)')
            elif got['media_spend'] != want['media_spend']:
                problems.append(
                    f'{name} — 매체비 총합 변경: {want["media_spend"]:,} '
                    f'→ {got["media_spend"]:,}')
        if got['mode'] != want['mode']:
            problems.append(
                f'{name} — 구성 모드 변경: {want["mode"]} → {got["mode"]}')

    print('=' * 72)
    print(f'실제 캠페인 회귀 — 기준 {len(base)}개 / 측정 {len(current)}개')
    print('=' * 72)
    for name, m in current.items():
        if m.get('error'):
            print(f'  ERROR  {name[:40]:42} {m["error"][:40]}')
            continue
        flag = 'DRM' if m['drm_locked'] else '   '
        spend = (f'{m["media_spend"]:,}' if m.get('media_spend') else '—')
        mark = '✓' if m.get('media_spend_verified') else ' '
        print(f'  {flag}    {name[:34]:36} '
              + ' '.join(f'{k[:5]}={m[k]:<5}' for k in METRICS)
              + f' | 매체비 {spend:>15}{mark} {m["mode"]:>5}')

    for s in skipped:
        print(f'\nSKIP  {s}')
    if problems:
        print(f'\n회귀 {len(problems)}건')
        for p in problems:
            print(f'  - {p}')
        return 1
    print('\n회귀 없음')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
