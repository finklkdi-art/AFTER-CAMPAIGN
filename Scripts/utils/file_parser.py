# -*- coding: utf-8 -*-
"""
File Parser - Extract data from various file formats (XLSX, PDF, PPTX, DOCX)
"""

import os
import pandas as pd
import pdfplumber
from pptx import Presentation
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from .encoder import detect_encoding, safe_decode
from .errors import humanize_parse_error
import openpyxl


class FileParser:
    """다양한 파일 형식에서 데이터를 추출합니다"""

    def __init__(self):
        self.extracted_data = {}

    @staticmethod
    def parse_file(file_path: str) -> Dict[str, Any]:
        """
        파일을 파싱하여 데이터를 추출합니다.

        Args:
            file_path: 파일 경로

        Returns:
            {
                'status': 'success' | 'error',
                'file_type': 파일 확장자,
                'encoding': 감지된 인코딩,
                'file_path': 파일 경로,
                'file_name': 파일명,
                'text_content': 추출된 텍스트,
                'tables': 추출된 표들,
                'metadata': 파일 메타데이터,
                'error_msg': 에러 메시지 (있을 경우)
            }
        """
        result = {
            'status': 'success',
            'file_path': file_path,
            'file_name': os.path.basename(file_path),
            'file_type': Path(file_path).suffix.lower()[1:],  # 확장자만
            'text_content': '',
            'tables': [],
            'metadata': {},
            'error_msg': None,
            'encoding': 'utf-8'
        }

        # 사내 문서보안(DRM) 파일은 어떤 파서로도 열리지 않는다.
        # 확장자별 핸들러로 넘기면 "format cannot be determined" 같은
        # 기술 오류만 남아 AE 가 원인을 알 수 없으므로 먼저 걸러 안내한다.
        from utils.drm_check import detect_drm
        drm = detect_drm(file_path)
        if drm:
            result['status'] = 'error'
            result['error_msg'] = drm
            return FileParser._finalize(result)

        try:
            file_type = result['file_type']

            if file_type == 'xlsx':
                result.update(FileParser._parse_xlsx(file_path))
            elif file_type == 'pdf':
                result.update(FileParser._parse_pdf(file_path))
            elif file_type == 'pptx':
                result.update(FileParser._parse_pptx(file_path))
            elif file_type == 'docx':
                result.update(FileParser._parse_docx(file_path))
            else:
                result['status'] = 'error'
                result['error_msg'] = f'Unsupported file type: {file_type}'

        except Exception as e:
            result['status'] = 'error'
            result['error_msg'] = str(e)

        return FileParser._finalize(result)

    # ------------------------------------------------------------------

    @staticmethod
    def _finalize(result: Dict[str, Any]) -> Dict[str, Any]:
        """
        핸들러 결과를 최종 판정한다.

        🔴 여기가 없던 탓에 생긴 버그 — 확장자별 핸들러(_parse_xlsx 등)는
        예외를 잡아 `error_msg` 만 채우고 **`status` 는 건드리지 않았다.**
        `parse_file` 은 그 dict 를 update 만 하므로 status 는 초기값
        'success' 그대로 남았다. 결과적으로 0바이트 파일·잘린 파일·확장자만
        바꾼 파일이 전부 "정상 파싱됨(내용 없음)"으로 보고됐고, 상위 단계는
        문서를 성공으로 등록했다. 시뮬레이션 15건 중 11건이 이 경우였다.

        판정 규칙 — 내용을 건졌는지로 가른다 (claude.md 3.1 · 조용한 소실 금지).
          · 오류 + 내용 없음  → error   (진짜 실패)
          · 오류 + 내용 있음  → success + partial=True
            (PDF 5쪽 중 4쪽을 읽고 마지막에서 실패한 경우가 여기다.
             읽은 4쪽을 버리지 않고 살리되, 일부만 읽었다는 사실은 남긴다)
          · 오류 없음         → success
        """
        raw = (result.get('error_msg') or '').strip()
        has_content = bool(result.get('tables')) or bool(
            (result.get('text_content') or '').strip())

        if raw:
            message, detail = humanize_parse_error(
                raw, file_name=result.get('file_name', ''))
            result['error_msg'] = message      # 사용자에게 보이는 한 문장
            result['error_detail'] = detail    # 개발자용 기술 원문
            if has_content:
                result['status'] = 'success'
                result['partial'] = True
            else:
                result['status'] = 'error'
        else:
            result.setdefault('error_detail', '')
            result.setdefault('partial', False)

        return result

    # 시트 텍스트 상한.
    #
    # `df.astype(str).to_string()` 은 시트 전체를 문자열로 한 번 더 복제한다.
    # 이 텍스트를 쓰는 곳은 역할 추론(앞 3,000자)과 개요 추출(앞부분)뿐인데,
    # 상한이 없으면 큰 시트에서 수 MB 짜리 문자열이 만들어져 세션이 끝날 때까지
    # SourceDocument 에 남는다. 무료 호스팅(1GB)에서 동시 접속자가 몇 명만
    # 되어도 위험하다.
    #
    # 실측 기준으로 여유를 크게 잡았다 — 샘플 6개 캠페인의 최대 시트가
    # 262행 · 118,086자였으므로 아래 값은 3배 이상의 헤드룸이다.
    # 즉 실제 파일의 동작은 그대로 두고 최악의 경우만 막는다.
    _TEXT_ROW_BUDGET = 5000
    _TEXT_CHAR_BUDGET = 400_000

    @staticmethod
    def _sheet_text(df) -> str:
        """시트를 분류·개요용 텍스트로 — 행/글자 상한을 걸어 잘라 담는다."""
        head = df.head(FileParser._TEXT_ROW_BUDGET)
        try:
            text = head.astype(str).to_string()
        except Exception:
            # 이상한 dtype 이 섞여 변환이 실패해도 파싱 전체를 실패시키지 않는다.
            # 표 데이터(tables)는 이미 확보돼 있으므로 텍스트만 포기한다.
            return ''
        return text[:FileParser._TEXT_CHAR_BUDGET]

    @staticmethod
    def _parse_xlsx(file_path: str) -> Dict[str, Any]:
        """XLSX 파일 파싱"""
        encoding, _ = detect_encoding(file_path)
        result = {'encoding': encoding, 'tables': [], 'text_content': ''}

        try:
            # 🔴 워크북은 한 번만 연다.
            # 시트마다 pd.read_excel(경로) 를 부르면 워크북 전체가 매번 다시
            # 파싱되어 시트 N개짜리 파일이 N배 느려진다
            # (실측: 25시트 8.4MB 데일리리포트 90초 → 18초, 4.9배)
            excel_file = pd.ExcelFile(file_path)
            try:
                for sheet_name in excel_file.sheet_names:
                    df = excel_file.parse(sheet_name=sheet_name, header=None)
                    if df.empty:
                        continue
                    result['tables'].append({
                        'sheet_name': sheet_name,
                        'data': df.to_dict('records'),
                        'shape': df.shape
                    })

                    # 첫 번째 시트의 텍스트도 추출 (역할 추론·개요 추출용)
                    if not result['text_content']:
                        result['text_content'] = FileParser._sheet_text(df)
            finally:
                excel_file.close()   # 업로드본 삭제를 막지 않도록 핸들을 닫는다

        except Exception as e:
            result['error_msg'] = str(e)

        return result

    @staticmethod
    def _parse_pdf(file_path: str) -> Dict[str, Any]:
        """PDF 파일 파싱"""
        result = {'encoding': 'utf-8', 'tables': [], 'text_content': ''}

        try:
            with pdfplumber.open(file_path) as pdf:
                # 텍스트 추출
                for page in pdf.pages:
                    result['text_content'] += page.extract_text() or ''

                    # 표 추출
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            result['tables'].append({
                                'page': page.page_number,
                                'data': table,
                                'shape': (len(table), len(table[0]) if table else 0)
                            })

        except Exception as e:
            result['error_msg'] = str(e)

        return result

    @staticmethod
    def _parse_pptx(file_path: str) -> Dict[str, Any]:
        """PPTX 파일 파싱"""
        result = {'encoding': 'utf-8', 'tables': [], 'text_content': ''}

        try:
            prs = Presentation(file_path)

            for slide_idx, slide in enumerate(prs.slides):
                for shape in slide.shapes:
                    # 텍스트 추출
                    if hasattr(shape, 'text'):
                        result['text_content'] += shape.text + '\n'

                    # 표 추출
                    if shape.has_table:
                        table = shape.table
                        table_data = []
                        for row in table.rows:
                            row_data = []
                            for cell in row.cells:
                                row_data.append(cell.text)
                            table_data.append(row_data)

                        result['tables'].append({
                            'slide': slide_idx,
                            'data': table_data,
                            'shape': (len(table_data), len(table_data[0]) if table_data else 0)
                        })

        except Exception as e:
            result['error_msg'] = str(e)

        return result

    @staticmethod
    def _parse_docx(file_path: str) -> Dict[str, Any]:
        """DOCX 파일 파싱"""
        result = {'encoding': 'utf-8', 'tables': [], 'text_content': ''}

        try:
            from docx import Document

            doc = Document(file_path)

            # 텍스트 추출
            for para in doc.paragraphs:
                result['text_content'] += para.text + '\n'

            # 표 추출
            for table in doc.tables:
                table_data = []
                for row in table.rows:
                    row_data = []
                    for cell in row.cells:
                        row_data.append(cell.text)
                    table_data.append(row_data)

                result['tables'].append({
                    'data': table_data,
                    'shape': (len(table_data), len(table_data[0]) if table_data else 0)
                })

        except ImportError:
            result['error_msg'] = 'python-docx not installed'
        except Exception as e:
            result['error_msg'] = str(e)

        return result

    @staticmethod
    def extract_structured_data(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        파싱된 데이터에서 구조화된 정보(KPI, 예산, 기간 등)를 추출합니다.

        Args:
            parsed_data: parse_file() 반환값

        Returns:
            구조화된 데이터 딕셔너리
        """
        result = {
            'kpi_candidates': [],
            'budget_candidates': [],
            'period_candidates': [],
            'strategy_keywords': [],
            'tables_summary': []
        }

        # 표에서 KPI 추출
        for table in parsed_data.get('tables', []):
            table_data = table.get('data', [])
            if table_data:
                result['tables_summary'].append({
                    'shape': table.get('shape'),
                    'preview': str(table_data[:2]) if table_data else ''
                })

                # 간단한 KPI 후보 추출 (숫자 포함 행 찾기)
                for row in table_data:
                    row_str = str(row).lower()
                    if any(kw in row_str for kw in ['노출', 'click', 'ctr', '클릭', 'kpi', '성과', '달성', '목표']):
                        result['kpi_candidates'].append(row)

        # 텍스트에서 키워드 추출
        text = parsed_data.get('text_content', '').lower()
        if '예산' in text or 'budget' in text:
            result['budget_candidates'].append('예산 정보 포함')
        if '기간' in text or '~' in text:
            result['period_candidates'].append('기간 정보 포함')

        return result
