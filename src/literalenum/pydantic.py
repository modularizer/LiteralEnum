from __future__ import annotations



def model_from_literal_enum(
    enum_cls: type,
    *,
    model_name: str | None = None,
    field_name: str = "value",
    description: str | None = None,
) -> type["BaseModel"]:
    """
    Create a pydantic BaseModel with a single field that validates against enum_cls.literal.
    """
    from pydantic import BaseModel, create_model, Field
    if not hasattr(enum_cls, "literal"):
        raise TypeError("enum_cls must have a .literal (typing.Literal[...]) property")

    ann = enum_cls.literal  # <-- Literal["GET","POST",...]
    default = Field(..., description=description) if description else ...

    return create_model(
        model_name or f"{enum_cls.__name__}Model",
        **{field_name: (ann, default)},
    )
