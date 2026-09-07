# -*- coding: utf-8 -*-
"""
<일자별 통합> 시트의 매체별 블록을 읽는다.

실측 구조 — 매체별 표가 가로로 나열된 넓은 시트 (121~144열):

        [Media Total]                [유튜브]                    [META]
  r15                                유튜브                      META
  r16   일자|비고|청구|집행|노출|...   일자|청구|집행|노출|...     일자|청구|집행|노출|...
  r17   Total  503,524,999 ...        Total 240,555,000 ...      Total 129,999,999 ...
  r18   1일 평균 ...                   1일 평균 ...                1일 평균 ...
  r19   2025-06-30 ...                2025-06-30 ...              2025-06-30 ...

첫 블록(Media Total)만 읽고 나머지를 버리면 매체별 집계의 가장 정확한 원천을
잃는다. 매체 시트의 상품별 표는 소계 행이 섞여 합계가 어긋날 수 있으나,
이 블록의 Total 행은 매체 단위 확정 실적이므로 매체 간 비교의 기준으로 쓴다.

블록 경계는 헤더 행의 '일자' 컬럼 위치로 잡는다. 매체명 셀과 '일자' 셀의
열 정렬이 파일마다 1~2열 어긋나므로(AC: 명13/일자14, OLED: 명14/일자15),
매체명은 블록 범위 안에서 가장 왼쪽의 유효 셀로 찾는다.
"""

import re
from typing import Dict, List, Optional, Tuple

import pandas as pd

from models.campaign_data import (
    DailyRow, MediaPerformance, MetricSet, Provenance,
)
from . import sheet_utils as su


_METRIC_KEYS = ('billed', 'spend', 'impressions', 'views', 'clicks',
                'vtr', 'ctr', 'cpm', 'cpv', 'cpc')

# 캠페인 전체 합계 블록 — 매체별 목록에서는 제외 (result.total 로 이미 보유)
_TOTAL_BLOCK_RE = re.compile(r'media\s*total|전체|합계', re.IGNORECASE)


def _date_columns(df: pd.DataFrame, header: int) -> List[int]:
    """헤더 행에서 '일자' 컬럼 위치를 모두 찾는다 = 블록 시작점"""
    return [j for j, v in enumerate(df.iloc[header])
            if su.canonical_column(v) == 'date']


def _block_name(df: pd.DataFrame, name_row: int,
                start: int, end: int) -> str:
    """블록 범위에서 매체명을 찾는다 (일자 컬럼보다 앞에 놓이는 경우 포함)"""
    if name_row < 0:
        return ''
    for j in range(max(0, start - 2), min(end, df.shape[1])):
        s = su.norm(su.cell(df, name_row, j))
        if s:
            return s
    return ''


def _column_map_range(df: pd.DataFrame, header: int,
                      start: int, end: int) -> Dict[str, int]:
    """블록 열 범위 안에서만 정규 컬럼을 매핑한다"""
    mapping: Dict[str, int] = {}
    for j in range(start, min(end, df.shape[1])):
        canon = su.canonical_column(su.cell(df, header, j))
        if canon and canon not in mapping:
            mapping[canon] = j
    return mapping


def _read_metrics(df: pd.DataFrame, row: int, cols: Dict[str, int]) -> MetricSet:
    return MetricSet(**{
        k: su.to_number(su.cell(df, row, cols.get(k))) for k in _METRIC_KEYS
    })


def read_media_blocks(df: pd.DataFrame, header: int, *, sheet: str,
                      file_name: str) -> Tuple[List[MediaPerformance],
                                               Dict[str, List[DailyRow]]]:
    """
    매체별 블록의 Total 행과 일자별 행을 읽는다.

    Args:
        df: header=None 으로 읽은 <일자별 통합> 시트
        header: '일자' 헤더 행 인덱스
        sheet: 시트명 (출처 표기용)
        file_name: 파일명 (출처 표기용)

    Returns:
        (매체별 Total 목록, {매체명: 일자별 행 목록})
    """
    date_cols = _date_columns(df, header)
    if len(date_cols) < 2:                    # 매체별 블록이 없는 단일 표
        return [], {}

    totals: List[MediaPerformance] = []
    daily: Dict[str, List[DailyRow]] = {}
    name_row = header - 1

    for i, start in enumerate(date_cols):
        end = date_cols[i + 1] if i + 1 < len(date_cols) else df.shape[1]
        name = _block_name(df, name_row, start, end)
        if not name or _TOTAL_BLOCK_RE.search(name):
            continue

        cols = _column_map_range(df, header, start, end)
        if 'date' not in cols:
            continue

        rows: List[DailyRow] = []
        block_total: Optional[MetricSet] = None

        for row in range(header + 1, len(df)):
            label = su.norm(su.cell(df, row, cols['date']))
            metrics = _read_metrics(df, row, cols)

            if label.lower() == 'total':
                block_total = metrics
                continue
            if '평균' in label:
                continue

            date = su.parse_date(su.cell(df, row, cols['date']))
            if not date:
                continue
            rows.append(DailyRow(
                date=date,
                note=su.norm(su.cell(df, row, cols.get('note'))),
                metrics=metrics,
            ))

        if block_total is not None:
            totals.append(MediaPerformance(
                media=name,
                axis='media',
                section='일자별 통합 매체별 Total',
                period_raw='',
                budget=block_total.billed,
                metrics=block_total,
                source=Provenance(file_name=file_name, sheet_or_slide=sheet,
                                  locator=f'c{start + 1} Total'),
            ))
        if rows:
            daily[name] = rows

    return totals, daily
