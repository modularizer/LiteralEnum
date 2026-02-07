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

from typing import Any, Iterator, Mapping, TypeVar, NoReturn, Never, TypeGuard
from types import MappingProxyType
import inspect

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


def is_member(literalenum: type[LE], x: object) -> TypeGuard[LE]:
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


def validate_is_member(literalenum: type[LE], x: object) -> LE:
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
    #
    # _members_:        dict[str, Any]                  — name -> value mapping (all names, including aliases)
    # _ordered_values_: tuple[Any, ...]                 — unique values in first-seen order
    # _value_keys_:     frozenset[tuple[type, object]]  — strict-key set for O(1) ``in``
    # _value_names_:    dict[tuple[type, object], tuple[str, ...]]
    #                                                   — strict-key -> declared names (first = canonical)
    # _allow_aliases_:  bool                            — whether duplicate values are permitted
    # _call_to_validate_: bool                          — whether __call__ validates instead of raising
    # __members__:      MappingProxyType[str, Any]      — public read-only view (all names, including aliases)

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
        literal_bases: list[type] = [b for b in bases if isinstance(b, LiteralEnumMeta)]
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

        base: type = literal_bases[0]

        # --- Guard against accidental subclassing ---
        # If the parent already has members and ``extend=True`` wasn't
        # passed, the user probably didn't intend to widen the value set.
        if not extend and getattr(base, "_members_", {}):
            raise TypeError(
                f"{name} inherits from {base.__name__}; use "
                f"`class {name}({base.__name__}, extend=True): ...` "
                "to inherit and extend members. "
                "Subclassing without extend=True is not allowed."
            )

        # --- Resolve inheritable flags: explicit kwarg wins, else inherit ---
        if allow_aliases is None:
            allow_aliases = getattr(base, "_allow_aliases_", True)
        cls._allow_aliases_ = allow_aliases

        if call_to_validate is None:
            call_to_validate = getattr(base, "_call_to_validate_", False)
        cls._call_to_validate_ = call_to_validate

        # --- Seed from parent if extending, otherwise start fresh ---
        if extend:
            members: dict[str, Any] = dict(getattr(base, "_members_", {}))
            values: list[Any] = list(getattr(base, "_ordered_values_", ()))
            value_keys: set[tuple[type, object]] = set(getattr(base, "_value_keys_", frozenset()))
            # Deep-copy so appending alias names doesn't mutate the parent.
            value_names: dict[tuple[type, object], list[str]] = {
                k: list(v) for k, v in getattr(base, "_value_names_", {}).items()
            }
        else:
            members = {}
            values = []
            value_keys = set()
            value_names = {}

        ignore: set[str] = _parse_ignore(ns)

        # --- Scan namespace for member candidates ---
        # A name is treated as a member if it:
        #   - is not in the _ignore_ set
        #   - does not start with "_"
        #   - is not a descriptor (function, property, classmethod, etc.)
        #   - has a value whose type is allowed by typing.Literal
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

            # Prevent name collisions when extending a parent.
            if extend and k in members:
                raise TypeError(
                    f"Member name '{name}.{k}' conflicts with inherited member "
                    f"'{base.__name__}.{k}'."
                )

            members[k] = v

            # Deduplicate by strict key so that e.g. True and 1 remain
            # distinct, but the same (type, value) pair isn't added twice.
            # Duplicate values are permitted; the first declared name is
            # canonical.  Later names for the same value become aliases.
            key: tuple[type, object] = _strict_key(v)
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
        """A read-only ``{name: value}`` mapping of all members, including aliases."""
        return cls.__members__

    @property
    def unique_mapping(cls) -> Mapping[str, Any]:
        """A read-only ``{name: value}`` mapping of canonical members only.

        Aliases are excluded — each unique value appears under its
        first-declared name only::

            class Method(LiteralEnum):
                GET = "GET"
                get = "GET"       # alias

            Method.unique_mapping  # {"GET": "GET"}
            Method.mapping         # {"GET": "GET", "get": "GET"}
        """
        return MappingProxyType({
            names[0]: cls._members_[names[0]]
            for names in cls._value_names_.values()
        })

    @property
    def name_mapping(cls) -> Mapping[Any, str]:
        """A read-only ``{value: canonical_name}`` inverse mapping.

        Each unique value maps to its first-declared (canonical) name::

            class Method(LiteralEnum):
                GET = "GET"
                get = "GET"       # alias

            Method.name_mapping   # {"GET": "GET"}

        See also :attr:`names_mapping` for all names including aliases.
        """
        return MappingProxyType({
            v: names[0]
            for v, names in zip(cls._ordered_values_, cls._value_names_.values())
        })

    @property
    def names_by_value(cls) -> Mapping[Any, str]:
        return cls.name_mapping


    @property
    def names_mapping(cls) -> Mapping[Any, tuple[str, ...]]:
        """A read-only ``{value: (name, ...)}`` inverse mapping.

        Each unique value maps to a tuple of all its declared names
        (canonical first, then aliases)::

            class Method(LiteralEnum):
                GET = "GET"
                get = "GET"       # alias

            Method.names_mapping  # {"GET": ("GET", "get")}
        """
        return MappingProxyType({
            v: names
            for v, names in zip(cls._ordered_values_, cls._value_names_.values())
        })

    def keys(cls) -> tuple[str, ...]:
        """Return canonical member names in definition order (aliases excluded)."""
        return tuple(
            names[0] for names in cls._value_names_.values()
        )

    def values(cls) -> tuple[Any, ...]:
        """Return unique member values in definition order (aliases excluded).

        Equivalent to ``tuple(cls)``.
        """
        return cls._ordered_values_

    def items(cls) -> tuple[tuple[str, Any], ...]:
        """Return ``(canonical_name, value)`` pairs in definition order (aliases excluded)."""
        return tuple(zip(cls.keys(), cls._ordered_values_))

    # ---- Alias introspection ----

    def names(cls, value: object) -> tuple[str, ...]:
        """Return all declared names for *value*, in definition order.

        The first element is the canonical name; any subsequent elements
        are aliases.  Useful for synonyms, deprecations, or backwards
        compatibility::

            class Method(LiteralEnum):
                GET = "GET"
                get = "GET"       # alias

            Method.names("GET")           # ("GET", "get")
            Method.canonical_name("GET")  # "GET"

        Raises:
            KeyError: If *value* is not a member of this LiteralEnum.
        """
        try:
            return cls._value_names_[_strict_key(value)]
        except KeyError:
            raise KeyError(
                f"{value!r} is not a member of {cls.__name__}"
            ) from None

    def canonical_name(cls, value: object) -> str:
        """Return the canonical (first-declared) name for *value*.

        Raises:
            KeyError: If *value* is not a member of this LiteralEnum.
        """
        return cls.names(value)[0]

    def __iter__(cls) -> Iterator[Any]:
        """Iterate over unique member *values* in first-seen order.

        Aliases are collapsed — each underlying value appears exactly once.

        Example::

            class Method(LiteralEnum):
                GET = "GET"
                get = "GET"   # alias, not yielded separately

            list(Method)  # ["GET"]
        """
        return iter(cls._ordered_values_)

    def __reversed__(cls) -> Iterator[Any]:
        """Iterate over unique member values in reverse definition order.

        Example::

            list(reversed(HttpMethod))  # ["DELETE", "POST", "GET"]
        """
        return reversed(cls._ordered_values_)

    def __len__(cls) -> int:
        """Return the number of unique member values (aliases are not counted)."""
        return len(cls._ordered_values_)

    def __bool__(cls) -> bool:
        """A LiteralEnum class is truthy if it has any members.

        Example::

            class Empty(LiteralEnum):
                pass

            bool(Empty)       # False
            bool(HttpMethod)  # True
        """
        return bool(cls._ordered_values_)

    def __contains__(cls, value: object) -> bool:
        """Test membership using strict (type-aware) equality.

        Example::

            "GET" in HttpMethod   # True
            "git" in HttpMethod   # False
            True in BoolFlags     # won't collide with 1

        Returns ``False`` for unhashable values instead of raising.
        """
        try:
            return _strict_key(value) in cls._value_keys_
        except TypeError:
            return False

    def __getitem__(cls, key: str) -> Any:
        """Look up a member value by its attribute name.

        Example::

            HttpMethod["GET"]  # "GET"

        Raises:
            KeyError: If *key* is not a member name.
        """
        try:
            return cls._members_[key]
        except KeyError:
            raise KeyError(f"'{key}' is not a member of {cls.__name__}") from None

    def __repr__(cls) -> str:
        """Return a readable representation of the LiteralEnum class.

        Example::

            repr(HttpMethod)
            # "<LiteralEnum 'HttpMethod' [GET='GET', POST='POST', DELETE='DELETE']>"
        """
        if not cls._members_:
            return f"<LiteralEnum '{cls.__name__}'>"
        members: str = ", ".join(f"{k}={v!r}" for k, v in cls._members_.items())
        return f"<LiteralEnum '{cls.__name__}' [{members}]>"

    def __or__(cls, other: LiteralEnumMeta) -> LiteralEnumMeta:
        """Combine two LiteralEnums into a new anonymous LiteralEnum.

        The result contains the union of both value sets.  Canonical name
        order is: all of *cls*'s values first, then *other*'s new values.

        Example::

            class Get(LiteralEnum):
                GET = "GET"

            class Post(LiteralEnum):
                POST = "POST"

            Combined = Get | Post
            list(Combined)          # ["GET", "POST"]
            "GET" in Combined       # True
            Combined.__name__       # "Get|Post"
        """
        if not isinstance(other, LiteralEnumMeta):
            return NotImplemented
        ns: dict[str, Any] = {}
        ns.update(cls._members_)
        ns.update(other._members_)
        combined_name: str = f"{cls.__name__}|{other.__name__}"
        return LiteralEnumMeta(combined_name, (LiteralEnum,), ns)

    def __and__(cls, other: LiteralEnumMeta) -> LiteralEnumMeta:
        """Intersect two LiteralEnums into a new anonymous LiteralEnum.

        The result contains only values present in *both* operands.
        Names and order are taken from the left operand (*cls*).

        Example::

            class ReadWrite(LiteralEnum):
                GET = "GET"
                POST = "POST"

            class ReadOnly(LiteralEnum):
                GET = "GET"
                HEAD = "HEAD"

            Common = ReadWrite & ReadOnly
            list(Common)          # ["GET"]
            Common.__name__       # "ReadWrite&ReadOnly"
        """
        if not isinstance(other, LiteralEnumMeta):
            return NotImplemented
        ns: dict[str, Any] = {
            k: v for k, v in cls._members_.items()
            if _strict_key(v) in other._value_keys_
        }
        combined_name: str = f"{cls.__name__}&{other.__name__}"
        return LiteralEnumMeta(combined_name, (LiteralEnum,), ns)

    def __call__(cls, value: Any) -> Any:
        """Call the LiteralEnum class to validate a value.

        Behavior depends on ``call_to_validate``:

        * ``False`` (default): raises ``TypeError`` — LiteralEnum is not
          instantiable.
        * ``True``: validates *value* and returns it if it's a member,
          otherwise raises ``ValueError``.  Equivalent to
          ``cls.validate(value)``::

            class HttpMethod(LiteralEnum, call_to_validate=True):
                GET = "GET"
                POST = "POST"

            HttpMethod("GET")   # "GET"
            HttpMethod("git")   # ValueError
        """
        if cls._call_to_validate_:
            return validate_is_member(cls, value)
        raise TypeError(
            f"{cls.__name__} is not instantiable; "
            f"use {cls.__name__}.validate(x) or x in {cls.__name__}"
        )

    # ---- Validation helpers (available as classmethods on the literalenum) ----

    def is_valid(cls: type[LE], x: object) -> TypeGuard[LE]:
        """Check if *x* is a valid member value (with type narrowing).

        Equivalent to ``is_member(cls, x)`` but available as a method on
        the class itself::

            if HttpMethod.is_valid(user_input):
                ...  # user_input is narrowed to HttpMethod
        """
        return is_member(cls, x)

    def validate(cls: type[LE], x: object) -> LE:
        """Validate *x* is a member value, or raise ``ValueError``.

        Equivalent to ``validate_is_member(cls, x)``::

            method = HttpMethod.validate(user_input)  # raises on bad input
        """
        return validate_is_member(cls, x)

    # ---- Testing utilities ----

    def matches_enum(cls, enum_cls: type) -> bool:
        """Check whether this LiteralEnum has exactly the same values as *enum_cls*.

        Compares the set of unique values in this LiteralEnum against the
        ``.value`` of every member in the given ``enum.Enum`` (or subclass).
        Useful in test suites to assert two parallel definitions stay in sync::

            import enum

            class Color(enum.StrEnum):
                RED = "red"
                GREEN = "green"

            class ColorLE(LiteralEnum):
                RED = "red"
                GREEN = "green"

            assert ColorLE.matches_enum(Color)

        Returns:
            ``True`` if the value sets are identical.
        """
        try:
            enum_values = {m.value for m in enum_cls}
        except TypeError:
            return False
        return set(cls._ordered_values_) == enum_values

    def matches_literal(cls, literal_type: Any) -> bool:
        """Check whether this LiteralEnum has exactly the same values as *literal_type*.

        Extracts the arguments from a ``typing.Literal[...]`` and compares
        them against this LiteralEnum's unique values.  Useful in test suites
        to assert a Literal type alias stays in sync with a LiteralEnum::

            from typing import Literal

            ColorLiteral = Literal["red", "green"]

            class Color(LiteralEnum):
                RED = "red"
                GREEN = "green"

            assert Color.matches_literal(ColorLiteral)

        Returns:
            ``True`` if the value sets are identical.
        """
        from typing import get_args
        args = get_args(literal_type)
        if not args:
            return False
        return set(cls._ordered_values_) == set(args)


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class LiteralEnum(metaclass=LiteralEnumMeta):
    """Base class for defining a set of named literal values.

    Subclass ``LiteralEnum`` and assign literal values as class attributes::

        class Color(LiteralEnum):
            RED = "red"
            GREEN = "green"
            BLUE = "blue"

    At runtime:

    * ``Color.RED`` evaluates to ``"red"`` (a plain ``str``).
    * ``list(Color)`` returns ``["red", "green", "blue"]``.
    * ``"red" in Color`` returns ``True``.
    * ``Color.validate(x)`` returns *x* if valid or raises ``ValueError``.

    At type-check time, ``Color`` is intended to be equivalent to
    ``Literal["red", "green", "blue"]``.

    ``LiteralEnum`` is **not instantiable** — its values are plain scalars,
    not wrapper objects.  Use ``validate()`` or ``is_valid()`` instead.

    Duplicate values are permitted; the first declared name is canonical
    and later names are aliases::

        class Method(LiteralEnum):
            GET = "GET"
            get = "GET"       # alias for GET

        Method.names("GET")           # ("GET", "get")
        Method.canonical_name("GET")  # "GET"
        list(Method)                  # ["GET"]  (aliases not yielded)

    To extend an existing LiteralEnum, pass ``extend=True``::

        class ExtendedColor(Color, extend=True):
            YELLOW = "yellow"
    """
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

    def __new__(cls, value: Never) -> NoReturn | LE:
        """Signal to type checkers that LiteralEnum is not instantiable.

        At runtime, the metaclass ``__call__`` intercepts before this is
        reached — either validating (``call_to_validate=True``) or raising
        ``TypeError``.  This method exists solely so that type checkers
        flag ``HttpMethod("GET")`` as an error by default.
        """
        if cls._call_to_validate_:
            return validate_is_member(cls, value)
        raise TypeError(
            f"{cls.__name__} is not instantiable; "
            f"use {cls.__name__}.validate(x) or x in {cls.__name__}"
        )
