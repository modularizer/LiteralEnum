from __future__ import annotations

from typing import Any, Literal, TypeVar

import typing_literalenum as core


class LiteralEnumMeta(core.LiteralEnumMeta):

    # __________________________________________________________________________________________________________________
    @property
    def runtime_literal(cls) -> Any:
        try:
            return Literal[*cls._ordered_values_]
        except TypeError:
            return Any

    @property
    def enum(cls) -> "Enum":
        if getattr(cls, "_enum_cache_", None) is None:
            from enum import Enum
            cls._enum_cache_ = Enum(cls.__name__, dict(cls._members_))
        return cls._enum_cache_

    @property
    def str_enum(cls) -> "StrEnum":
        if not all(isinstance(v, str) for v in cls._ordered_values_ if v is not None):
            raise TypeError("str_enum only works on a string-valued LiteralEnum")

        if getattr(cls, "_str_enum_cache_", None) is None:
            from enum import StrEnum
            cls._str_enum_cache_ = StrEnum(cls.__name__, dict(cls._members_))
        return cls._str_enum_cache_

    def json_schema(cls) -> "JsonSchema":
        from literalenum.json_schema import literal_enum_schema
        return literal_enum_schema(cls)

    @property
    def base_model(cls) -> type["BaseModel"]:
        from literalenum.pydantic import model_from_literal_enum
        return model_from_literal_enum(cls)

    @property
    def sqlalchemy_enum(cls):
        try:
            from sqlalchemy import Enum
        except ImportError as e:
            raise RuntimeError("Install sqlalchemy to use .sqlalchemy_enum") from e
        return Enum(*cls._ordered_values_, name=cls.__name__)

    @property
    def graphql_enum(cls):
        # strawberry.enum / graphene.Enum need different shapes; provide raw dict
        return dict(cls._members_)

    @property
    def regex(cls) -> str:
        if not all(isinstance(v, str) for v in cls._ordered_values_ if v is not None):
            raise TypeError("regex is only valid for string-valued LiteralEnum")
        import re
        vals = [v for v in cls._ordered_values_ if isinstance(v, str)]
        return "^(?:" + "|".join(re.escape(v) for v in vals) + ")$"

    def annotated(cls, *metadata: Any):
        from typing import Annotated
        return Annotated[cls.runtime_literal, *metadata]


T = TypeVar("T")

class LiteralEnum(metaclass=LiteralEnumMeta):
    """Base class for literal enums."""
    def __new__(cls, value: T) -> T: ...
