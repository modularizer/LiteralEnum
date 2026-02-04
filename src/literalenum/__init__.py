from __future__ import annotations

from .literal_enum import LiteralEnum, LiteralEnumMeta
from .stubgen import main as lestub

import typing_literalenum as core

__all__ = [
    "LiteralEnum", "LiteralEnumMeta",
    "plugin",
    "compatibility_extensions",
    "lestub",
    "core"
]


def __getattr__(name: str):
    if name == "plugin":
        from .mypy_plugin import plugin
        return plugin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")