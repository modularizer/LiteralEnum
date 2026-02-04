def graphene_enum(cls) -> type:
    """Convert this LiteralEnum to a Graphene GraphQL enum type.

    Requires ``graphene`` to be installed.  Uses canonical members
    only (aliases are excluded)::

        class Color(LiteralEnum):
            RED = "red"
            GREEN = "green"

        # use in a Graphene schema
        ColorEnum = Color.graphene_enum
    """
    import enum as _enum
    import graphene

    PyEnum = _enum.Enum(cls.__name__, dict(cls.unique_mapping))
    return graphene.Enum.from_enum(PyEnum)