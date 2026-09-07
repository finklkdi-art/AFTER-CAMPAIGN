# -*- coding: utf-8 -*-
"""
MediaMixParser — 미디어믹스에서 계획축을 추출

산출: 매체 × 상품 × 기간 × 소재 × 타겟팅 × 예산 × 예상성과
      → 집행 로드맵(B05)과 KPI 목표(제안 기준)의 원천

주의: 미디어믹스의 '예상 성과'는 제안 시점 값으로, 부킹 후 확정된
      포스트바이 KPI 목표와 다를 수 있다(실측 확인됨).
      확정 목표로 단정하지 말 것.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from models.campaign_data import MediaMixResult, PlanLine, Provenance
from . import sheet_utils as su


# 미디어믹스 시트 탐색 패턴 (앞선 것 우선)
_SHEET_PATTERNS = (r'media[\s_-]*mix', r'미디어[\s_-]*믹스', r'^mix$')

# 상단 메타데이터 라벨 — 국문·영문 표기를 함께 받는다.
# 실측: 데일리리포트는 'Period:' / 'Budget :' 처럼 영문 라벨을 쓰고,
# 미디어믹스도 파일에 따라 'Advertiser' / 'Product/Campaign' 표기가 섞인다.
_META_LABELS = {
    'advertiser': ('광고주', 'advertiser', 'client', '클라이언트'),
    'campaign': ('캠페인', 'campaign', 'product/campaign', '캠페인명', '제품'),
    'budget': ('예산', 'budget', '총예산', '총 예산'),
    'period': ('기간', 'period', '집행기간', '집행 기간', '일정'),
}


class MediaMixParser:
    """미디어믹스 엑셀에서 집행 계획 라인을 추출합니다"""

    @staticmethod
    def parse(file_path: str) -> MediaMixResult:
        """
        Args:
            file_path: 미디어믹스 xlsx 경로

        Returns:
            MediaMixResult (실패해도 예외를 던지지 않고 warnings 에 기록)
        """
        path = Path(file_path)
        result = MediaMixResult(source_file=path.name)

        try:
            xl = pd.ExcelFile(path)
        except Exception as e:
            from utils.drm_check import detect_drm
            result.warnings.append(detect_drm(str(path))
                                   or f'파일을 열 수 없음: {e}')
            return result

        try:
            MediaMixParser._parse_book(xl, path, result)
        finally:
            xl.close()          # 업로드본 삭제를 막지 않도록 핸들을 닫는다
        return result

    @staticmethod
    def _parse_book(xl: pd.ExcelFile, path: Path,
                    result: MediaMixResult) -> None:
        """열린 워크북에서 집행 계획을 읽는다 (핸들 수명은 parse 가 관리)"""
        sheet = su.find_sheet(xl.sheet_names, _SHEET_PATTERNS)
        if sheet is None:
            # 시트명이 달라도 내용으로 한 번 더 탐색
            sheet = MediaMixParser._find_by_content(xl, xl.sheet_names)
        if sheet is None:
            result.warnings.append(
                f'Media Mix 시트를 찾지 못함 (시트: {", ".join(xl.sheet_names[:8])})')
            return

        try:
            df = su.read_sheet(xl, sheet, header=None)
        except Exception as e:
            result.warnings.append(f'시트 읽기 실패 [{sheet}]: {e}')
            return

        header = su.find_header_row(df, required=('media', 'product'))
        if header is None:
            result.warnings.append(f'[{sheet}] 집행 계획 헤더(Media/Product)를 찾지 못함')
            return

        # 메타데이터는 반드시 헤더 위쪽에서만 찾는다
        # (헤더 행의 '캠페인 | 월별 | 구분' 같은 그룹 라벨을 메타로 오인하지 않도록)
        MediaMixParser._read_metadata(df, header, result)

        cols = su.column_map(df, header)
        result.lines = MediaMixParser._read_lines(df, header, cols, path.name, sheet)

        if not result.lines:
            result.warnings.append(f'[{sheet}] 유효한 집행 계획 라인이 없음')
        if 'period' not in cols:
            result.warnings.append(
                f'[{sheet}] 기간 컬럼이 없어 로드맵 시간축을 만들 수 없음 — 검증 화면에서 입력 필요')

        return

    # ------------------------------------------------------------------

    @staticmethod
    def _find_by_content(xl: pd.ExcelFile, sheet_names: List[str]) -> Optional[str]:
        """시트명으로 못 찾았을 때 내용(Media/Product 헤더)으로 탐색"""
        for sn in sheet_names:
            try:
                head = su.read_sheet(xl, sn, header=None, nrows=45)
            except Exception:
                continue
            if su.find_header_row(head, required=('media', 'product')) is not None:
                return sn
        return None

    @staticmethod
    def _read_metadata(df: pd.DataFrame, header: int, result: MediaMixResult) -> None:
        """
        헤더 위쪽의 광고주/캠페인/예산/기간 블록을 읽는다.

        병합셀 때문에 라벨 바로 옆 칸이 비어 있는 경우가 많아 오른쪽으로 훑는다.
        """
        for i in range(min(header, 10)):
            for j in range(min(4, df.shape[1])):
                raw = su.norm(su.cell(df, i, j))
                if not raw:
                    continue
                # 'Budget : 300,000,000원' 처럼 한 셀에 라벨과 값이 함께 오는
                # 표기도 있어 콜론을 기준으로 나눈 뒤 오른쪽 칸을 훑는다
                head, _, inline = raw.partition(':')
                label = su.norm_key(head)
                value = su.norm(inline) or su.scan_right(df, i, j)
                if not label:
                    continue
                if label in _META_LABELS['advertiser'] and not result.advertiser:
                    result.advertiser = su.norm(value)
                elif label in _META_LABELS['campaign'] and not result.campaign:
                    result.campaign = su.norm(value)
                elif label in _META_LABELS['budget'] and result.total_budget is None:
                    result.total_budget = su.to_number(value)
                elif label in _META_LABELS['period'] and not result.period_raw:
                    result.period_raw = su.norm(value)

    @staticmethod
    def _read_lines(df: pd.DataFrame, header: int, cols: Dict[str, int],
                    file_name: str, sheet: str) -> List[PlanLine]:
        """헤더 아래 데이터 행을 PlanLine 으로 변환"""
        # 병합셀 보정: 상위 분류 컬럼은 아래로 채워 내려간다.
        # 단, 소계 행의 라벨("유튜브 Sub Total")이 아래로 전파되면 안 되므로 미리 비운다.
        fill_targets = [c for c in ('media', 'product', 'category', 'purpose')
                        if c in cols]
        body = list(range(header + 1, len(df)))
        totals = {i for i in body if su.row_is_total(df, i)}
        filled: Dict[str, List[str]] = {}
        for c in fill_targets:
            raw = [None if i in totals else su.cell(df, i, cols[c]) for i in body]
            filled[c] = su.forward_fill(raw)

        lines: List[PlanLine] = []
        for offset, row in enumerate(body):
            # 소계/합계 행 제외 — 라벨이 놓이는 열이 파일마다 달라 행 전체를 검사한다
            if su.row_is_total(df, row):
                continue

            def val(key: str) -> str:
                if key in filled:
                    return filled[key][offset]
                return su.norm(su.cell(df, row, cols.get(key)))

            media = val('media')
            product = val('product')
            creative = su.norm(su.cell(df, row, cols.get('creative')))
            period_raw = su.norm(su.cell(df, row, cols.get('period')))
            budget = su.to_number(su.cell(df, row, cols.get('budget')))
            imps = su.to_number(su.cell(df, row, cols.get('exp_imps')))
            clicks = su.to_number(su.cell(df, row, cols.get('exp_clicks')))
            views = su.to_number(su.cell(df, row, cols.get('exp_views')))

            # 내용이 전혀 없는 행은 건너뛴다
            if not any([media, product, creative, period_raw, budget, imps, clicks, views]):
                continue
            # 매체도 상품도 없으면 계획 라인으로 보지 않는다
            if not media and not product:
                continue

            start, end = su.split_period(period_raw)
            lines.append(PlanLine(
                media=media,
                product=product,
                category=val('category'),
                purpose=val('purpose'),
                period_raw=period_raw,
                period_start=start,
                period_end=end,
                creative=creative.replace('\n', ' '),
                device=su.norm(su.cell(df, row, cols.get('device'))),
                targeting=su.norm(su.cell(df, row, cols.get('targeting'))).replace('\n', ' '),
                budget=budget,
                expected_impressions=imps,
                expected_clicks=clicks,
                expected_views=views,
                source=Provenance(file_name=file_name, sheet_or_slide=sheet,
                                  locator=f'r{row}'),
            ))
        return lines
