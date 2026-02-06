from literalenum import LiteralEnum


class HttpMethod(LiteralEnum):
    GET = "GET"
    POST = "POST"
    DELETE = "DELETE"


class HttpStatus(LiteralEnum):
    OK = 200
    NOT_FOUND = 404
    INTERNAL_SERVER_ERROR = 500


class ExtendedMethod(HttpMethod, extend=True):
    OPTIONS = "OPTIONS"
    HEAD = "HEAD"


class WithAliases(LiteralEnum):
    GET = "GET"
    get = "GET"  # alias


class MixedTypes(LiteralEnum):
    NAME = "hello"
    CODE = 42
    FLAG = True
    NOTHING = None


class Empty(LiteralEnum):
    pass


def handle(method: HttpMethod) -> None: ...


handle("GET")       # should be accepted
handle("POST")      # should be accepted
HttpMethod.GET       # should type as Literal["GET"]
x: HttpMethod        # should show union type

# Extended class includes parent members
y: ExtendedMethod    # should show GET, POST, DELETE, OPTIONS, HEAD

# Individual member access
status_code = HttpStatus.OK  # should type as Literal[200]

# Metaclass methods
all_methods = HttpMethod.values()
method_names = HttpMethod.keys()
method_items = HttpMethod.items()
is_valid = HttpMethod.is_valid("GET")
validated = HttpMethod.validate("GET")
