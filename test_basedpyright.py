"""Test file for basedpyright LiteralEnum support."""
from typing_literalenum import LiteralEnum


class HttpMethod(LiteralEnum):
    GET = "GET"
    POST = "POST"
    DELETE = "DELETE"


# Test 1: Member access should be Literal["GET"]
method = HttpMethod.GET
reveal_type(method)  # Should be Literal["GET"]

# Test 2: Annotation should expand to literal union
def handle(method: HttpMethod) -> None:
    reveal_type(method)  # Should be Literal["GET"] | Literal["POST"] | Literal["DELETE"]
    pass

# Test 3: Literal value should be assignable
x: HttpMethod = "GET"  # Should be OK

# Test 4: Invalid literal should be rejected
y: HttpMethod = "PATCH"  # Should be an error

# Test 5: Direct call
handle("GET")  # Should be OK
handle("PATCH")  # Should be an error
