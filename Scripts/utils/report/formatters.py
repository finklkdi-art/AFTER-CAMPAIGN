# -*- coding: utf-8 -*-
"""
숫자·기간 표기 유틸 — tone-guide.md 3장 '숫자 표기 규칙' 구현

- 금액: 억 단위 한글 혼용 ("6.74억"), 표 안은 원 단위 콤마
- 횟수: 만/억 혼용 ("8억 2,726만회", "778만회"), 표 안은 콤마 원값
- 달성율: "123%"
"""

from typing import Any, Optional


def comma(value: Optional[float]) -> str:
    """표 안 숫자: 천단위 콤마, 정수 표기. None/0 구분 유지."""
    if value is None:
        return '-'
    try:
        return f'{float(value):,.0f}'
    except (TypeError, ValueError):
        return str(value)


def krw_eok(value: Optional[float], digits: int = 2) -> str:
    """금액을 억 단위로: 674,000,000 -> '6.74억'"""
    if value is None:
        return '-'
    eok = float(value) / 1e8
    if eok >= 100:
        return f'{eok:,.0f}억'
    text = f'{eok:.{digits}f}'.rstrip('0').rstrip('.')
    return f'{text}억'


def count_korean(value: Optional[float]) -> str:
    """
    횟수를 억/만 혼용 표기로 (tone-guide 예: '8억 2,726만회' '778만회' '23만회')

    1만 미만은 콤마 원값.
    """
    if value is None:
        return '-'
    n = int(round(float(value)))
    if n >= 100_000_000:
        eok = n // 100_000_000
        man = round((n - eok * 100_000_000) / 10_000)
        if man:
            return f'{eok}억 {man:,}만'
        return f'{eok}억'
    if n >= 10_000:
        man = n / 10_000
        if man >= 100:
            return f'{man:,.0f}만'
        text = f'{man:.1f}'.rstrip('0').rstrip('.')
        return f'{text}만'
    return f'{n:,}'


def pct(value: Optional[float], digits: int = 0) -> str:
    """
    비율 표기. 0~1 스케일이면 %로 환산, 1 초과(이미 % 값)면 그대로.
    달성율 1.23 -> '123%', CTR 0.0012 -> '0.12%'(digits=2)
    """
    if value is None:
        return '-'
    v = float(value)
    shown = v * 100 if abs(v) <= 1.5 else v
    return f'{shown:.{digits}f}%'


def period_display(raw: str) -> str:
    """기간 원본 표기를 그대로 (파싱 실패 시에도 원문 보존 — 추측 금지)"""
    return (raw or '').strip() or '-'


def yymmdd(dt=None) -> str:
    """파일명 규칙용 YYMMDD"""
    from datetime import date
    d = dt or date.today()
    return d.strftime('%y%m%d')
