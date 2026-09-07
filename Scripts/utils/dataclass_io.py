# -*- coding: utf-8 -*-
"""
데이터클래스 역직렬화 — `dataclasses.asdict()` 의 역방향

`to_dict()` 만 있고 `from_dict()` 가 없으면 파싱 결과를 파일로 남겨도 되살릴 수
없어 세션이 끝나면 사라진다 (claude.md 4장: 직렬화는 to_dict/from_dict 대칭).

클래스별로 from_dict 를 손으로 쓰면 필드를 추가할 때 한쪽만 고쳐 값이 조용히
소실되므로, 타입 힌트를 읽어 일반적으로 복원한다.

지원 형태:
  - 기본형 (str / int / float / bool / None)
  - Optional[X]
  - List[X] / Dict[str, X]  (X 가 데이터클래스여도 됨)
  - 중첩 데이터클래스
  - Any (dict 그대로 둠)
"""

from dataclasses import fields, is_dataclass
from typing import (
    Any, Dict, Type, TypeVar, Union, get_args, get_origin, get_type_hints,
)

T = TypeVar('T')

_NONE_TYPE = type(None)

# 클래스별 해석된 타입 힌트 캐시
_HINTS: Dict[type, Dict[str, Any]] = {}


def _hints(cls: type) -> Dict[str, Any]:
    """
    필드 타입 힌트를 실제 타입 객체로 해석한다.

    Python 3.14 부터 애노테이션이 지연 평가되어 `field.type` 이 문자열로 올 수
    있다. 문자열을 그대로 비교하면 중첩 데이터클래스를 알아보지 못해 dict 가
    그대로 남으므로 get_type_hints 로 해석해 둔다.
    """
    cached = _HINTS.get(cls)
    if cached is None:
        try:
            cached = get_type_hints(cls)
        except Exception:
            cached = {f.name: f.type for f in fields(cls)}
        _HINTS[cls] = cached
    return cached


def _unwrap_optional(tp: Any) -> Any:
    """Optional[X] / Union[X, None] 에서 X 를 꺼낸다"""
    if get_origin(tp) is Union:
        args = [a for a in get_args(tp) if a is not _NONE_TYPE]
        if len(args) == 1:
            return args[0]
    return tp


def _coerce(tp: Any, value: Any) -> Any:
    """타입 힌트에 맞춰 값을 복원한다 (모르면 그대로 둔다)"""
    if value is None:
        return None

    tp = _unwrap_optional(tp)
    origin = get_origin(tp)

    if origin in (list, tuple):
        args = get_args(tp)
        inner = args[0] if args else Any
        if not isinstance(value, (list, tuple)):
            return value
        return [_coerce(inner, v) for v in value]

    if origin is dict:
        args = get_args(tp)
        inner = args[1] if len(args) == 2 else Any
        if not isinstance(value, dict):
            return value
        return {k: _coerce(inner, v) for k, v in value.items()}

    if is_dataclass(tp) and isinstance(value, dict):
        return build(tp, value)

    return value


def build(cls: Type[T], data: Dict[str, Any]) -> T:
    """
    딕셔너리에서 데이터클래스 인스턴스를 만든다.

    - 딕셔너리에 없는 필드는 클래스 기본값을 쓴다
    - 클래스에 없는 키는 무시한다 (구버전 스냅샷 호환)

    Args:
        cls: 대상 데이터클래스
        data: `asdict()` 로 만든 딕셔너리

    Returns:
        복원된 인스턴스
    """
    if not is_dataclass(cls):
        raise TypeError(f'데이터클래스가 아님: {cls!r}')
    if not isinstance(data, dict):
        raise TypeError(f'딕셔너리가 아님: {type(data).__name__}')

    hints = _hints(cls)
    kwargs: Dict[str, Any] = {}
    for f in fields(cls):
        if not f.init or f.name not in data:
            continue
        kwargs[f.name] = _coerce(hints.get(f.name, f.type), data[f.name])
    return cls(**kwargs)
