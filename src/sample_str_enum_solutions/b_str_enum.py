import json
from enum import Enum

import pytest


class HttpMethod(str, Enum):
    GET = "GET"
    POST = "POST"


def handle(method: HttpMethod) -> None:
    print(f"{method=}")

if __name__ == "__main__":
    # CONS
    handle("GET") # warning => ❌ bad
    print(repr(HttpMethod.GET)) # "<HttpMethod.GET: 'GET'>" => I don't love this
    print(str(HttpMethod.GET)) # 'HttpMethod.GET' => I don't love this

    # PROS
    print(json.dumps(HttpMethod.GET)) # => '"GET"'
    handle(HttpMethod.GET) # no warning => ✅ good
    handle("got") # warning => ✅ good
    assert isinstance(HttpMethod.GET, str) # passes => ✅ good
    assert HttpMethod.GET == "GET" # passes => ✅ good
    with pytest.raises(AttributeError):
        handle(HttpMethod.got) # warning AND runtime AttributeError => ✅ good
