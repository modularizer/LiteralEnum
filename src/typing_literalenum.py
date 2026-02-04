from __future__ import annotations

from typing import Any, Iterator, Mapping, TypeVar, NoReturn, Never, TypeGuard
from types import MappingProxyType
import inspect

_LITERAL_TYPES = (str, int, bytes, bool, type(None))
_MISSING = object()


def _is_literal_type(value: object) -> bool:
    # typing.Literal supports: str, bytes, int, bool, None (also enums, but we exclude)
    return isinstance(value, _LITERAL_TYPES)


def _strict_key(value: object) -> tuple[type, object]:
    """
    A hashable identity for "strict equality" (type + value), preventing
    bool/int collisions (True vs 1) and similar edge cases.
    """
    return type(value), value


def _is_descriptor(obj: object) -> bool:
    # Enum excludes descriptors (functions/methods/properties/etc.)
    # In a class dict, functions are plain function objects; properties/classmethod/staticmethod
    # are descriptor instances.
    return (
        inspect.isfunction(obj)
        or inspect.ismethoddescriptor(obj)
        or hasattr(obj, "__get__")
    )


def _parse_ignore(ns: Mapping[str, Any]) -> set[str]:
    """
    Enum-like `_ignore_` handling.

    Accepts:
      - "_ignore_" = "a b c"
      - "_ignore_" = ["a", "b"]
      - "_ignore_" = ("a", "b")
      - "_ignore_" = {"a", "b"}
    """
    ignore = ns.get("_ignore_", ())
    if ignore is None:
        return set()
    if isinstance(ignore, str):
        return {name for name in ignore.replace(",", " ").split() if name}
    if isinstance(ignore, (list, tuple, set, frozenset)):
        return {str(x) for x in ignore}
    raise TypeError("_ignore_ must be a str or a sequence of names")


LE = TypeVar("LE", bound="LiteralEnum")


def is_member(enum: type[LE], x: object) -> TypeGuard[LE]:
    return x in enum


def validate_is_member(enum: type[LE], x: object) -> LE:
    if is_member(enum, x):
        x = x  # keep runtime value
        return x  # type: ignore[return-value]
    raise ValueError(f"{x!r} is not a valid {enum.__name__}")


class LiteralEnumMeta(type):
    def __new__(
        mcls,
        name: str,
        bases: tuple[type, ...],
        ns: dict[str, Any],
        **kwds: Any,
    ):
        extend = bool(kwds.pop("extend", False))
        cls = super().__new__(mcls, name, bases, ns)

        literal_bases = [b for b in bases if isinstance(b, LiteralEnumMeta)]
        is_subclass = bool(literal_bases)
        if not is_subclass:
            cls._members_ = {}
            cls._ordered_values_ = ()
            cls._value_keys_ = frozenset()
            cls.__members__ = MappingProxyType(cls._members_)
            return cls

        if len(literal_bases) > 1:
            raise TypeError(
                f"{name} may not inherit from multiple LiteralEnum bases "
                f"({', '.join(b.__name__ for b in literal_bases)})."
            )

        base = literal_bases[0]

        if not extend and getattr(base, "_members_", {}):
            raise TypeError(
                f"{name} inherits from {base.__name__}; use "
                f"`class {name}({base.__name__}, extend=True): ...` "
                "to inherit and extend members. "
                "Subclassing without extend=True is not allowed."
            )

        if extend:
            members: dict[str, Any] = dict(getattr(base, "_members_", {}))
            values: list[Any] = list(getattr(base, "_ordered_values_", ()))
            value_keys: set[tuple[type, object]] = set(getattr(base, "_value_keys_", frozenset()))
        else:
            members = {}
            values = []
            value_keys = set()

        ignore = _parse_ignore(ns)

        # Enum-like membership: any non-private name that isn't a descriptor and isn't ignored
        for k, v in ns.items():
            if k in ignore:
                continue
            if k.startswith("_"):
                continue
            if _is_descriptor(v):
                continue

            if not _is_literal_type(v):
                raise TypeError(
                    f"Member '{name}.{k}' has value {v!r} (type {type(v).__name__}), "
                    "not a supported Literal value."
                )

            if extend and k in members:
                raise TypeError(
                    f"Member name '{name}.{k}' conflicts with inherited member "
                    f"'{base.__name__}.{k}'."
                )

            members[k] = v

            key = _strict_key(v)
            if key not in value_keys:
                value_keys.add(key)
                values.append(v)

        cls._members_ = members
        cls._ordered_values_ = tuple(values)
        cls._value_keys_ = frozenset(value_keys)
        cls.__members__ = MappingProxyType(cls._members_)
        return cls

    @property
    def mapping(cls) -> Mapping[str, Any]:
        return cls.__members__

    def __iter__(cls) -> Iterator[Any]:
        return iter(cls._ordered_values_)

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

    def __repr__(cls) -> str:
        if not cls._members_:
            return f"<LiteralEnum '{cls.__name__}'>"
        members = ", ".join(f"{k}={v!r}" for k, v in cls._members_.items())
        return f"<LiteralEnum '{cls.__name__}' [{members}]>"

    def is_valid(cls: type[LE], x: object) -> TypeGuard[LE]:
        return is_member(cls, x)

    def validate(cls: type[LE], x: object) -> LE:
        return validate_is_member(cls, x)


class LiteralEnum(metaclass=LiteralEnumMeta):
    def __new__(cls, not_instantiable: Never) -> NoReturn:
        raise TypeError(
            f"{cls.__name__} is not instantiable; use {cls.__name__}.validate(x) or x in {cls.__name__}"
        )
