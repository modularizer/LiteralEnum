from __future__ import annotations

from typing import Any, Iterator, Mapping, TypeVar
from types import MappingProxyType

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


class LiteralEnumMeta(type):
    """
    Metaclass for "literal enums":

    - Members are real runtime literal values (strings, ints, bools, None, bytes)
    - Class is usable as a validator: HttpMethod("GET") -> "GET"
    - Iteration yields VALUES; dict(HttpMethod.mapping) yields {NAME: value}
    - Provides typing conveniences: .runtime_literal (a typing.Literal union)
    """

    def __new__(
            mcls,
            name: str,
            bases: tuple[type, ...],
            ns: dict[str, Any],
            **kwds: Any,
    ):
        extend = bool(kwds.pop("extend", False))

        cls = super().__new__(mcls, name, bases, ns)

        # Is this the root LiteralEnum class (or a non-LiteralEnum subclass)?
        literal_bases = [b for b in bases if isinstance(b, LiteralEnumMeta)]
        is_subclass = bool(literal_bases)
        if not is_subclass:
            cls._members_ = {}
            cls._ordered_values_ = ()
            cls._value_keys_ = frozenset()
            cls.__members__ = MappingProxyType(cls._members_)
            return cls

        # v1 recommendation: forbid multiple LiteralEnum bases
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

        # If extend=False, do NOT inherit members/values.
        if extend:
            members: dict[str, Any] = dict(getattr(base, "_members_", {}))
            values: list[Any] = list(getattr(base, "_ordered_values_", ()))
            value_keys: set[tuple[type, object]] = set(getattr(base, "_value_keys_", frozenset()))
        else:
            members = {}
            values = []
            value_keys = set()

        # Collect own members: UPPERCASE, non-private.
        for k, v in ns.items():
            if not k.isupper() or k.startswith("_"):
                continue
            if not _is_literal_type(v):
                raise TypeError(
                    f"Member '{name}.{k}' has value {v!r} (type {type(v).__name__}), "
                    "not a supported Literal value."
                )

            # Disallow overriding inherited member names when extending
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

    # ----- Introspection helpers -----

    @property
    def mapping(cls) -> Mapping[str, Any]:
        # Return a read-only mapping for stability.
        return cls.__members__

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

    def __call__(cls, value: Any = _MISSING) -> Any:
        # Validator/constructor: return the literal value if valid, else error.
        if value is _MISSING:
            raise TypeError(f"{cls.__name__}() requires a value argument")

        if value in cls:
            return value
        valid = ", ".join(repr(v) for v in cls._ordered_values_)
        raise ValueError(f"{value!r} is not a valid {cls.__name__}. Valid: {valid}")

    def __repr__(cls) -> str:
        if not cls._members_:
            return f"<LiteralEnum '{cls.__name__}'>"
        members = ", ".join(f"{k}={v!r}" for k, v in cls._members_.items())
        return f"<LiteralEnum '{cls.__name__}' [{members}]>"

    def is_valid(cls, x: object) -> bool:
        return x in cls

    def validate(cls, x: Any):
        if x in cls:
            return x
        raise ValueError(f"{x!r} is not a valid {cls.__name__}")


T = TypeVar("T")
class LiteralEnum(metaclass=LiteralEnumMeta):
    """Base class for literal enums."""
    def __new__(cls, value: T) -> T: ...
