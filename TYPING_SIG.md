**Subject:** Proposal: LiteralEnum — runtime literals with static exhaustiveness

Hello typing community,

I’d like feedback on a possible typing construct tentatively called **`LiteralEnum`**, aimed at a common gap between `Enum` and `typing.Literal`.

**Problem**
Many APIs use small, closed sets of scalar values (often strings: HTTP methods, event names, config keys). At runtime, these are most ergonomic as *plain literals*, but statically we want *exhaustiveness checking*.

Today this usually leads to duplication, e.g. a constants namespace plus a parallel `Literal[...]` union, or forcing callers to pass enum members instead of raw values.

**Proposed idea**
`LiteralEnum` defines a finite, named set of literal values that:

* are plain runtime literals (`str`, `int`, `bool`, `None`, etc.),
* provide a runtime namespace, iteration, and validation, and
* are treated by type checkers as an exhaustive `Literal[...]` union.
* This is not intended to replace Enum or Literal, but to cover the narrow case where literal values themselves are the API surface.

Minimal example:

```python
from typing import LiteralEnum

class HttpMethod(LiteralEnum):
    GET = "GET"
    POST = "POST"
    DELETE = "DELETE"

def handle(method: HttpMethod) -> None:
    ...

handle("GET")          # accepted
handle(HttpMethod.GET) # accepted
handle("git")          # type checker error
```

At runtime:

* `HttpMethod.GET == "GET"`
* `list(HttpMethod) == ["GET", "POST", "DELETE"]`
* `HttpMethod("GET")` validates and returns `"GET"`

At type-check time, `HttpMethod` is equivalent to:

```python
Literal["GET", "POST", "DELETE"]
```

Subclass extension is explicit (`extend=True`) to avoid accidental widening.

**Status**

* I have a small runtime prototype as a proof of concept (linked below, under 200 lines); it does not attempt to solve the type-checker side yet
* I’m interested in whether this direction seems:

  * useful enough to justify checker support, and
  * compatible with existing typing model assumptions.

Draft PEP (early): https://github.com/modularizer/LiteralEnum/blob/master/PEP.md
Runtime prototype: https://github.com/modularizer/LiteralEnum/blob/master/src/typing_literalenum.py

I’m not attached to the name or the source code, I'm looking to validate the *concept* and scope before going further.

Questions for discussion:
1. Do other people feel this pain point as much as me?
2. Have you found yourself writing duplicate types: a (`Literal` plus an `Enum` or just a bare class with attributes)?


Thanks for any feedback,
Torin
