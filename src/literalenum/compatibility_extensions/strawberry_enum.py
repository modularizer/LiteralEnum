def strawberry_enum(cls) -> type:
    """Convert this LiteralEnum to a Strawberry GraphQL enum type.

    Requires ``strawberry`` to be installed.  Uses canonical members
    only (aliases are excluded)::

        class Color(LiteralEnum):
            RED = "red"
            GREEN = "green"

        # use in a Strawberry schema
        ColorEnum = Color.strawberry_enum
    """
    import enum as _enum
    import strawberry

    PyEnum = _enum.Enum(cls.__name__, dict(cls.unique_mapping))
    return strawberry.enum(PyEnum)