from __future__ import annotations
from typing import ClassVar, Final, Literal, Iterable, Never, NoReturn, TypeGuard, TypeAlias, overload
from literalenum import LiteralEnum

HttpMethodT: TypeAlias = Literal["GET", "POST", "DELETE", "PATCH", "PUT"]

class HttpMethod(LiteralEnum[HttpMethodT]):
    T_ = Literal["GET", "POST", "DELETE", "PATCH", "PUT"]
    GET: Final[Literal["GET"]] = "GET"
    POST: Final[Literal["POST"]] = "POST"
    DELETE: Final[Literal["DELETE"]] = "DELETE"
    PATCH: Final[Literal["PATCH"]] = "PATCH"
    PUT: Final[Literal["PUT"]] = "PUT"
    values: ClassVar[Iterable[HttpMethodT]]
    mapping: ClassVar[dict[str, HttpMethodT]]

    def __new__(cls, value: Never) -> NoReturn: ...

    @classmethod
    def is_member(cls, value: object) -> TypeGuard[HttpMethodT]: ...

HttpStatusCodeT: TypeAlias = Literal[100, 101, 102, 103, 200, 201, 202, 203, 204, 205, 206, 207, 208, 226, 300, 301, 302, 303, 304, 305, 307, 308, 400, 401, 402, 403, 404, 405, 406, 407, 408, 409, 410, 411, 412, 413, 414, 415, 416, 417, 418, 421, 422, 423, 424, 425, 426, 428, 429, 431, 451, 500, 501, 502, 503, 504, 505, 506, 507, 508, 510, 511]

