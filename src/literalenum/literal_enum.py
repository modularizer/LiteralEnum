from __future__ import annotations

import math
from typing import Any, Iterator, Literal, Mapping, TypeVar, TypeGuard, cast
from types import MappingProxyType


# float supported with restrictions: NaN and -0.0 are forbidden
_LITERAL_TYPES = (float, str, int, bytes, bool, type(None))
_MISSING = object()

def _is_nan(v: float) -> bool:
    return math.isnan(v)

def _is_neg_zero(v: float) -> bool:
    # True for -0.0, False for 0.0 and all non-zero values
    return v == 0.0 and math.copysign(1.0, v) < 0.0


def _is_literal_type(value: object) -> bool:
    # typing.Literal supports: str, bytes, int, bool, None (also enums, but we exclude)
    return value is None or isinstance(value, _LITERAL_TYPES)


def _strict_key(value: object) -> tuple[type, object]:
    """
    A hashable identity for "strict equality" (type + value), preventing
    bool/int collisions (True vs 1) and similar edge cases.
    """
    return (type(value), value)



E = TypeVar("E", bound="LiteralEnum")

class LiteralEnumMeta(type):
    """
    Metaclass for "literal enums":

    - Members are real runtime literal values (strings, ints, bools, None, bytes)
    - Class is usable as a validator: HttpMethod("GET") -> "GET"
    - isinstance("GET", HttpMethod) is supported via __instancecheck__
    - Iteration yields VALUES; dict(HttpMethod.mapping) yields {NAME: value}
    - Provides typing conveniences: .runtime_literal (a typing.Literal union)
    """

    def __new__(mcls, name: str, bases: tuple[type, ...], ns: dict[str, Any]):
        cls = super().__new__(mcls, name, bases, ns)

        # Base class itself: initialize empty containers.
        is_subclass = any(isinstance(b, LiteralEnumMeta) for b in bases)
        if not is_subclass:
            cls._members_: dict[str, Any] = {}
            cls._ordered_values_: tuple[Any, ...] = ()
            cls._value_keys_: frozenset[tuple[type, object]] = frozenset()
            cls.__members__ = MappingProxyType(cls._members_)
            return cls

        # Inherit base members/value order (if any).
        inherited_members: dict[str, Any] = {}
        inherited_values: list[Any] = []
        inherited_keys: set[tuple[type, object]] = set()

        for b in bases:
            if isinstance(b, LiteralEnumMeta):
                inherited_members.update(getattr(b, "_members_", {}))
                inherited_values.extend(getattr(b, "_ordered_values_", ()))
                inherited_keys.update(getattr(b, "_value_keys_", frozenset()))

        members: dict[str, Any] = dict(inherited_members)
        values: list[Any] = list(inherited_values)
        value_keys: set[tuple[type, object]] = set(inherited_keys)

        # Collect own members: UPPERCASE, non-private.
        for k, v in ns.items():
            if not k.isupper() or k.startswith("_"):
                continue
            if not _is_literal_type(v):
                raise TypeError(
                    f"Member '{name}.{k}' has value {v!r} (type {type(v).__name__}), "
                    "not a supported Literal value."
                )
            if isinstance(v, float):
                if _is_nan(v):
                    raise TypeError(
                        f"Member '{name}.{k}' is NaN; NaN is not permitted in LiteralEnum."
                    )
                if _is_neg_zero(v):
                    raise TypeError(
                        f"Member '{name}.{k}' is -0.0; negative zero is not permitted in LiteralEnum."
                    )

            members[k] = v

            key = _strict_key(v)
            if key not in value_keys:
                value_keys.add(key)
                values.append(v)

        cls._members_ = members
        cls._ordered_values_ = tuple(values)
        cls._value_keys_ = frozenset(value_keys)

        # Enum-compatible read-only mapping of member names -> values.
        cls.__members__ = MappingProxyType(cls._members_)

        # Convenience for runtime introspection (NOT a typing contract):
        # - __args__ : tuple of values
        # - T_       : a Literal[...] union of values
        cls.__args__ = cls._ordered_values_
        return cls

    # ----- Introspection helpers -----

    @property
    def args(cls) -> tuple[Any, ...]:
        return tuple(cls._ordered_values_)

    @property
    def choices(cls) -> tuple[Any, ...]:
        return tuple(cls._ordered_values_)

    @property
    def choices_kv(cls) -> tuple[tuple[str, Any], ...]:
        # Preserve declaration order of names as stored in _members_
        return tuple((k, v) for k, v in cls._members_.items())

    @property
    def mapping(cls) -> Mapping[str, Any]:
        # Return a read-only mapping for stability.
        return cls.__members__

    def as_dict(cls) -> dict[str, Any]:
        return dict(cls._members_)

    # Enum-ish dict-like helpers
    def keys(cls):
        return cls._members_.keys()

    def values(cls):
        # This yields in insertion order of the dict, which matches declaration order
        # (including inherited members added first).
        return cls._members_.values()

    def items(cls):
        return cls._members_.items()

    # ----- Mutation prevention -----

    def __setattr__(cls, name: str, value: Any) -> None:
        if name in getattr(cls, "_members_", {}):
            raise AttributeError(f"Cannot reassign '{cls.__name__}.{name}'")
        super().__setattr__(name, value)

    def __delattr__(cls, name: str) -> None:
        if name in getattr(cls, "_members_", {}):
            raise AttributeError(f"Cannot delete '{cls.__name__}.{name}'")
        super().__delattr__(name)

    # ----- Container / iteration -----

    def __iter__(cls) -> Iterator[Any]:
        # Iteration yields VALUES, not names.
        return iter(cls._ordered_values_)

    def __reversed__(cls) -> Iterator[Any]:
        return reversed(cls._ordered_values_)

    def __len__(cls) -> int:
        return len(cls._ordered_values_)

    def __contains__(cls, value: object) -> bool:
        try:
            return _strict_key(value) in cls._value_keys_
        except TypeError:
            return False

    def __getitem__(cls, key: str) -> Any:
        try:
            return cls._members_[key]
        except KeyError:
            raise KeyError(f"'{key}' is not a member of {cls.__name__}") from None

    # ----- isinstance + validation -----

    def __instancecheck__(cls, obj: object) -> bool:
        # Treat instances of the LiteralEnum as "values in the set".
        return obj in cls

    def __call__(cls, value: Any = _MISSING) -> Any:
        # Validator/constructor: return the literal value if valid, else error.
        if value is _MISSING:
            raise TypeError(f"{cls.__name__}() requires a value argument")

        if value in cls:
            return value

        # give special error messages for nan or -0.0
        if isinstance(value, float):
            if _is_nan(value):
                raise ValueError("NaN is not a valid LiteralEnum value.")
            if _is_neg_zero(value):
                raise ValueError("-0.0 is not a valid LiteralEnum value.")
        valid = ", ".join(repr(v) for v in cls._ordered_values_)
        raise ValueError(f"{value!r} is not a valid {cls.__name__}. Valid: {valid}")

    def __repr__(cls) -> str:
        if not cls._members_:
            return f"<LiteralEnum '{cls.__name__}'>"
        members = ", ".join(f"{k}={v!r}" for k, v in cls._members_.items())
        return f"<LiteralEnum '{cls.__name__}' [{members}]>"

    # ----- Optional conveniences (library-facing) -----

    @property
    def runtime_literal(cls) -> Any:
        try:
            return Literal[*cls._ordered_values_]
        except TypeError:
            return Any


    def to_jsonable(cls, v: Any) -> Any:
        cls(v)  # validate
        if isinstance(v, (bytes, bytearray, memoryview)):
            # NOTE: "base64" here is a placeholder; decode("base64") is not valid in stdlib.
            # Keep your existing behavior if you have a custom codec; otherwise implement properly.
            return bytes(v)
        return v

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

    def is_valid(cls: type[E], x: object) -> TypeGuard[E]:
        return x in cls

    def validate(cls: type[E], x: Any) -> E:
        if x in cls:
            return cast(E, x)
        raise ValueError(f"{x!r} is not a valid {cls.__name__}")


T = TypeVar("T")


class LiteralEnum(metaclass=LiteralEnumMeta):
    """Base class for literal enums."""
    def __new__(cls, value: T) -> T: ...
