"""
Test cases for the LiteralEnum mypy plugin.

Run with:
    mypy --config-file mypy.ini tests/test_typing.py

Expected: lines marked # E: produce errors, all others pass.
"""
from typing import reveal_type

from literalenum import LiteralEnum


# ── String enum ───────────────────────────────────────────────────────────

class HttpMethod(LiteralEnum):
    GET = "GET"
    POST = "POST"
    DELETE = "DELETE"


def handle(method: HttpMethod) -> None:
    pass


# These should PASS
handle("GET")
handle("POST")
handle("DELETE")
handle(HttpMethod.GET)
handle(HttpMethod.POST)

x = HttpMethod.GET
handle(x)

reveal_type(HttpMethod.GET)   # N: Revealed type is "Literal['GET']"


# These should FAIL
handle("git")        # E: Argument 1 to "handle" has incompatible type
handle(123)          # E: Argument 1 to "handle" has incompatible type


# ── Integer enum ──────────────────────────────────────────────────────────

class StatusCode(LiteralEnum):
    OK = 200
    NOT_FOUND = 404

def handle_status(code: StatusCode) -> None:
    pass

handle_status(200)              # should pass
handle_status(StatusCode.OK)    # should pass
handle_status(999)              # E: Argument 1 to "handle_status" has incompatible type

reveal_type(StatusCode.OK)      # N: Revealed type is "Literal[200]"


# ── Boolean enum ──────────────────────────────────────────────────────────

class Feature(LiteralEnum):
    ENABLED = True
    DISABLED = False

def check_feature(f: Feature) -> None:
    pass

check_feature(True)             # should pass
check_feature(Feature.ENABLED)  # should pass
check_feature(42)               # E: Argument 1 to "check_feature" has incompatible type


# ── Constructor ───────────────────────────────────────────────────────────

m = HttpMethod("GET")
handle(m)                       # should pass: m is Literal["GET"]
reveal_type(m)                  # N: Revealed type is "Literal['GET']"


# ── Subclass extends parent ──────────────────────────────────────────────

class ExtendedMethod(HttpMethod):
    PATCH = "PATCH"
    PUT = "PUT"

def handle_extended(method: ExtendedMethod) -> None:
    pass

handle_extended("GET")          # inherited — should pass
handle_extended("PATCH")        # own — should pass
handle_extended("OPTIONS")      # E: should fail

reveal_type(ExtendedMethod.GET)   # N: inherited, Literal['GET']
reveal_type(ExtendedMethod.PATCH) # N: own, Literal['PATCH']
