# -*- coding: utf-8 -*-
"""
인사이트 규칙 설정 로딩 — Config/insight_rules.json

임계값과 키워드는 운영 중 조정될 값이므로 코드에서 분리한다 (claude.md 1.1).
설정을 읽지 못해도 파이프라인이 멈추지 않도록 내장 기본값으로 폴백한다.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


_FALLBACK: Dict[str, Any] = {
    "version": "fallback",
    "thresholds": {
        # 2026.09 완화 — 도출량 확대. 근거가 약한 건은 confidence='low' 로 표시해
        # Stage 1.5 검증 화면에서 기획자가 골라낼 수 있게 한다.
        "min_impressions": 5000,
        "min_views": 500,
        "min_clicks": 50,
        "min_spend": 300000,
        "min_gap_ratio": 1.10,
        "min_compare_items": 2,
        "min_daily_rows": 5,
        "min_stage_gap": 0.10,       # 퍼널 단계 간 달성률 편차 하한
        "min_share_lift": 0.05,      # 기여-예산 비중 격차 하한
        "max_achievement_rate": 5.0,
        "min_achievement_items": 2,
        # 도출된 인사이트는 버리지 않는다 — 장수는 필요한 만큼 늘린다 (AE 결정)
        "max_insights": 99,
        "max_per_axis": 99,
        "max_evidence_per_insight": 5,
        "max_strategy_items": 4,
    },
    "media_kind": {
        "video_min_views": 1000,
        "video_primary_metric": "cpv",
        "video_quality_metric": "vtr",
        "banner_primary_metric": "cpc",
        "banner_quality_metric": "ctr",
    },
    "targeting_types": {},
    "event_keywords": {},
    "media_display": {
        "strip_group_prefix": True,
        "group_prefix_patterns": [r"^[A-Za-z0-9&()./ ]{2,20}-\s*",
                                  r"^[^>]{1,14}>\s*"],
        "max_length": 28,
    },
    "phase_pattern": r"phase\s*([0-9]+)",
    "metric_labels": {
        "vtr": "VTR", "ctr": "CTR", "cpv": "CPV", "cpc": "CPC", "cpm": "CPM",
        "impressions": "노출", "views": "조회", "clicks": "클릭",
        "spend": "집행 금액",
    },
}


class InsightConfig:
    """인사이트 규칙 설정 접근자"""

    def __init__(self, config_path: Optional[str] = None):
        self.data, self.source = self._load(config_path)

    @staticmethod
    def _default_path() -> Path:
        # Scripts/utils/insight/config.py -> 프로젝트 루트
        return (Path(__file__).resolve().parent.parent.parent.parent
                / 'Config' / 'insight_rules.json')

    def _load(self, config_path: Optional[str]) -> Tuple[Dict[str, Any], str]:
        path = Path(config_path) if config_path else self._default_path()
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            return dict(_FALLBACK), 'fallback(내장 기본값)'
        # 누락 키는 기본값으로 보강 (부분 설정 허용)
        merged = dict(_FALLBACK)
        for key, value in data.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                sub = dict(merged[key])
                sub.update(value)
                merged[key] = sub
            else:
                merged[key] = value
        return merged, str(path)

    # ---------- 조회 ----------

    def th(self, key: str) -> Any:
        return self.data['thresholds'].get(key)

    def kind(self, key: str) -> Any:
        return self.data['media_kind'].get(key)

    def metric_label(self, key: str) -> str:
        return self.data['metric_labels'].get(key, key.upper())

    @property
    def targeting_types(self) -> Dict[str, List[str]]:
        return self.data.get('targeting_types', {})

    @property
    def event_keywords(self) -> Dict[str, List[str]]:
        return self.data.get('event_keywords', {})

    @property
    def phase_pattern(self) -> str:
        return self.data.get('phase_pattern', r'phase\s*([0-9]+)')

    def classify_targeting(self, label: str) -> str:
        """타겟팅 표기를 유형으로 분류 (모르면 빈 문자열)"""
        low = (label or '').lower()
        for kind, words in self.targeting_types.items():
            if any(w.lower() in low for w in words):
                return kind
        return ''

    def media_display(self, raw: str) -> str:
        """
        슬라이드 문장용 매체명 표기.

        데이터에는 원본 표기를 그대로 보존하고(데이터 보존 원칙), 문장에서만
        매체군 접두를 떼어낸다. 접두 판정은 영문·기호로만 구성된 경우로 한정해
        한글 매체명을 훼손하지 않는다.
        """
        name = (raw or '').strip()
        if not name:
            return name
        opts = self.data.get('media_display', {})
        if opts.get('strip_group_prefix'):
            patterns = opts.get('group_prefix_patterns') or []
            single = opts.get('group_prefix_pattern')      # 구버전 설정 호환
            if single:
                patterns = list(patterns) + [single]
            for pattern in patterns:
                try:
                    stripped = re.sub(pattern, '', name).strip()
                except re.error:
                    continue
                if stripped and stripped != name:
                    name = stripped
                    break
        cap = opts.get('max_length') or 0
        if cap and len(name) > cap:
            name = name[:cap - 1].rstrip() + '…'
        return name

    def match_event(self, note: str) -> List[str]:
        """운영 이벤트 비고에 해당하는 유형들"""
        low = (note or '').lower()
        return [kind for kind, words in self.event_keywords.items()
                if any(w.lower() in low for w in words)]
