from enum import IntEnum

import typing_literalenum as core


def int_enum(cls: core.LiteralEnumMeta) -> IntEnum:
    if not all(isinstance(v, int) for v in cls._ordered_values_ if v is not None):
        raise TypeError("int_enum only works on a int-valued LiteralEnum")
    return IntEnum(cls.__name__, dict(cls._members_))
