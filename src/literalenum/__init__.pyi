# src/literalenum/__init__.pyi
from __future__ import annotations

from typing import (
    Any,
    ClassVar,
    Generic,
    Iterable,
    Iterator,
    Mapping,
    Sequence,
    TypeGuard,
    TypeVar,
    overload,
)

# Values you allow in LiteralEnum members.
# Adjust this union to match what your runtime supports.
LiteralEnumValue = str | int | float | bool | None | bytes

V = TypeVar("V", bound=LiteralEnumValue)

class LiteralEnumMeta(type):
    # runtime helpers your metaclass provides
    values: ClassVar[Sequence[Any]]
    mapping: ClassVar[Mapping[str, Any]]

    def __iter__(cls) -> Iterator[Any]: ...
    def __contains__(cls, value: object) -> bool: ...

    @overload
    def __call__(cls, value: V) -> V: ...
    @overload
    def __call__(cls, value: object) -> V: ...

    def as_dict(cls) -> dict[str, Any]: ...
    def items(cls) -> Iterable[tuple[str, Any]]: ...
    def to_jsonable(cls, value: Any) -> Any: ...

class LiteralEnum(Generic[V], metaclass=LiteralEnumMeta):
    """
    Runtime: a real class used for attribute access, validation, isinstance checks, etc.
    Static: subclasses get precise Literal[...] via generated stubs.
    """

    # NOTE: returning V here means "the validated literal value", not an instance wrapper.
    @overload
    def __new__(cls, value: V) -> V: ...
    @overload
    def __new__(cls, value: object) -> V: ...

    @classmethod
    def is_member(cls, value: object) -> TypeGuard[V]: ...
