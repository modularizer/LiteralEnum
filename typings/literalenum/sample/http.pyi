from __future__ import annotations

from typing import Final, Literal, Mapping, Sequence, TypeGuard, overload
from literalenum import LiteralEnum

MoreHttpMethodsT = Literal['GET', 'POST', 'DELETE', 'PATCH', 'PUT', 'OPTIONS', 'HEAD', 'TRACE']

class MoreHttpMethods(LiteralEnum[MoreHttpMethodsT]):
    GET: Final[MoreHttpMethodsT]
    POST: Final[MoreHttpMethodsT]
    DELETE: Final[MoreHttpMethodsT]
    PATCH: Final[MoreHttpMethodsT]
    PUT: Final[MoreHttpMethodsT]
    OPTIONS: Final[MoreHttpMethodsT]
    HEAD: Final[MoreHttpMethodsT]
    TRACE: Final[MoreHttpMethodsT]
    values: Sequence[MoreHttpMethodsT]
    mapping: Mapping[str, MoreHttpMethodsT]

    @overload
    def __new__(cls, value: MoreHttpMethodsT) -> MoreHttpMethodsT: ...
    @overload
    def __new__(cls, value: object) -> MoreHttpMethodsT: ...

    @classmethod
    def is_member(cls, value: object) -> TypeGuard[MoreHttpMethodsT]: ...
