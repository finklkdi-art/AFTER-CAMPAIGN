# -*- coding: utf-8 -*-
"""
집행 기간 교차검증 검사 — 그래프가 캠페인보다 길게 그려지지 않는가

    python Scripts/test_period_window.py

데일리리포트 파일은 캠페인이 끝난 뒤에도 행이 이어지는 경우가 있다.
0 으로 채운 꼬리, 다음 Phase, 다른 캠페인이 같은 시트에 붙어 온다.
행 수를 그대로 '캠페인 기간'으로 쓰면 보고서가 사실보다 길게 말한다 —
미디어믹스가 6/29~7/28 인데 '총 55일 · 8/22 까지'로 찍힌 제보가 그것이다.

DRM 때문에 실제 샘플을 못 읽는 날이 있어서, 문제의 모양만 그대로 옮긴
합성 데이터로 검사한다. 파서를 타지 않으므로 잠금과 무관하게 돌아간다.
"""

import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from models.campaign_data import (                       # noqa: E402
    CampaignDataset, DailyReportResult, DailyRow, MediaMixResult,
    MetricSet, PlanLine, PostbuyResult,
)
from models.campaign_knowledge import CampaignKnowledge  # noqa: E402
from utils.report.blocks import ReportSpecBuilder as B   # noqa: E402


def _knowledge():
    return CampaignKnowledge(campaign_id='test', campaign_name='테스트 캠페인')


def _rows(start: str, days: int, *, blank_from: int = -1):
    """start(YYYY-MM-DD) 부터 days 일치 행. blank_from 이후는 값 0."""
    d0 = date.fromisoformat(start)
    out = []
    for i in range(days):
        empty = 0 <= blank_from <= i
        out.append(DailyRow(
            date=(d0 + timedelta(days=i)).isoformat(),
            metrics=MetricSet(spend=0 if empty else 1_000_000 + i)))
    return out


def _dataset(*, mix_period='', mix_lines=(), pb_period='', rows=()):
    mm = MediaMixResult(period_raw=mix_period, source_file='미디어믹스.xlsx',
                        lines=[PlanLine(media=m, period_start=s, period_end=e)
                               for m, s, e in mix_lines])
    pb = (PostbuyResult(period_raw=pb_period) if pb_period else None)
    if pb is not None:
        pb.source_file = '포스트바이.pptx'
    dr = DailyReportResult(source_file='데일리리포트.xlsx', daily_rows=list(rows))
    return CampaignDataset(media_mix=mm, daily_report=dr, postbuy=pb)


def _chart(dataset):
    """(그린 일수, 첫날, 마지막날) — 슬라이드가 안 나오면 None"""
    sl = B._daily_trend(_knowledge(), dataset)
    if sl is None:
        return None
    cats = sl.payload['categories']
    return len(cats), cats[0], cats[-1]


CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


@case('기간 표기 분해 — 연도 붙은 형식이 월로 새지 않는가')
def _split_period_formats():
    """
    2026.09.09 회귀 방지.

    `2025-04-01~2025-04-30` 이 '25-04'/'25-01' 로 파싱돼 로드맵 슬라이드가
    `date(2000, 25, ...)` 에서 죽었다. MM-DD 규칙의 한두 자리 숫자 패턴이 연도 뒷자리를
    월로 물어서다. 월 유효성 검사도 없어 '25/06/26' 류도 같이 깨졌다.
    """
    from utils.parsers.sheet_utils import split_period as sp

    expect = [
        ('2025-04-01~2025-04-30', ('04-01', '04-30')),
        ('2025-04-01 ~ 2025-04-30', ('04-01', '04-30')),
        ('25/06/26 ~ 08/10', ('06-26', '08-10')),
        ('2025-04-01', ('04-01', '04-01')),
        # 기존 표기는 그대로 살아 있어야 한다
        ('4/18~4/30', ('04-18', '04-30')),
        ('04-21~05-20', ('04-21', '05-20')),
        ('6/1~30', ('06-01', '06-30')),
        ('8/8(금)', ('08-08', '08-08')),
        # 달력에 없는 값은 추측하지 않는다 (Rule Book 2.1)
        ('13/45~99/99', (None, None)),
        ('상시', (None, None)),
    ]
    for raw, want in expect:
        got = sp(raw)
        assert got == want, f'{raw!r} -> {got} (기대 {want})'

    # 파싱 결과는 반드시 달력에 있는 월이어야 한다 — 렌더가 date() 로 받는다
    for raw, _ in expect:
        for v in sp(raw):
            if v is not None:
                mm = int(v.split('-')[0])
                assert 1 <= mm <= 12, f'{raw!r} 에서 월 {mm} 이 나옴'


