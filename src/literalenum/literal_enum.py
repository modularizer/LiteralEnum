from __future__ import annotations

from typing import Never, NoReturn, Any

import typing_literalenum as core
from literalenum import compatibility_extensions as compat


class LiteralEnumMeta(core.LiteralEnumMeta):
    def literal(cls):
        return compat.literal(cls)

    def enum(cls):
        return compat.enum(cls)

    def str_enum(cls):
        return compat.str_enum(cls)

    def int_enum(cls):
        return compat.int_enum(cls)

    def json_schema(cls):
        return compat.json_schema(cls)

    def base_model(cls):
        return compat.base_model(cls)

    def sqlalchemy_enum(cls):
        return compat.sqlalchemy_enum(cls)

    def strawberry_enum(cls):
        return compat.strawberry_enum(cls)

    def graphene_enum(cls):
        return compat.graphene_enum(cls)

    def regex_str(cls):
        return compat.regex_str(cls)

    def regex_pattern(cls, flags=0):
        return compat.regex_pattern(cls, flags)

    def annotated(cls):
        return compat.annotated(cls)

    def django_choices(cls):
        return compat.django_choices(cls)

    def click_choice(cls):
        return compat.click_choice(cls)

    def random_choice(cls):
        return compat.random_choice(cls)

    def bare_class(cls):
        return compat.bare_class(cls)

    def set(cls):
        return set(cls)

    def list(cls):
        return list(cls)

    def frozenset(cls):
        return frozenset(cls)

    def dict(cls):
        return dict(cls.mapping)

    def tuple(cls):
        return tuple(cls)

    def str(cls):
        return "|".join(f'"{v}"' if isinstance(v, str) else repr(v) for v in cls)

    def stub(cls):
        from literalenum.stubgen import stub_for
        return stub_for(cls)

    @property
    def T_(cls):
        return cls.literal()

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

    def __new__(cls, value: Never) -> NoReturn | core.LE:
        """Signal to type checkers that LiteralEnum is not instantiable.

        At runtime, the metaclass ``__call__`` intercepts before this is
        reached — either validating (``call_to_validate=True``) or raising
        ``TypeError``.  This method exists solely so that type checkers
        flag ``HttpMethod("GET")`` as an error by default.
        """
        if cls._call_to_validate_:
            return core.validate_is_member(cls, value)
        raise TypeError(
            f"{cls.__name__} is not instantiable; "
            f"use {cls.__name__}.validate(x) or x in {cls.__name__}"
        )
