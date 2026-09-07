# -*- coding: utf-8 -*-
"""
결과보고서 생성 패키지 (Stage 2 블록 빌드 + Stage 4 PPTX 렌더)

디자인 원천: Skills/campaign-report-pptx.skill
  - references/design-spec.md 의 레벨 체계·좌표·색상·표/차트 스타일을
    python-pptx 로 포팅함 (원본은 pptxgenjs 기준)
  - references/tone-guide.md 의 개조식 명사형 문체를 자동 문구에 적용

폰트 절대 규칙 (사용자 지정):
  - Fonts/ 폴더의 Samsung SS Head/Body KR 7종 웨이트만 사용
  - PowerPoint 굵게(bold) 플래그 전면 금지 — 웨이트는 패밀리명으로 선택
    (각 OTF가 'Samsung SS Head KR Bold' 처럼 독립 패밀리로 등록되어 있음)
"""

from .blocks import ReportSpecBuilder
from .renderer import ReportRenderer
from . import revise

__all__ = ['ReportSpecBuilder', 'ReportRenderer', 'revise']
