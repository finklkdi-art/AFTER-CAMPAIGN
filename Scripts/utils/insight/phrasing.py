# -*- coding: utf-8 -*-
"""
문구 조립 — Skills/campaign-report-pptx.skill 의 tone-guide.md 준수

규칙:
  - 개조식 명사형 종결 (~기록 / ~달성 / ~확보 / ~운영 / ~권고 / ~절감)
  - 서술형 어미("~했습니다", "~입니다") 금지
  - 숫자가 먼저, 해석이 뒤 (키메시지 공식)
  - 금액은 억 단위 한글 혼용, 횟수는 만/억 혼용
  - 경쟁사는 'X사', 자사는 '당사' (여기서는 매체명만 다루므로 해당 없음)
  - 데이터 없는 긍정 포장 금지 — 값이 없으면 해당 문구를 만들지 않는다
"""

from typing import List, Optional

from utils.report import formatters as fmt

from .config import InsightConfig


def won(value: Optional[float]) -> str:
    """단가 표기 — CPV 22원"""
    if value is None:
        return '-'
    return f'{value:,.0f}원'


def eok(value: Optional[float]) -> str:
    """
    금액 표기 — 5.03억 / 1,281만원

    1억 미만을 '0.13억' 으로 적으면 보고 문장에서 읽히지 않으므로
    만원 단위로 바꿔 표기한다 (tone-guide 3장: 금액은 억·만 혼용).
    """
    if value is None:
        return '-'
    if abs(float(value)) < 1e8:
        man = float(value) / 1e4
        if abs(man) < 1:
            return f'{float(value):,.0f}원'
        return f'{man:,.0f}만원'
    return fmt.krw_eok(value)


def cnt(value: Optional[float]) -> str:
    """횟수 표기 — 1,401만회"""
    if value is None:
        return '-'
    return f'{fmt.count_korean(value)}회'


def rate(value: Optional[float], digits: int = 0) -> str:
    """
    비율 표기 — VTR 54.9% / 달성률 176% / 달성률 9,367%

    입력은 항상 비율(1.0 = 100%)이므로 100을 곱한다.
    formatters.pct 의 '1.5 초과면 이미 % 값' 휴리스틱을 쓰면 달성률 93.67(=9,367%)이
    '94%'로 표기되어 미달로 읽히므로 여기서는 쓰지 않는다.
    """
    if value is None:
        return '-'
    return f'{float(value) * 100:,.{digits}f}%'


# 받침이 있는 글자 뒤에 붙는 조사 / 없는 글자 뒤에 붙는 조사
_PARTICLES = {
    '이/가': ('이', '가'),
    '은/는': ('은', '는'),
    '을/를': ('을', '를'),
    '과/와': ('과', '와'),
    '으로/로': ('으로', '로'),
}


def has_final(word: str) -> bool:
    """마지막 글자에 받침이 있는지 (한글이 아니면 받침 있음으로 취급)"""
    if not word:
        return False
    ch = word.rstrip(')]}』」\'"').strip()
    ch = ch[-1] if ch else word[-1]
    code = ord(ch)
    if 0xAC00 <= code <= 0xD7A3:
        return (code - 0xAC00) % 28 != 0
    # 영문·숫자·기호는 받침 있는 것으로 보아 '이/가' 를 붙인다 (SPOTV이/가 → 이)
    return True


def share_rate(value: Optional[float]) -> str:
    """
    비중 표기 — 39% / 2% / 0.3%

    1% 미만을 정수로 반올림하면 '비중 0% → 확대' 처럼 값이 사라진 문장이 된다.
    """
    if value is None:
        return '-'
    pct_value = float(value) * 100
    if 0 < pct_value < 1:
        return f'{pct_value:.1f}%'
    return f'{pct_value:,.0f}%'


