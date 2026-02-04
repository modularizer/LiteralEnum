from typing import Literal, TypeVar, Any

import typing_literalenum as core

def literal(cls: core.LiteralEnumMeta) -> TypeVar:
    try:
        return Literal[*cls._ordered_values_]
    except TypeError:
        return Any