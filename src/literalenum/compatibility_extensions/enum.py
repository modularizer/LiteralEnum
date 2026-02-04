from enum import Enum

import typing_literalenum as core


def enum(cls: core.LiteralEnumMeta) -> Enum:
    return Enum(cls.__name__, dict(cls._members_))