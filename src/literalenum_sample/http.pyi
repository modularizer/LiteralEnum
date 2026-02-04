from __future__ import annotations
from typing import ClassVar, Final, Literal, Iterable, TypeGuard, TypeAlias, overload
from literalenum import LiteralEnum

HttpMethodT: TypeAlias = Literal["GET", "POST", "DELETE"]

class HttpMethod(LiteralEnum[HttpMethodT]):
    T_ = Literal["GET", "POST", "DELETE"]
    GET: Final[Literal["GET"]] = "GET"
    POST: Final[Literal["POST"]] = "POST"
    DELETE: Final[Literal["DELETE"]] = "DELETE"
    values: ClassVar[Iterable[HttpMethodT]]
    mapping: ClassVar[dict[str, HttpMethodT]]

    @overload
    def __new__(cls, value: HttpMethodT) -> HttpMethodT: ...
    @overload
    def __new__(cls, value: object) -> HttpMethodT: ...

    @classmethod
    def is_member(cls, value: object) -> TypeGuard[HttpMethodT]: ...

MoreHttpMethodsT: TypeAlias = Literal["GET", "POST", "DELETE", "PATCH", "PUT", "OPTIONS", "HEAD", "TRACE"]

class MoreHttpMethods(HttpMethod):
    T_ = Literal["GET", "POST", "DELETE", "PATCH", "PUT", "OPTIONS", "HEAD", "TRACE"]
    PATCH: Final[Literal["PATCH"]] = "PATCH"
    PUT: Final[Literal["PUT"]] = "PUT"
    OPTIONS: Final[Literal["OPTIONS"]] = "OPTIONS"
    HEAD: Final[Literal["HEAD"]] = "HEAD"
    TRACE: Final[Literal["TRACE"]] = "TRACE"
    values: ClassVar[Iterable[MoreHttpMethodsT]]
    mapping: ClassVar[dict[str, MoreHttpMethodsT]]

    @overload
    def __new__(cls, value: MoreHttpMethodsT) -> MoreHttpMethodsT: ...
    @overload
    def __new__(cls, value: object) -> MoreHttpMethodsT: ...

    @classmethod
    def is_member(cls, value: object) -> TypeGuard[MoreHttpMethodsT]: ...

