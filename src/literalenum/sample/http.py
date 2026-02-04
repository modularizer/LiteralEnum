from literalenum import LiteralEnum

class HttpMethod(LiteralEnum):
    GET = "GET"
    POST = "POST"
    DELETE = "DELETE"

class MoreHttpMethods(HttpMethod):
    PATCH = "PATCH"
    PUT = "PUT"
    OPTIONS = "OPTIONS"
    HEAD = "HEAD"
    TRACE = "TRACE"