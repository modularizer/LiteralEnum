from enum import StrEnum

import typing_literalenum as core


def str_enum(cls: core.LiteralEnumMeta) -> StrEnum:
    if not all(isinstance(v, str) for v in cls._ordered_values_ if v is not None):
        raise TypeError("str_enum only works on a string-valued LiteralEnum")
    return StrEnum(cls.__name__, dict(cls._members_))
