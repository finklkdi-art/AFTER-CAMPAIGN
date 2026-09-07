# -*- coding: utf-8 -*-
"""
Stage 3 인사이트 생성 패키지

  engine.py           도출 실행 + Checklist 변환
  rules_media.py      매체·상품별 효율 비교
  rules_targeting.py  타겟팅별 비교
  rules_kpi.py        목표 대비 달성률 (Full 모드)
  rules_period.py     기간·Phase별 추이
  strategy.py         차기 캠페인 전략 방향 4개 영역
  phrasing.py         tone-guide 문체 문구 조립
  metrics.py          비율 재계산·임계값 판정
  config.py           Config/insight_rules.json 로딩
"""

from .config import InsightConfig
from .engine import InsightEngine

__all__ = ['InsightEngine', 'InsightConfig']
