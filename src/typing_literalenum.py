"""
LiteralEnum — a runtime namespace for literal values with static exhaustiveness.

LiteralEnum bridges the gap between ``typing.Literal`` and ``enum.Enum`` /
``enum.StrEnum``.  It defines a finite, named set of literal values that:

* are plain runtime scalars (``str``, ``int``, ``bytes``, ``bool``, ``None``),
* provide a runtime namespace, iteration, and validation, and
* can be treated by type checkers as an exhaustive ``Literal[...]`` union.

Minimal example::

    class HttpMethod(LiteralEnum):
        GET = "GET"
        POST = "POST"
        DELETE = "DELETE"

    HttpMethod.GET          # "GET"  (plain str at runtime)
    list(HttpMethod)        # ["GET", "POST", "DELETE"]
    "GET" in HttpMethod     # True
    HttpMethod.validate(x)  # returns x if valid, raises ValueError otherwise

Duplicate values are permitted; the first declared name is canonical.
Subsequent names for the same value are aliases.  Use ``names(value)``
and ``canonical_name(value)`` to introspect.

See the companion PEP draft for the full motivation and typing semantics.
"""

from __future__ import annotations

import sys
from types import MappingProxyType
import inspect
from typing import Any, Iterator, Mapping, TypeVar, NoReturn, TypeGuard

if sys.version_info >= (3, 11):
    from typing import Never
else:
    from typing_extensions import Never


# ---------------------------------------------------------------------------
# Allowed literal types — mirrors the set accepted by ``typing.Literal``
# (PEP 586).  Enum members are technically allowed by Literal but are
# excluded here because LiteralEnum is an *alternative* to Enum.
# ---------------------------------------------------------------------------
_LITERAL_TYPES: tuple[type, ...] = (str, int, bytes, bool, type(None))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_literal_type(value: object) -> bool:
    """Return ``True`` if *value* is a type supported by ``typing.Literal``.

    Supported types: ``str``, ``int``, ``bytes``, ``bool``, and ``None``.
    """
    return isinstance(value, _LITERAL_TYPES)


def _strict_key(value: object) -> tuple[type, object]:
    """Return a hashable ``(type, value)`` pair for identity-safe comparison.

    Python considers ``True == 1`` and ``False == 0``.  Using the type as part
    of the key prevents a ``bool`` member from colliding with an ``int``
    member (or vice versa) inside the value set.

    Example::

        _strict_key(True)   # (bool, True)
        _strict_key(1)      # (int, 1)
        # These are distinct despite True == 1.
    """
    return type(value), value


def _is_descriptor(obj: object) -> bool:
    """Return ``True`` if *obj* looks like a descriptor or function.

    Enum-style semantics: functions, method descriptors, ``property``,
    ``classmethod``, ``staticmethod``, and anything with ``__get__`` are
    treated as class infrastructure rather than member values.
    """
    return (
        inspect.isfunction(obj)
        or inspect.ismethoddescriptor(obj)
        or hasattr(obj, "__get__")
    )


def _parse_ignore(ns: Mapping[str, Any]) -> set[str]:
    """Parse an optional ``_ignore_`` directive from the class namespace.

    Follows the same convention as ``enum.Enum._ignore_``:

    * A whitespace- or comma-separated string: ``"a b c"`` or ``"a, b, c"``
    * A list, tuple, set, or frozenset of name strings.
    * ``None`` (treated as empty).

    Returns:
        A set of attribute names to skip when collecting members.

    Raises:
        TypeError: If ``_ignore_`` is present but not a recognized format.
    """
    ignore = ns.get("_ignore_", ())
    if ignore is None:
        return set()
    if isinstance(ignore, str):
        return {name for name in ignore.replace(",", " ").split() if name}
    if isinstance(ignore, (list, tuple, set, frozenset)):
        return {str(x) for x in ignore}
    raise TypeError("_ignore_ must be a str or a sequence of names")


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

LE = TypeVar("LE", bound="LiteralEnum")


def is_member(literalenum: "LiteralEnumMeta", x: object) -> TypeGuard["LiteralEnumMeta"]:
    """Check whether *x* is a valid member value of *literalenum*.

    Acts as a ``TypeGuard`` so that, after a successful check, a type
    checker can narrow ``x`` to the ``LiteralEnum`` type::

        if is_member(HttpMethod, value):
            reveal_type(value)  # HttpMethod  (i.e. Literal["GET", "POST", ...])

    Args:
        literalenum: The ``LiteralEnum`` subclass to check against.
        x:    The value to test.

    Returns:
        ``True`` if *x* is one of the literal values defined in *literalenum*.
    """
    return x in literalenum


def validate_is_member(literalenum: "LiteralEnumMeta", x: object) -> "LiteralEnum":
    """Validate that *x* is a member of *literalenum*, or raise ``ValueError``.

    Unlike :func:`is_member`, this function raises on failure rather than
    returning ``False``, making it suitable for input validation::

        method = validate_is_member(HttpMethod, user_input)
        # method is now narrowed to HttpMethod

    Args:
        literalenum: The ``LiteralEnum`` subclass to validate against.
        x:    The value to validate.

    Returns:
        *x* unchanged (the runtime value is already a plain literal).

    Raises:
        ValueError: If *x* is not a valid member of *literalenum*.
    """
    if is_member(literalenum, x):
        return x  # type: ignore[return-value]
    raise ValueError(f"{x!r} is not a valid {literalenum.__name__}")


