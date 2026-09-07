# -*- coding: utf-8 -*-
"""
Encoding detection and conversion utilities
"""

import chardet
from pathlib import Path
from typing import Tuple, Optional


def detect_encoding(file_path: str) -> Tuple[str, float]:
    """
    파일의 인코딩을 자동으로 감지합니다.

    Args:
        file_path: 파일 경로

    Returns:
        (인코딩명, 신뢰도) 튜플
        예: ('utf-8', 0.99), ('euc-kr', 0.95)
    """
    try:
        with open(file_path, 'rb') as f:
            raw_data = f.read()

        detected = chardet.detect(raw_data)
        encoding = detected.get('encoding', 'utf-8') or 'utf-8'
        confidence = detected.get('confidence', 0.0)

        return encoding.lower(), confidence
    except Exception as e:
        return 'utf-8', 0.0


def convert_to_utf8(file_path: str, source_encoding: Optional[str] = None) -> str:
    """
    파일을 UTF-8로 변환합니다.

    Args:
        file_path: 원본 파일 경로
        source_encoding: 원본 인코딩 (None이면 자동 감지)

    Returns:
        성공/실패 메시지
    """
    try:
        if source_encoding is None:
            source_encoding, _ = detect_encoding(file_path)

        if source_encoding.lower() == 'utf-8':
            return "already_utf8"

        # 파일 읽기
        with open(file_path, 'r', encoding=source_encoding, errors='ignore') as f:
            content = f.read()

        # UTF-8로 쓰기
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return "converted"
    except Exception as e:
        return f"failed: {str(e)}"


def safe_decode(data: bytes, encoding: Optional[str] = None) -> str:
    """
    안전하게 바이트를 문자열로 디코딩합니다.

    Args:
        data: 바이트 데이터
        encoding: 인코딩 (None이면 자동 감지)

    Returns:
        디코딩된 문자열
    """
    if encoding is None:
        detected = chardet.detect(data)
        encoding = detected.get('encoding', 'utf-8') or 'utf-8'

    try:
        return data.decode(encoding.lower(), errors='ignore')
    except:
        return data.decode('utf-8', errors='ignore')
