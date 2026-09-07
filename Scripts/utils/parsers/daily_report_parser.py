# -*- coding: utf-8 -*-
"""
DailyReportParser — 데일리리포트에서 실적축을 추출

산출:
  - Total / 1일 평균 (Campaign Summary 원천)
  - 일자별 행 + 비고 (Scheduling 차트와 이벤트 주석 원천)
  - 매체별 상품/타겟팅 실적 (매체별 성과표 원천)

포스트바이가 없는 캠페인에서도 정량 블록을 만들 수 있게 하는 핵심 파서.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from models.campaign_data import (
    DailyReportResult, DailyRow, MediaPerformance, MetricSet,
    Provenance, ScheduleEvent,
)
from . import sheet_utils as su
from .integrated_blocks import read_media_blocks
from .section_tables import read_section_tables


# 일자별 통합 시트 탐색 패턴
_INTEGRATED_PATTERNS = (r'일자별\s*통합', r'일자별', r'daily', r'summary')

# 매체별 시트에서 제외할 이름 (통합/요약/비율 등)
_SKIP_SHEET_RE = r'일자별|summary|비율|media\s*mix|mix'

_METRIC_KEYS = ('billed', 'spend', 'impressions', 'views', 'clicks',
                'vtr', 'ctr', 'cpm', 'cpv', 'cpc')


class DailyReportParser:
    """데일리리포트 엑셀에서 실적 데이터를 추출합니다"""

    @staticmethod
    def parse(file_path: str) -> DailyReportResult:
        """
        Args:
            file_path: 데일리리포트 xlsx 경로

        Returns:
            DailyReportResult (실패해도 예외 없이 warnings 에 기록)
        """
        path = Path(file_path)
        result = DailyReportResult(source_file=path.name)

        try:
            xl = pd.ExcelFile(path)
        except Exception as e:
            from utils.drm_check import detect_drm
            result.warnings.append(detect_drm(str(path))
                                   or f'파일을 열 수 없음: {e}')
            return result

        try:
            DailyReportParser._parse_overview(xl, path, xl.sheet_names, result)
            DailyReportParser._parse_integrated(xl, path, xl.sheet_names, result)
            DailyReportParser._parse_media_sheets(xl, path, xl.sheet_names, result)
        finally:
            xl.close()          # 업로드본 삭제를 막지 않도록 핸들을 닫는다
        return result

    # ---------------- Summary 시트 (캠페인/기간/예산) ----------------

    @staticmethod
    def _parse_overview(xl: pd.ExcelFile, path: Path, sheet_names: List[str],
                        result: DailyReportResult) -> None:
        """
        캠페인명·기간·예산은 Summary 시트 상단에 안내 문구로 들어있다.
        (예: "Period: 2025/04/21 ~ 2025/07/18", "Budget : 395,170,000원")
        """
        sheet = su.find_sheet(sheet_names, (r'^summary$', r'summary', r'개요'))
        if sheet is None:
            return
        try:
            df = su.read_sheet(xl, sheet, header=None, nrows=20)
        except Exception:
            return

        for i in range(len(df)):
            for j in range(min(6, df.shape[1])):
                s = su.norm(su.cell(df, i, j))
                if not s or ':' not in s:
                    continue
                key, _, value = s.partition(':')
                key, value = key.strip().lower(), value.strip()
                if not value:
                    value = su.norm(su.scan_right(df, i, j))
                if key.startswith('period') and not result.period_raw:
                    result.period_raw = value
                elif key.startswith('budget') and result.budget_raw is None:
                    result.budget_raw = su.to_number(value)
                elif key.startswith(('product/campaign', 'campaign')) and not result.campaign:
                    result.campaign = value

    # ---------------- 일자별 통합 ----------------

    @staticmethod
    def _parse_integrated(xl: pd.ExcelFile, path: Path, sheet_names: List[str],
                          result: DailyReportResult) -> None:
        sheet = su.find_sheet(sheet_names, _INTEGRATED_PATTERNS)
        if sheet is None:
            result.warnings.append('일자별 통합 시트를 찾지 못함')
            return

        try:
            df = su.read_sheet(xl, sheet, header=None)
        except Exception as e:
            result.warnings.append(f'시트 읽기 실패 [{sheet}]: {e}')
            return

        header = su.find_header_row(df, required=('date', 'impressions'))
        if header is None:
            result.warnings.append(f'[{sheet}] 일자 헤더를 찾지 못함')
            return

        cols = su.column_map(df, header)

        # 헤더 바로 위 행에 매체명이 나열되어 있다 (Media Total | 유튜브 | 메타 ...)
        if header > 0:
            names = [su.norm(v) for v in df.iloc[header - 1]]
            result.media_names = [n for n in names if n and n.lower() != 'nan']

        # 캠페인/기간/예산은 상단 안내 영역에 있다
        DailyReportParser._read_header_meta(df, header, result)

        # 매체별 블록 — 매체 간 비교의 기준 원천 (매체 시트는 소계 혼입 위험)
        try:
            totals, daily = read_media_blocks(
                df, header, sheet=sheet, file_name=path.name)
            result.media_totals.extend(totals)
            result.media_daily.update(daily)
        except Exception as e:                      # 파싱 실패로 중단하지 않음
            result.warnings.append(f'[{sheet}] 매체별 블록 파싱 실패: {e}')
        if not result.media_totals:
            result.warnings.append(
                f'[{sheet}] 매체별 블록을 찾지 못함 — 매체 간 비교 원천 미확보')

        # Total / 1일 평균 / 일자별 행
        for row in range(header + 1, len(df)):
            first = su.norm(su.cell(df, row, cols.get('date')))
            metrics = DailyReportParser._read_metrics(df, row, cols)

            if first.lower() == 'total':
                result.total = metrics
                continue
            if '평균' in first:
                result.daily_average = metrics
                continue

            date = su.parse_date(su.cell(df, row, cols.get('date')))
            if not date:
                continue
            note = su.norm(su.cell(df, row, cols.get('note')))
            result.daily_rows.append(DailyRow(date=date, note=note, metrics=metrics))
            if note:
                result.events.append(ScheduleEvent(
                    date=date, note=note,
                    source=Provenance(file_name=path.name, sheet_or_slide=sheet,
                                      locator=f'r{row}'),
                ))

        if not result.daily_rows:
            result.warnings.append(f'[{sheet}] 일자별 데이터를 찾지 못함')

    @staticmethod
    def _read_header_meta(df: pd.DataFrame, header: int,
                          result: DailyReportResult) -> None:
        """상단 안내 영역에서 캠페인/기간/예산 문구를 찾는다"""
        for i in range(min(header, 16)):
            for j in range(min(6, df.shape[1])):
                s = su.norm(su.cell(df, i, j))
                if not s:
                    continue
                low = s.lower()
                if low.startswith('period'):
                    result.period_raw = s.split(':', 1)[-1].strip()
                elif low.startswith('budget'):
                    result.budget_raw = su.to_number(s.split(':', 1)[-1])
                elif low.startswith(('product/campaign', 'campaign')):
                    result.campaign = s.split(':', 1)[-1].strip()

    @staticmethod
    def _read_metrics(df: pd.DataFrame, row: int, cols: Dict[str, int]) -> MetricSet:
        return MetricSet(**{
            k: su.to_number(su.cell(df, row, cols.get(k))) for k in _METRIC_KEYS
        })

    # ---------------- 매체별 시트 ----------------

    @staticmethod
    def _parse_media_sheets(xl: pd.ExcelFile, path: Path, sheet_names: List[str],
                            result: DailyReportResult) -> None:
        import re
        skip = re.compile(_SKIP_SHEET_RE, re.IGNORECASE)

        for sn in sheet_names:
            if skip.search(sn):
                continue
            try:
                df = su.read_sheet(xl, sn, header=None)
            except Exception:
                continue
            if df.empty:
                continue

            media, budget, period = DailyReportParser._read_media_meta(df)
            date_header = su.find_header_row(df, required=('date', 'impressions'))

            # ■ 라벨로 구분된 표(상품별/타겟팅별/소재별)를 표 단위로 읽는다.
            # 표를 구분하지 않으면 서로 다른 축의 행과 소계가 뒤섞인다.
            try:
                sections = read_section_tables(
                    df, media=media, sheet=sn, file_name=path.name,
                    budget=budget, period=period, stop_row=date_header)
            except Exception as e:
                sections = []
                result.warnings.append(f'[{sn}] 섹션 표 파싱 실패: {e}')
            if sections:
                result.media_performance.extend(sections)
                continue

            # ■ 라벨이 없는 시트 — 단일 상품별 표로 간주 (구버전 경로)
            prod_header = DailyReportParser._find_product_header(df)
            if prod_header is None:
                continue
            end = date_header if (date_header and date_header > prod_header) else len(df)

            cols = su.column_map(df, prod_header)
            dim_cols = DailyReportParser._dimension_columns(cols)

            body = range(prod_header + 1, end)
            filled = {j: su.forward_fill([su.cell(df, i, j) for i in body])
                      for j in dim_cols}

            for offset, row in enumerate(body):
                dims = [filled[j][offset] for j in dim_cols]
                if su.is_total_row(*dims) or su.row_is_total(df, row):
                    continue
                metrics = DailyReportParser._read_metrics(df, row, cols)
                if all(getattr(metrics, k) in (None, 0) for k in
                       ('impressions', 'clicks', 'views', 'spend')):
                    continue
                result.media_performance.append(MediaPerformance(
                    media=media or sn,
                    product=dims[0] if dims else '',
                    targeting=dims[1] if len(dims) > 1 else '',
                    period_raw=period,
                    budget=budget,
                    metrics=metrics,
                    source=Provenance(file_name=path.name, sheet_or_slide=sn,
                                      locator=f'r{row}'),
                ))

    @staticmethod
    def _read_media_meta(df: pd.DataFrame) -> Tuple[str, Optional[float], str]:
        """시트 상단의 Media / Budget / Period 라벨을 읽는다"""
        media, budget, period = '', None, ''
        for i in range(min(12, len(df))):
            for j in range(min(3, df.shape[1])):
                label = su.norm(su.cell(df, i, j)).lower()
                value = su.cell(df, i, j + 1)
                if label == 'media' and not media:
                    media = su.norm(value)
                elif label == 'budget' and budget is None:
                    budget = su.to_number(value)
                elif label == 'period' and not period:
                    period = su.norm(value)
        return media, budget, period

    @staticmethod
    def _find_product_header(df: pd.DataFrame, limit: int = 45) -> Optional[int]:
        """상품별 효율 표의 헤더 (노출+클릭 있고 일자 없음)"""
        for i in range(min(limit, len(df))):
            found = {su.canonical_column(v) for v in df.iloc[i]}
            found.discard(None)
            if {'impressions', 'clicks'} <= found and 'date' not in found:
                return i
        return None

    @staticmethod
    def _dimension_columns(cols: Dict[str, int]) -> List[int]:
        """
        지표 컬럼보다 앞에 있는 열 = 상품/타겟팅 등 분류 축.
        최대 2개까지 사용한다.
        """
        metric_positions = [cols[k] for k in _METRIC_KEYS if k in cols]
        if not metric_positions:
            return []
        first_metric = min(metric_positions)
        return list(range(0, min(first_metric, 2)))
