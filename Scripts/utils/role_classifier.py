# -*- coding: utf-8 -*-
"""
RoleClassifier - 문서 역할 동적 추론

Rule Book 5.2:
- 파일명이 1차 신호, 본문 텍스트가 2차 보조 신호
- 판정 키워드는 Config/document_roles.json 에 외부화 (코드 수정 없이 조정 가능)
- 신뢰도가 임계값 미만이면 unknown 으로 두고 사람이 확정
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 하이픈·언더바·공백·점을 제거해 표기 차이를 흡수한다
_SEPARATOR_RE = re.compile(r'[\s\-_.]+')


def _strip_separators(text: str) -> str:
    return _SEPARATOR_RE.sub('', text)


# 설정 파일이 없을 때 사용하는 최소 기본값 (배포 누락 대비)
_FALLBACK_CONFIG: Dict[str, Any] = {
    "min_confidence": 0.30,
    "filename_keyword_weight": 0.45,
    "filename_score_cap": 0.95,
    "text_keyword_weight": 0.02,
    "text_score_cap": 0.20,
    "text_scan_chars": 3000,
    "roles": {
        "proposal": {"label": "제안서", "filename_keywords": ["제안", "기획안"], "text_keywords": []},
        "postbuy": {"label": "포스트바이", "filename_keywords": ["포스트바이", "결과보고"], "text_keywords": []},
    },
    "legacy_slot_priority": {
        "proposal": ["proposal", "media_brief", "media_mix", "sales_guide"],
        "postbuy": ["postbuy", "daily_report"],
    },
    "category_aliases": {},
}


class RoleClassifier:
    """문서 역할을 추론합니다. 설정은 Config/document_roles.json 에서 읽습니다."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Args:
            config_path: 설정 파일 경로. None이면 프로젝트 루트의 Config/ 에서 탐색
        """
        self.config, self.config_source = self._load_config(config_path)

        self.roles: Dict[str, Any] = self.config.get('roles', {})
        self.min_confidence: float = self.config.get('min_confidence', 0.30)
        self._fn_weight: float = self.config.get('filename_keyword_weight', 0.45)
        self._fn_cap: float = self.config.get('filename_score_cap', 0.95)
        self._tx_weight: float = self.config.get('text_keyword_weight', 0.02)
        self._tx_cap: float = self.config.get('text_score_cap', 0.20)
        self._tx_scan: int = self.config.get('text_scan_chars', 3000)

    # ---------- 설정 로딩 ----------

    @staticmethod
    def _default_config_path() -> Path:
        # Scripts/utils/role_classifier.py -> 프로젝트 루트
        return Path(__file__).resolve().parent.parent.parent / 'Config' / 'document_roles.json'

    def _load_config(self, config_path: Optional[str]) -> Tuple[Dict[str, Any], str]:
        """설정을 읽습니다. 실패해도 파이프라인이 멈추지 않도록 기본값으로 폴백합니다."""
        path = Path(config_path) if config_path else self._default_config_path()
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f), str(path)
        except Exception:
            return dict(_FALLBACK_CONFIG), 'fallback(내장 기본값)'

    # ---------- 역할 추론 ----------

    def classify(self, file_name: str, text_content: str = '') -> Tuple[str, float, Dict[str, float]]:
        """
        문서의 역할을 추론합니다.

        Args:
            file_name: 파일명
            text_content: 문서 본문 텍스트

        Returns:
            (역할 키, 신뢰도, 역할별 점수)
            신뢰도가 임계값 미만이면 역할은 'unknown'
        """
        name_lower = (file_name or '').lower()
        text_lower = (text_content or '').lower()[:self._tx_scan]

        # 구분자를 뗀 형태도 함께 비교한다.
        # "Post-buy Report" / "post buy" / "postbuy" 가 모두 같은 키워드에 걸리도록.
        name_flat = _strip_separators(name_lower)

        scores: Dict[str, float] = {}

        for role_key, spec in self.roles.items():
            fn_score = 0.0
            for kw in spec.get('filename_keywords', []):
                if not kw:
                    continue
                kw_lower = kw.lower()
                if kw_lower in name_lower or _strip_separators(kw_lower) in name_flat:
                    fn_score += self._fn_weight
            fn_score = min(fn_score, self._fn_cap)

            tx_score = 0.0
            for kw in spec.get('text_keywords', []):
                if kw and kw.lower() in text_lower:
                    tx_score += self._tx_weight
            tx_score = min(tx_score, self._tx_cap)

            total = min(fn_score + tx_score, 1.0)
            if total > 0:
                scores[role_key] = round(total, 3)

        best_role = max(scores, key=lambda k: scores[k]) if scores else 'unknown'
        best_score = scores.get(best_role, 0.0)

        # 텍스트 점수 상한(_tx_cap)이 임계값보다 낮으므로,
        # 파일명 신호가 전혀 없으면 여기서 항상 unknown 으로 남는다.
        if best_score < self.min_confidence:
            # 구제 규칙 — '…보고' 로 끝나는 기획/제안 문서
            rescued = self._generic_report(file_name, text_content)
            if rescued:
                role, score, reason = rescued
                scores[role] = max(scores.get(role, 0.0), score)
                scores['_generic_report'] = score
                self.last_reason = reason
                return role, score, scores
            return 'unknown', best_score, scores

        return best_role, best_score, scores

    # ---------- '…보고' 구제 규칙 ----------

    #: 직전 classify() 에서 구제 규칙이 발동했을 때의 사유 (Checklist 기재용)
    last_reason: str = ''

    def _generic_report(self, file_name: str,
                        text_content: str) -> Optional[Tuple[str, float, str]]:
        """
        파일명이 '…보고' / '…보고서' 로 끝나는 문서를 제안서로 구제한다.

        다른 역할이 잡히지 않았을 때만(unknown) 호출되므로 '결과보고'(포스트바이)나
        '게재보고'(게재 보고)처럼 이미 구체적 역할이 붙은 파일은 대상이 아니다.

        Returns:
            (역할, 신뢰도, 사유) 또는 None
        """
        rule = self.config.get('generic_report_rule') or {}
        if not rule.get('enabled'):
            return None

        stem = re.sub(r'\.[A-Za-z0-9]{2,5}$', '', (file_name or '')).strip()
        stem = stem.lower()
        try:
            if not re.search(rule.get('stem_pattern', r'보고(서)?$'), stem):
                return None
        except re.error:
            return None

        role = rule.get('assign_role', 'proposal')
        text = (text_content or '').lower()[:self._tx_scan]

        # 본문이 읽히지 않는 경우(이미지 PDF) — 낮은 신뢰도로 두고 사람이 확정
        if len(text.strip()) < int(rule.get('min_text_chars', 200)):
            return (role, float(rule.get('confidence_unverified', 0.30)),
                    f"파일명이 '보고'로 끝나 제안서로 추정 — 본문 텍스트가 없어 "
                    f"내용 검증 불가 (이미지 문서로 보임)")

        hits = sum(1 for kw in rule.get('require_text_keywords', [])
                   if kw and kw.lower() in text)
        bad = sum(1 for kw in rule.get('exclude_text_keywords', [])
                  if kw and kw.lower() in text)

        if hits < int(rule.get('min_text_hits', 3)):
            return None
        if bad >= int(rule.get('max_exclude_hits', 2)):
            return None

        return (role, float(rule.get('confidence_verified', 0.55)),
                f"파일명이 '보고'로 끝나고 기획 키워드 {hits}개 확인 — 제안서로 판정")

    def label_of(self, role_key: str) -> str:
        """역할 키의 사람이 읽는 이름을 반환합니다."""
        if role_key == 'unknown':
            return '역할 미확정'
        return self.roles.get(role_key, {}).get('label', role_key)

    def known_roles(self) -> List[str]:
        """설정에 정의된 역할 키 목록 (+ unknown)"""
        return list(self.roles.keys()) + ['unknown']

    # ---------- 구버전 슬롯 매핑 ----------

    def legacy_slot_priority(self, slot: str) -> List[str]:
        """
        구버전 proposal/postbuy 단일 슬롯에 넣을 대표 문서의 역할 우선순위.

        선택되지 않은 문서도 documents 리스트에 모두 보존되므로,
        여기서의 선택은 '대표'를 고르는 것일 뿐 데이터 소실과 무관함.
        """
        default = _FALLBACK_CONFIG['legacy_slot_priority'].get(slot, [])
        return self.config.get('legacy_slot_priority', {}).get(slot, default)

    # ---------- 품목 추출 ----------

    def infer_category(self, campaign_name: str) -> str:
        """
        캠페인명에서 품목을 추출합니다.

        1순위: 괄호 안 표기 — "(에어컨) AI 무풍콤보..." -> "에어컨"
        2순위: 설정의 category_aliases 사전
        실패 시 빈 문자열을 반환하여 Stage 1.5에서 사람이 입력하게 함
        (브랜드/품목 하드코딩 금지 — Rule Book 1.1)
        """
        if not campaign_name:
            return ''

        # 1순위: 괄호 표기
        if '(' in campaign_name and ')' in campaign_name:
            inner = campaign_name.split('(', 1)[1].split(')', 1)[0].strip()
            if inner:
                return inner

        # 2순위: 별칭 사전
        lowered = campaign_name.lower()
        for category, aliases in self.config.get('category_aliases', {}).items():
            for alias in aliases:
                if alias and alias.lower() in lowered:
                    return category

        # 추측하지 않고 비워 둔다
        return ''
