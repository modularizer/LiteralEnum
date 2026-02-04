from __future__ import annotations

from typing import Any, Iterator, Literal, TypeVar, Generic, Iterable

_LITERAL_TYPES = (str, int, bytes, bool, type(None))
_MISSING = object()


def _is_literal_type(value: object) -> bool:
    # typing.Literal supports: str, bytes, int, bool, None (also enums, but we exclude)
    return value is None or isinstance(value, _LITERAL_TYPES)


def _strict_eq(a: object, b: object) -> bool:
    return type(a) is type(b) and a == b


def _strict_in(obj: object, values: Iterable[Any]) -> bool:
    # Prefer identity when possible, but fall back to strict equality.
    for v in values:
        if v is obj:
            return True
        if _strict_eq(v, obj):
            return True
    return False





class LiteralEnumMeta(type):
    """
    Metaclass for "literal enums":
    - Members are real runtime literal values (strings, ints, bools, None, bytes)
    - Class is usable as a validator: HttpMethod("GET") -> "GET"
    - isinstance("GET", HttpMethod) is supported via __instancecheck__
    - Iteration yields VALUES; dict(HttpMethod) yields {NAME: value}
    - Provides typing helpers: .literal and .T
    """

    def __new__(mcls, name: str, bases: tuple[type, ...], ns: dict[str, Any]):
        cls = super().__new__(mcls, name, bases, ns)

        # Base class itself: initialize empty containers
        is_subclass = any(isinstance(b, LiteralEnumMeta) for b in bases)
        if not is_subclass:
            cls._members_: dict[str, Any] = {}
            cls._values_: frozenset[Any] = frozenset()
            cls._ordered_values_: tuple[Any, ...] = ()
            return cls

        # Collect uppercase, non-dunder members as the enum members
        members = {}
        if hasattr(cls, "_members_"):
            members.update(cls._members_)
        vals = []
        if hasattr(cls, "_ordered_values_"):
            vals.extend(cls._ordered_values_)
        val_set = set()
        if hasattr(cls, "_values_"):
            val_set.update(cls._values_)

        # Collect own members
        for k, v in ns.items():
            if not k.isupper() or k.startswith("_"):
                continue
            if not _is_literal_type(v):
                raise TypeError(
                    f"Member '{name}.{k}' has value {v!r} (type {type(v).__name__}), "
                    "not a valid Literal type."
                )
            members[k] = v
            if v not in val_set:
                val_set.add(v)
                vals.append(v)

        cls._members_ = members
        cls._values_ = frozenset(val_set)
        cls._ordered_values_ = tuple(vals)
        cls.__args__ = cls._ordered_values_
        return cls

    @property
    def args(cls) -> tuple[Any, ...]:
        return tuple(cls._ordered_values_)

    @property
    def choices(cls) -> tuple[Any, ...]:
        return tuple(cls._ordered_values_)

    @property
    def choices_kv(cls) -> tuple[tuple[str, Any], ...]:
        return tuple((k, v) for k, v in cls._members_.items())

    def to_jsonable(cls, v: Any) -> Any:
        cls(v)  # validate
        if isinstance(v, (bytes, bytearray, memoryview)):
            return bytes(v).decode("base64")
        return v

    @property
    def validator(cls):
        return cls  # since cls(value) validates

    # --- Prevent mutation of declared members ---
    def __setattr__(cls, name: str, value: Any) -> None:
        if name in getattr(cls, "_members_", {}):
            raise AttributeError(f"Cannot reassign '{cls.__name__}.{name}'")
        super().__setattr__(name, value)

    def __delattr__(cls, name: str) -> None:
        if name in getattr(cls, "_members_", {}):
            raise AttributeError(f"Cannot delete '{cls.__name__}.{name}'")
        super().__delattr__(name)

    # --- Iteration yields VALUES (your preference) ---
    def __iter__(cls) -> Iterator[Any]:
        return iter(cls._ordered_values_)

    def __reversed__(cls) -> Iterator[Any]:
        return reversed(cls._ordered_values_)

    def __len__(cls) -> int:
        return len(cls._members_)

    # --- Membership on the class: "x in HttpMethod" ---
    def __contains__(cls, value: object) -> bool:
        return _strict_in(value, cls._values_)


    def __getitem__(cls, key: str) -> Any:
        try:
            return cls._members_[key]
        except KeyError:
            raise KeyError(f"'{key}' is not a member of {cls.__name__}") from None

    def keys(cls):
        return cls._members_.keys()

    def values(cls):
        return cls._members_.values()

    def items(cls):
        return cls._members_.items()

    def as_dict(cls) -> dict[str, Any]:
        return dict(cls._members_)

    @property
    def mapping(cls) -> dict[str, Any]:
        return dict(cls._members_)


    # --- isinstance("GET", HttpMethod) ---
    def __instancecheck__(cls, obj: object) -> bool:
        return _strict_in(obj, cls._values_)

    # --- Validator/constructor ---
    def __call__(cls, value: Any = _MISSING) -> Any:
        if value is _MISSING:
            raise TypeError(f"{cls.__name__}() requires a value argument")
        if _strict_in(value, cls._values_):
            return value
        valid = ", ".join(repr(v) for v in cls._ordered_values_)
        raise ValueError(f"{value!r} is not a valid {cls.__name__}. Valid: {valid}")

    def __repr__(cls) -> str:
        if not cls._members_:
            return f"<LiteralEnum '{cls.__name__}'>"
        members = ", ".join(f"{k}={v!r}" for k, v in cls._members_.items())
        return f"<LiteralEnum '{cls.__name__}' [{members}]>"

    @property
    def literal(cls) -> Any:
        return Literal[*cls._ordered_values_]

    @property
    def enum(cls) -> "Enum":
        if getattr(cls, "_enum_cache_", None) is None:
            from enum import Enum
            cls._enum_cache_ = Enum(cls.__name__, cls._members_)
        return cls._enum_cache_

    @property
    def str_enum(cls) -> "StrEnum":
        if not all(isinstance(v, str) for v in cls._ordered_values_ if v is not None):
            raise TypeError("str_enum only works on a string-valued LiteralEnum")

        if getattr(cls, "_str_enum_cache_", None) is None:
            from enum import StrEnum
            cls._str_enum_cache_ = StrEnum(cls.__name__, cls._members_)
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
        return Annotated[cls.literal, *metadata]






T = TypeVar("T")
class LiteralEnum(metaclass=LiteralEnumMeta):
    """Base class for literal enums."""
    def __new__(cls, value: T) -> T: ...