class HttpStatusCode(LiteralEnum[HttpStatusCodeT]):
    T_ = Literal[100, 101, 102, 103, 200, 201, 202, 203, 204, 205, 206, 207, 208, 226, 300, 301, 302, 303, 304, 305, 307, 308, 400, 401, 402, 403, 404, 405, 406, 407, 408, 409, 410, 411, 412, 413, 414, 415, 416, 417, 418, 421, 422, 423, 424, 425, 426, 428, 429, 431, 451, 500, 501, 502, 503, 504, 505, 506, 507, 508, 510, 511]
    CONTINUE: Final[Literal[100]] = 100
    SWITCHING_PROTOCOLS: Final[Literal[101]] = 101
    PROCESSING: Final[Literal[102]] = 102
    EARLY_HINTS: Final[Literal[103]] = 103
    OK: Final[Literal[200]] = 200
    CREATED: Final[Literal[201]] = 201
    ACCEPTED: Final[Literal[202]] = 202
    NON_AUTHORITATIVE_INFORMATION: Final[Literal[203]] = 203
    NO_CONTENT: Final[Literal[204]] = 204
    RESET_CONTENT: Final[Literal[205]] = 205
    PARTIAL_CONTENT: Final[Literal[206]] = 206
    MULTI_STATUS: Final[Literal[207]] = 207
    ALREADY_REPORTED: Final[Literal[208]] = 208
    IM_USED: Final[Literal[226]] = 226
    MULTIPLE_CHOICES: Final[Literal[300]] = 300
    MOVED_PERMANENTLY: Final[Literal[301]] = 301
    FOUND: Final[Literal[302]] = 302
    SEE_OTHER: Final[Literal[303]] = 303
    NOT_MODIFIED: Final[Literal[304]] = 304
    USE_PROXY: Final[Literal[305]] = 305
    TEMPORARY_REDIRECT: Final[Literal[307]] = 307
    PERMANENT_REDIRECT: Final[Literal[308]] = 308
    BAD_REQUEST: Final[Literal[400]] = 400
    UNAUTHORIZED: Final[Literal[401]] = 401
    PAYMENT_REQUIRED: Final[Literal[402]] = 402
    FORBIDDEN: Final[Literal[403]] = 403
    NOT_FOUND: Final[Literal[404]] = 404
    METHOD_NOT_ALLOWED: Final[Literal[405]] = 405
    NOT_ACCEPTABLE: Final[Literal[406]] = 406
    PROXY_AUTHENTICATION_REQUIRED: Final[Literal[407]] = 407
    REQUEST_TIMEOUT: Final[Literal[408]] = 408
    CONFLICT: Final[Literal[409]] = 409
    GONE: Final[Literal[410]] = 410
    LENGTH_REQUIRED: Final[Literal[411]] = 411
    PRECONDITION_FAILED: Final[Literal[412]] = 412
    PAYLOAD_TOO_LARGE: Final[Literal[413]] = 413
    URI_TOO_LONG: Final[Literal[414]] = 414
    UNSUPPORTED_MEDIA_TYPE: Final[Literal[415]] = 415
    RANGE_NOT_SATISFIABLE: Final[Literal[416]] = 416
    EXPECTATION_FAILED: Final[Literal[417]] = 417
    IM_A_TEAPOT: Final[Literal[418]] = 418
    MISDIRECTED_REQUEST: Final[Literal[421]] = 421
    UNPROCESSABLE_ENTITY: Final[Literal[422]] = 422
    LOCKED: Final[Literal[423]] = 423
    FAILED_DEPENDENCY: Final[Literal[424]] = 424
    TOO_EARLY: Final[Literal[425]] = 425
    UPGRADE_REQUIRED: Final[Literal[426]] = 426
    PRECONDITION_REQUIRED: Final[Literal[428]] = 428
    TOO_MANY_REQUESTS: Final[Literal[429]] = 429
    REQUEST_HEADER_FIELDS_TOO_LARGE: Final[Literal[431]] = 431
    UNAVAILABLE_FOR_LEGAL_REASONS: Final[Literal[451]] = 451
    INTERNAL_SERVER_ERROR: Final[Literal[500]] = 500
    NOT_IMPLEMENTED: Final[Literal[501]] = 501
    BAD_GATEWAY: Final[Literal[502]] = 502
    SERVICE_UNAVAILABLE: Final[Literal[503]] = 503
    GATEWAY_TIMEOUT: Final[Literal[504]] = 504
    HTTP_VERSION_NOT_SUPPORTED: Final[Literal[505]] = 505
    VARIANT_ALSO_NEGOTIATES: Final[Literal[506]] = 506
    INSUFFICIENT_STORAGE: Final[Literal[507]] = 507
    LOOP_DETECTED: Final[Literal[508]] = 508
    NOT_EXTENDED: Final[Literal[510]] = 510
    NETWORK_AUTHENTICATION_REQUIRED: Final[Literal[511]] = 511
    values: ClassVar[Iterable[HttpStatusCodeT]]
    mapping: ClassVar[dict[str, HttpStatusCodeT]]

    def __new__(cls, value: Never) -> NoReturn: ...

    @classmethod
    def is_member(cls, value: object) -> TypeGuard[HttpStatusCodeT]: ...

MoreHttpMethodsT: TypeAlias = Literal["GET", "POST", "DELETE", "PATCH", "PUT", "OPTIONS", "HEAD", "TRACE"]

class MoreHttpMethods(HttpMethod):
    T_ = Literal["GET", "POST", "DELETE", "PATCH", "PUT", "OPTIONS", "HEAD", "TRACE"]
    OPTIONS: Final[Literal["OPTIONS"]] = "OPTIONS"
    HEAD: Final[Literal["HEAD"]] = "HEAD"
    TRACE: Final[Literal["TRACE"]] = "TRACE"
    values: ClassVar[Iterable[MoreHttpMethodsT]]
    mapping: ClassVar[dict[str, MoreHttpMethodsT]]

    def __new__(cls, value: Never) -> NoReturn: ...

    @classmethod
    def is_member(cls, value: object) -> TypeGuard[MoreHttpMethodsT]: ...