@case('제보 사례 — 믹스 6/29~7/28 · 행은 8/22 까지')
def _reported():
    ds = _dataset(mix_period='6/29 ~ 7/28', pb_period='25.06.29~07.28',
                  rows=_rows('2025-06-29', 55, blank_from=30))
    p = ds.campaign_period()
    assert p and (p.start, p.end) == ('06-29', '07-28'), p
    assert p.confidence == 'high', p.confidence
    assert _chart(ds) == (30, '06/29', '07/28'), _chart(ds)


@case('꼬리만 0 — 기간 표기가 없어도 빈 꼬리는 기간이 아니다')
def _blank_tail():
    ds = _dataset(rows=_rows('2025-06-29', 55, blank_from=30))
    assert ds.campaign_period() is None
    assert _chart(ds) == (30, '06/29', '07/28'), _chart(ds)


@case('정상 캠페인 — 아무것도 잘라내지 않는다')
def _clean():
    ds = _dataset(mix_period='6/26 ~ 8/10', rows=_rows('2025-06-26', 46))
    assert _chart(ds) == (46, '06/26', '08/10'), _chart(ds)


@case('믹스와 포스트바이가 어긋나면 합집합 · 저신뢰로 표시')
def _mismatch():
    ds = _dataset(mix_period='4/21 ~ 7/19', pb_period='25.04.27~07.26',
                  rows=_rows('2025-04-21', 98))
    p = ds.campaign_period()
    assert (p.start, p.end) == ('04-21', '07-26'), p
    assert p.confidence == 'low', p.confidence
    assert _chart(ds) == (97, '04/21', '07/26'), _chart(ds)


@case('계획 라인의 기간이 표기보다 우선')
def _plan_lines():
    ds = _dataset(mix_period='알 수 없음',
                  mix_lines=[('유튜브', '06-29', '07-20'),
                             ('메타', '07-01', '07-28')],
                  rows=_rows('2025-06-29', 55))
    p = ds.campaign_period()
    assert (p.start, p.end) == ('06-29', '07-28'), p
    assert _chart(ds) == (30, '06/29', '07/28'), _chart(ds)


@case('기간이 행과 전혀 겹치지 않으면 원본을 살린다')
def _no_overlap():
    ds = _dataset(mix_period='1/1 ~ 1/20', rows=_rows('2025-06-29', 30))
    assert _chart(ds) == (30, '06/29', '07/28'), _chart(ds)


@case('잘라낸 날은 Checklist 에 남는다')
def _checklist():
    k = _knowledge()
    ds = _dataset(mix_period='6/29 ~ 7/28',
                  rows=_rows('2025-06-29', 55, blank_from=30))
    B._daily_trend(k, ds)
    items = k.get_checklist_items()
    hits = [i for i in items if getattr(i, 'type', '') == 'daily_trend_period']
    assert len(hits) == 1, items
    assert '25일' in hits[0].message, hits[0].message


def main() -> int:
    bad = []
    for name, fn in CASES:
        try:
            fn()
            print(f'  통과   {name}')
        except AssertionError as e:
            bad.append(name)
            print(f'  실패   {name}\n         {e}')
        except Exception as e:
            bad.append(name)
            print(f'  오류   {name}\n         {type(e).__name__}: {e}')
    print()
    if bad:
        print(f'{len(bad)}건 실패 (검사 {len(CASES)}건)')
        return 1
    print(f'통과 — 집행 기간 교차검증 {len(CASES)}건')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
