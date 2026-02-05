# What if one object could be a namespace AND a typehint?

```python
# Wouldn't it be nice if this worked?
from typing import LiteralEnum

class HttpMethod(LiteralEnum):
    GET = "GET"
    POST = "POST"

def handle(method: HttpMethod) -> None: ...  # when used as a typehint, HttpMethod would behave like Literal["GET", "POST"]

# core
handle("GET")                # type-checks: "GET" is a valid HttpMethod
handle(HttpMethod.POST)      # type-checks: HttpMethod.POST is just "POST"
handle("PATCH")              # type error: not a valid HttpMethod
assert list(HttpMethod) == ["GET", "POST"]
assert "GET" in HttpMethod   # runtime validation

# NOTHING fancy, value is JUST the literal, not a subclass, not an instance of HttpMethod, not an instance of LiteralEnum, not modified in any way
assert HttpMethod.GET == "GET" and type(HttpMethod.GET) is str and HttpMethod.GET.__class__.__bases__ == (object,)

HttpMethod.validate(x)       # raises ValueError if invalid
assert dict(HttpMethod.mapping) == {"GET": "GET", "POST": "POST"}
assert HttpMethod.names_by_value[HttpMethod.POST] == "POST"
```

One definition. Plain raw literals at runtime. Exhaustive checking at type-check time. 

- A realistic runtime version is available at `pip install literalenum` (but is not as good as advertised above)
- Support in the [Python Community Discussion](https://discuss.python.org/t/proposal-literalenum-runtime-literals-with-static-exhaustiveness/106000/15) 
  would be needed to have a shot at a PEP that could improve Python