def josa_ro(text: str) -> str:
    """
    '~으로 / ~로' 를 붙인다 — 'CPV 23원으로' / 'CTR 0.34%로' / '2.5억회로'

    모음 또는 ㄹ 받침 뒤에는 '로', 그 외 받침 뒤에는 '으로'.
    지표값 뒤에 바로 붙는 조사라 단위 글자에 따라 달라진다.
    """
    if not text:
        return text
    ch = text[-1]
    code = ord(ch)
    if 0xAC00 <= code <= 0xD7A3:
        jong = (code - 0xAC00) % 28
        return f'{text}로' if jong in (0, 8) else f'{text}으로'
    # %·숫자·영문 뒤 — 읽는 소리 기준으로 '로'
    return f'{text}로'


def with_particle(word: str, kind: str = '이/가') -> str:
    """
    단어에 알맞은 조사를 붙인다 — '직방이' / '유튜브가'

    자동 생성 문장은 매체명이 런타임에 결정되므로 조사를 고정할 수 없다.
    """
    solid, light = _PARTICLES.get(kind, _PARTICLES['이/가'])
    return f'{word}{solid if has_final(word) else light}'



def metric_value(metric: str, value: Optional[float],
                 cfg: InsightConfig) -> str:
    """지표명 + 값 — 'CPV 22원', 'VTR 54.9%'"""
    label = cfg.metric_label(metric)
    if value is None:
        return f'{label} -'
    if metric in ('vtr', 'ctr'):
        return f'{label} {rate(value, 1 if metric == "vtr" else 2)}'
    if metric in ('cpv', 'cpc', 'cpm'):
        return f'{label} {won(value)}'
    if metric == 'spend':
        return f'{label} {eok(value)}'
    return f'{label} {cnt(value)}'


def pair(metric_a: str, value_a: Optional[float],
         metric_b: str, value_b: Optional[float],
         cfg: InsightConfig) -> str:
    """두 지표를 슬래시로 병렬 표기 — 'VTR 54.9% · CPV 22원'"""
    parts = [metric_value(metric_a, value_a, cfg),
             metric_value(metric_b, value_b, cfg)]
    return ' · '.join(p for p in parts if not p.endswith(' -'))


def saving_phrase(pct_value: Optional[float], metric: str,
                  cfg: InsightConfig) -> Optional[str]:
    """단가 절감 문구 — 'CPV 단가 39% 절감'"""
    if pct_value is None or pct_value <= 0:
        return None
    return f'{cfg.metric_label(metric)} 단가 {rate(pct_value)} 절감'


def gap_phrase(ratio: Optional[float]) -> Optional[str]:
    """격차 문구 — '2.1배 우위'"""
    if ratio is None or ratio <= 1.0:
        return None
    return f'{ratio:.1f}배'


def short_label(text: str, limit: int = 30) -> str:
    """
    근거 줄에 넣을 라벨 축약 — 원문은 데이터·출처에 그대로 남는다.

    타겟팅 라인명이 길면(예: '④ MF2544 + DMP(인테리어/OTT/경쟁사TV보유관심사 + 게임/엔터))')
    근거 한 줄이 두 줄로 밀려 블록이 지면을 넘긴다.
    """
    t = (text or '').strip()
    if len(t) <= limit:
        return t
    return t[:limit - 1].rstrip(' +,(/') + '…'


def source_label(file_name: str, where: str = '') -> str:
    """자료원 표기 — '자료원: 파일명 <시트명>'"""
    tail = f' <{where}>' if where else ''
    return f'자료원: {file_name}{tail}'


def join_sources(labels: List[str]) -> List[str]:
    """중복 제거하고 순서 보존"""
    out: List[str] = []
    for label in labels:
        if label and label not in out:
            out.append(label)
    return out


def day_label(date: str) -> str:
    """일자 표기 — '06/30' (YYYY-MM-DD 입력)"""
    if not date:
        return '-'
    return date[5:].replace('-', '/') if len(date) >= 10 else date


def period_label(start: str, end: str) -> str:
    """기간 표기 — '06/30 ~ 08/27' (YYYY-MM-DD 입력)"""
    if not start or not end:
        return '-'
    return f'{day_label(start)} ~ {day_label(end)}'
