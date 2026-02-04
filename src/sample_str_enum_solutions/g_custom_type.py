from __future__ import annotations

from typing import Any, ClassVar, Generic, Iterable, TypeVar, get_type_hints, Literal



class LiteralNamespaceMeta(type):
    def __new__(mcls, name: str, bases: tuple[type, ...], ns: dict[str, Any]):
        cls = super().__new__(mcls, name, bases, dict(ns))

        # Determine the declared member type (if any)
        # Users set this once per class: __member_type__ = <some type>
        member_type = getattr(cls, "__member_type__", None)

        # Collect uppercase members as "items"
        items: dict[str, Any] = {}
        annotations: dict[str, Any] = dict(ns.get("__annotations__", {}))

        for k, v in ns.items():
            if k.isupper() and not k.startswith("_"):
                items[k] = v
                # If a member type is declared and this member has no annotation, add it
                if member_type is not None and k not in annotations:
                    annotations[k] = member_type

        # Re-attach annotations so type checkers can "see" member types (best effort)
        if annotations:
            cls.__annotations__ = annotations

        cls._items_ = items
        return cls

    def __iter__(cls) -> Iterable[str]:
        return iter(cls._items_.values())

    def __len__(cls) -> int:
        return len(cls._items_)

    def __contains__(cls, value: object) -> bool:
        return value in cls._items_.values()

    def values(cls) -> list[str]:
        return list(cls._items_.values())

    def names(cls) -> list[str]:
        return list(cls._items_.keys())

    def items(cls) -> list[tuple[str, str]]:
        return list(cls._items_.items())

    # Optional: treat membership as "instance of"
    def __instancecheck__(cls, obj: object) -> bool:
        return obj in cls


class LiteralNamespace(metaclass=LiteralNamespaceMeta):
    _items_: ClassVar[dict[str, str]]
    __member_type__: ClassVar[Any]  # subclasses set this


HttpMethodT = Literal["GET", "POST", "DELETE"]

class HttpMethod(LiteralNamespace):
    GET: HttpMethodT = "GET"
    POST: HttpMethodT = "POST"
    DELETE: HttpMethodT = "DELETE"