# ---------------------------------------------------------------------------
# Metaclass
# ---------------------------------------------------------------------------

class LiteralEnumMeta(type):
    """Metaclass that powers ``LiteralEnum``.

    Responsibilities:

    1. **Member collection** — during ``__new__``, scans the class namespace
       for public, non-descriptor attributes whose values are literal types.
    2. **Inheritance control** — subclassing a populated ``LiteralEnum``
       requires ``extend=True`` to prevent accidental widening of the value
       set.
    3. **Runtime container protocol** — makes the *class itself* iterable and
       supportive of ``in`` / ``len`` / ``[]`` so that ``"GET" in HttpMethod``
       and ``for m in HttpMethod`` work directly on the class.
    """

    # ---- Internal attributes set on every LiteralEnum subclass ----
    _members_: dict[str, Any]
    _ordered_values_: tuple[Any, ...]
    _value_keys_: frozenset[tuple[type, object]]
    _value_names_: dict[tuple[type, object], tuple[str, ...]]
    _allow_aliases_: bool
    _call_to_validate_: bool
    __members__: MappingProxyType[str, Any]

    def __new__(
        mcls,
        name: str,
        bases: tuple[type, ...],
        ns: dict[str, Any],
        *,
        extend: bool = False,
        allow_aliases: bool | None = None,
        call_to_validate: bool | None = None,
        **kwds: Any,
    ) -> LiteralEnumMeta:
        """Create a new LiteralEnum class, collecting its members.

        Args:
            name:  The class name.
            bases: Base classes.
            ns:    The class body namespace.
            extend: If ``True``, allow subclassing a populated LiteralEnum
                and inherit its members.  Defaults to ``False``.
            allow_aliases: If ``False``, raise ``TypeError`` when two names
                map to the same value.  ``None`` (the default) inherits the
                parent's setting, or ``True`` at the root.
            call_to_validate: If ``True``, calling the class (e.g.
                ``HttpMethod("GET")``) validates and returns the value
                instead of raising ``TypeError``.  ``None`` (the default)
                inherits the parent's setting, or ``False`` at the root.
            **kwds: Reserved for future keyword arguments.

        Returns:
            The newly created class.

        Raises:
            TypeError: On multiple LiteralEnum bases, non-literal member
                values, name conflicts during extension, duplicate values
                when ``allow_aliases=False``, or subclassing without
                ``extend=True``.
        """
        cls = super().__new__(mcls, name, bases, ns)

        # --- Identify LiteralEnum bases ---
        literal_bases: list[LiteralEnumMeta] = [b for b in bases if isinstance(b, LiteralEnumMeta)]
        is_subclass: bool = bool(literal_bases)

        # The root LiteralEnum class itself has no members.
        if not is_subclass:
            cls._members_ = {}
            cls._ordered_values_ = ()
            cls._value_keys_ = frozenset()
            cls._value_names_ = {}
            cls._allow_aliases_ = True if allow_aliases is None else allow_aliases
            cls._call_to_validate_ = False if call_to_validate is None else call_to_validate
            cls.__members__ = MappingProxyType(cls._members_)
            return cls

        # --- Enforce single-base inheritance ---
        if len(literal_bases) > 1:
            raise TypeError(
                f"{name} may not inherit from multiple LiteralEnum bases "
                f"({', '.join(b.__name__ for b in literal_bases)})."
            )

        base: LiteralEnumMeta = literal_bases[0]

        # --- Guard against accidental subclassing ---
        if not extend and base._members_:
            raise TypeError(
                f"{name} inherits from {base.__name__}; use "
                f"`class {name}({base.__name__}, extend=True): ...` "
                "to inherit and extend members. "
                "Subclassing without extend=True is not allowed."
            )

        # --- Resolve inheritable flags: explicit kwarg wins, else inherit ---
        if allow_aliases is None:
            allow_aliases = base._allow_aliases_
        cls._allow_aliases_ = allow_aliases

        if call_to_validate is None:
            call_to_validate = base._call_to_validate_
        cls._call_to_validate_ = call_to_validate

        # --- Seed from parent if extending, otherwise start fresh ---
        if extend:
            members: dict[str, Any] = dict(base._members_)
            values: list[Any] = list(base._ordered_values_)
            value_keys: set[tuple[type, object]] = set(base._value_keys_)
            value_names: dict[tuple[type, object], list[str]] = {
                k: list(v) for k, v in base._value_names_.items()
            }
        else:
            members = {}
            values = []
            value_keys = set()
            value_names = {}

        ignore: set[str] = _parse_ignore(ns)

        # --- Scan namespace for member candidates ---
        for k, v in ns.items():
            if k in ignore or k.startswith("_") or _is_descriptor(v):
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
                value_names[key] = [k]
            else:
                if not allow_aliases:
                    canonical: str = value_names[key][0]
                    raise TypeError(
                        f"Duplicate value {v!r} in '{name}': "
                        f"'{k}' conflicts with canonical member '{canonical}'. "
                        f"Use allow_aliases=True to permit aliases."
                    )
                value_names[key].append(k)

        # --- Freeze the collected members onto the class ---
        cls._members_ = members
        cls._ordered_values_ = tuple(values)
        cls._value_keys_ = frozenset(value_keys)
        cls._value_names_ = {k: tuple(v) for k, v in value_names.items()}
        cls.__members__ = MappingProxyType(cls._members_)
        return cls

    # ---- Container protocol (operates on the *class*, not instances) ----

    @property
    def mapping(cls) -> Mapping[str, Any]:
        return cls.__members__

    @property
    def unique_mapping(cls) -> Mapping[str, Any]:
        return MappingProxyType({
            names[0]: cls._members_[names[0]]
            for names in cls._value_names_.values()
        })

    @property
    def name_mapping(cls) -> Mapping[Any, str]:
        return MappingProxyType({
            v: names[0]
            for v, names in zip(cls._ordered_values_, cls._value_names_.values())
        })

    @property
    def names_by_value(cls) -> Mapping[Any, str]:
        return cls.name_mapping

    @property
    def names_mapping(cls) -> Mapping[Any, tuple[str, ...]]:
        return MappingProxyType({
            v: names
            for v, names in zip(cls._ordered_values_, cls._value_names_.values())
        })

    def keys(cls) -> tuple[str, ...]:
        return tuple(names[0] for names in cls._value_names_.values())

    def values(cls) -> tuple[Any, ...]:
        return cls._ordered_values_

    def items(cls) -> tuple[tuple[str, Any], ...]:
        return tuple(zip(cls.keys(), cls._ordered_values_))

    def names(cls, value: object) -> tuple[str, ...]:
        try:
            return cls._value_names_[_strict_key(value)]
        except KeyError:
            raise KeyError(f"{value!r} is not a member of {cls.__name__}") from None

    def canonical_name(cls, value: object) -> str:
        return cls.names(value)[0]

    def __iter__(cls) -> Iterator[Any]:
        return iter(cls._ordered_values_)

    def __reversed__(cls) -> Iterator[Any]:
        return reversed(cls._ordered_values_)

    def __len__(cls) -> int:
        return len(cls._ordered_values_)

    def __bool__(cls) -> bool:
        return bool(cls._ordered_values_)

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
        members: str = ", ".join(f"{k}={v!r}" for k, v in cls.items())
        return f"<LiteralEnum '{cls.__name__}' [{members}]>"

    def __or__(cls, other: Any) -> LiteralEnumMeta:
        if not isinstance(other, LiteralEnumMeta):
            return NotImplemented
        ns: dict[str, Any] = {}
        ns.update(cls._members_)
        ns.update(other._members_)
        combined_name: str = f"{cls.__name__}|{other.__name__}"
        return LiteralEnumMeta(combined_name, (LiteralEnum,), ns)

    def __and__(cls, other: Any) -> LiteralEnumMeta:
        if not isinstance(other, LiteralEnumMeta):
            return NotImplemented
        ns: dict[str, Any] = {
            k: v for k, v in cls._members_.items()
            if _strict_key(v) in other._value_keys_
        }
        combined_name: str = f"{cls.__name__}&{other.__name__}"
        return LiteralEnumMeta(combined_name, (LiteralEnum,), ns)

    def __call__(cls, value: Any) -> Any:
        if cls._call_to_validate_:
            return validate_is_member(cls, value)
        raise TypeError(
            f"{cls.__name__} is not instantiable; "
            f"use {cls.__name__}.validate(x) or x in {cls.__name__}"
        )

    def is_valid(cls: "LiteralEnumMeta", x: object) -> TypeGuard["LiteralEnumMeta"]:
        return is_member(cls, x)

    def validate(cls: "LiteralEnumMeta", x: object) -> "LiteralEnum":
        return validate_is_member(cls, x)

    def matches_enum(cls, enum_cls: "LiteralEnumMeta") -> bool:
        try:
            enum_values = {m.value for m in enum_cls}
        except (TypeError, AttributeError):
            return False
        return set(cls._ordered_values_) == enum_values

    def matches_literal(cls, literal_type: Any) -> bool:
        from typing import get_args
        args = get_args(literal_type)
        if not args:
            return False
        return set(cls._ordered_values_) == set(args)


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class LiteralEnum(metaclass=LiteralEnumMeta):
    """Base class for defining a set of named literal values."""
    @classmethod
    def __init_subclass__(
            cls,
            *,
            extend: bool = False,
            call_to_validate: bool = False,
            allow_aliases: bool = True,
            **kwargs: Any,
    ) -> None:
        super().__init_subclass__(**kwargs)

    def __new__(cls: "LiteralEnumMeta", value: Never) -> "LiteralEnum":
        if getattr(cls, '_call_to_validate_', False):
            return validate_is_member(cls, value)
        raise TypeError(
            f"{cls.__name__} is not instantiable; "
            f"use {cls.__name__}.validate(x) or x in {cls.__name__}"
        )
