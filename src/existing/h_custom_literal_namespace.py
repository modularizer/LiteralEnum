from __future__ import annotations

from types import new_class
from typing import Any, ClassVar, Generic, Iterable, Literal, TypeVar, get_args, get_origin

T = TypeVar("T")


def _extract_literal_param(orig_bases: tuple[Any, ...]) -> Any | None:
    """
    Find LiteralNamespace[SomeLiteral] among __orig_bases__ and return SomeLiteral.
    This is called only for subclasses (after LiteralNamespace exists).
    """
    for b in orig_bases:
        origin = get_origin(b)
        if origin is LiteralNamespace:
            (tp,) = get_args(b)
            return tp
    return None


def _literal_values(tp: Any) -> tuple[Any, ...]:
    return get_args(tp) if get_origin(tp) is Literal else ()


def _dupes(seq: list[Any]) -> set[Any]:
    seen: set[Any] = set()
    d: set[Any] = set()
    for x in seq:
        if x in seen:
            d.add(x)
        seen.add(x)
    return d


class LiteralNamespaceMeta(type):
    def __new__(mcls, name: str, bases: tuple[type, ...], ns: dict[str, Any]):
        # Collect uppercase members before class creation
        items: dict[str, Any] = {
            k: v for k, v in ns.items() if k.isupper() and not k.startswith("_")
        }

        annotations: dict[str, Any] = dict(ns.get("__annotations__", {}))

        # Create the class first (safe for bootstrap)
        cls = super().__new__(mcls, name, bases, dict(ns))

        if annotations:
            cls.__annotations__ = annotations

        cls._items_ = items

        # Skip validation for the base class itself (explicit marker)
        if ns.get("__literal_namespace_base__", False):
            return cls

        # Validate for subclasses only
        orig_bases = ns.get("__orig_bases__", ())
        tp = _extract_literal_param(orig_bases)
        lit_vals = _literal_values(tp) if tp is not None else ()

        if lit_vals:
            expected = list(lit_vals)
            actual = list(items.values())

            missing = set(expected) - set(actual)
            extra = set(actual) - set(expected)
            dup_expected = _dupes(expected)
            dup_actual = _dupes(actual)

            if (
                missing
                or extra
                or dup_expected
                or dup_actual
                or len(expected) != len(actual)
            ):
                raise TypeError(
                    f"{name} must be a 1:1 match with Literal args {expected!r}. "
                    f"missing={missing!r}, extra={extra!r}, "
                    f"dup_literal={dup_expected!r}, dup_class={dup_actual!r}"
                )

        return cls

    def __iter__(cls) -> Iterable[T]:
        return iter(cls._items_.values())

    def __len__(cls) -> int:
        return len(cls._items_)

    def __contains__(cls, value: object) -> bool:
        return value in cls._items_.values()

    def values(cls) -> list[T]:
        return list(cls._items_.values())

    def names(cls) -> list[str]:
        return list(cls._items_.keys())

    def items(cls) -> list[tuple[str, T]]:
        return list(cls._items_.items())

    def __instancecheck__(cls, obj: object) -> bool:
        return obj in cls


class LiteralNamespace(Generic[T], metaclass=LiteralNamespaceMeta):
    # Explicit marker recognized by the metaclass (no name/module hacks)
    __literal_namespace_base__ = True

    _items_: ClassVar[dict[str, Any]]


def make_namespace(name: str, tp: Any):
    ns: dict[str, Any] = {}
    for v in get_args(tp):
        if isinstance(v, str) and v.isidentifier():
            ns[v] = v

    return new_class(name, (LiteralNamespace[tp],), {}, lambda d: d.update(ns))


if __name__ == "__main__":
    HttpMethodT = Literal["GET", "POST", "DELETE"]

    class HttpMethod(LiteralNamespace[HttpMethodT]):
        GET: HttpMethodT = "GET"
        POST: HttpMethodT = "POST"
        DELETE: HttpMethodT = "DELETE"

    from typing import LiteralEnum
    class HttpMethod(LiteralEnum):
        GET = "GET"
        POST = "POST"
        DELETE = "DELETE"

    # HttpMethod should be treated like Literal["GET", "POST", "DELETE"] in static type checking

    # Raises at class definition time:
    # class BadHttpMethod(LiteralNamespace[HttpMethodT]):
    #     GET: HttpMethodT = "GET"
    #     POST: HttpMethodT = "POST"
    #     PUT: HttpMethodT = "PUT"

    # Works with new_class too:
    # HttpMethod2 = make_namespace("HttpMethod2", HttpMethodT)


