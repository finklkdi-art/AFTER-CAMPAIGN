# -*- coding: utf-8 -*-
"""
폰트 설치 확인 — 산출물이 지정 폰트로 렌더링될 환경인지 점검

PPTX 는 폰트를 이름으로 참조하므로, 열람 PC 에 Samsung SS 폰트가 없으면
PowerPoint 가 대체 폰트로 렌더링한다. (OTF/CFF 는 PPT 임베드 불가)
누락 시 Fonts/ 폴더의 파일을 설치하도록 안내한다.
"""

import sys
from typing import List

from .theme import ALLOWED_FONTS


def installed_font_names() -> set:
    """Windows 레지스트리(HKLM+HKCU)에 등록된 폰트 표시명 집합"""
    names = set()
    if not sys.platform.startswith('win'):
        return names
    try:
        import winreg
    except ImportError:
        return names
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            key = winreg.OpenKey(
                hive, r'SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts')
        except OSError:
            continue
        try:
            i = 0
            while True:
                try:
                    name, _, _ = winreg.EnumValue(key, i)
                except OSError:
                    break
                # "Samsung SS Body KR Bold (TrueType)" → 표시명만
                names.add(name.split(' (')[0].strip())
                i += 1
        finally:
            key.Close()
    return names


def missing_fonts() -> List[str]:
    """산출물에 쓰이는 폰트 중 미설치 목록 (비 Windows 는 검사 생략)"""
    if not sys.platform.startswith('win'):
        return []
    installed = installed_font_names()
    return sorted(f for f in ALLOWED_FONTS if f not in installed)
