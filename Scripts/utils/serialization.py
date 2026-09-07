# -*- coding: utf-8 -*-
"""
직렬화 안전장치

claude.md 4장 / Rule Book 4장:
- JSON에 NaN / Infinity 등 비표준 토큰을 남기지 말 것 (None으로 정규화)
- 절대경로를 데이터에 저장하지 말 것 (캠페인 폴더 기준 상대경로)
"""

import math
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any


def normalize_for_json(value: Any) -> Any:
    """
    JSON 표준을 따르도록 값을 재귀적으로 정규화합니다.

    처리 대상:
      - float('nan'), inf, -inf            -> None
      - numpy 정수/실수/불리언              -> 파이썬 기본형
      - pandas NaT / NA                     -> None
      - datetime, date, pandas Timestamp    -> ISO 문자열
      - dict 의 비문자열 키                  -> 문자열

    Args:
        value: 정규화할 값 (중첩 구조 허용)

    Returns:
        표준 JSON으로 직렬화 가능한 값
    """
    # None
    if value is None:
        return None

    # 문자열 (아래 시퀀스 분기보다 먼저 처리)
    if isinstance(value, str):
        return value

    # 불리언 (int 보다 먼저 처리해야 함)
    if isinstance(value, bool):
        return value

    # 실수: NaN / Infinity 제거
    if isinstance(value, float):
        return None if (math.isnan(value) or math.isinf(value)) else value

    if isinstance(value, int):
        return value

    # 날짜/시각
    if isinstance(value, (datetime, date)):
        return value.isoformat()

    # 매핑
    if isinstance(value, dict):
        normalized = {}
        for key, item in value.items():
            # JSON 객체의 키는 문자열이어야 함
            safe_key = key if isinstance(key, str) else str(key)
            normalized[safe_key] = normalize_for_json(item)
        return normalized

    # 시퀀스
    if isinstance(value, (list, tuple, set)):
        return [normalize_for_json(item) for item in value]

    # numpy / pandas 스칼라 (의존성 없이 덕 타이핑으로 처리)
    item_method = getattr(value, 'item', None)
    if callable(item_method):
        try:
            return normalize_for_json(item_method())
        except Exception:
            pass

    # pandas NaT 등 자기 자신과 같지 않은 결측 표현
    try:
        if value != value:
            return None
    except Exception:
        pass

    # 그 밖의 객체는 문자열로 보존 (정보 소실보다 낫다)
    return str(value)


def to_portable_path(abs_path: str, base_dir: str) -> str:
    """
    절대경로를 캠페인 폴더 기준 상대경로로 변환합니다.

    다른 AE의 PC에서도 열 수 있도록 이식성을 확보하기 위함.
    base_dir 밖의 경로는 파일명만 남깁니다.

    Args:
        abs_path: 원본 경로
        base_dir: 기준 폴더 (캠페인 폴더)

    Returns:
        상대경로 문자열 (POSIX 구분자)
    """
    if not abs_path:
        return ''
    if not base_dir:
        return Path(abs_path).name

    try:
        rel = Path(abs_path).resolve().relative_to(Path(base_dir).resolve())
        return rel.as_posix()
    except (ValueError, OSError):
        # 기준 폴더 밖이거나 경로 해석 실패 시 파일명만 보존
        return Path(abs_path).name


def from_portable_path(rel_path: str, base_dir: str) -> str:
    """
    상대경로를 현재 PC의 절대경로로 복원합니다.

    Args:
        rel_path: to_portable_path 가 만든 상대경로
        base_dir: 현재 PC의 캠페인 폴더 경로

    Returns:
        절대경로 문자열 (복원 불가 시 입력값 그대로)
    """
    if not rel_path:
        return ''
    if os.path.isabs(rel_path):
        return rel_path
    if not base_dir:
        return rel_path
    return str(Path(base_dir) / rel_path)
