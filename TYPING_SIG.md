Here’s a **ready-to-send** initial email. It’s intentionally short, concrete, and non-defensive, which tends to work best on typing-sig.

---

**Subject:** Proposal: `LiteralEnum` — named runtime literals with static exhaustiveness

Hello typing-sig,

I’d like feedback on a possible typing construct tentatively called **`LiteralEnum`**, aimed at a common gap between `Enum` and `typing.Literal`.

**Problem**
Many APIs use small, closed sets of scalar values (often strings: HTTP methods, event names, config keys). At runtime, these are most ergonomic as *plain literals*, but statically we want *exhaustiveness checking*.

Today this usually leads to duplication, e.g. a constants namespace plus a parallel `Literal[...]` union, or forcing callers to pass enum members instead of raw values.

**Proposed idea**
`LiteralEnum` defines a finite, named set of literal values that:

* are plain runtime literals (`str`, `int`, `bool`, `None`, etc.),
* provide a runtime namespace, iteration, and validation, and
* are treated by type checkers as an exhaustive `Literal[...]` union.

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

* I have a working runtime implementation.
* I’m interested in whether this direction seems:

  * useful enough to justify checker support, and
  * compatible with existing typing model assumptions.

Draft PEP (early): <LINK>
Runtime prototype: <LINK>

I’m not attached to the name or exact surface API—mostly looking to validate the *concept* and scope before going further.

Thanks for any feedback,
Torin

