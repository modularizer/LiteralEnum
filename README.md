# LiteralEnum

> A proposal for a Python typing construct that provides **namespaced literal constants** which are **actual runtime values** and **statically type-checked as a finite `Literal` union**, using a **single source of truth**.

---
## Motivation

> Merge the best of what `StrEnum`'s runtime with `Literal`'s checktime

Python developers frequently need a small, finite set of **string values**. 
The following would be my preferences as to how the namespace should work.
I am interested to see who agrees.

1. accessing `.value` is annoying
   - `StrEnum` and `class HttpMethod(str, Enum):` already somewhat address this to make it less necessary
2. I think with `def handle(method: HttpMethod):`, `handle("GET")` should be fine, and should not cause type-checker warnings
   - This works when using `Literal` but not when using enums
3. I want a single source of truth
   - using both `Literal` and `StrEnum` can be powerful, but is also annoying and redundant and error-prone
4. I want `isinstance` to be a first class citizen
   - `isinstance` cannot be used with `Literal`
   - `isinstance("GET", MyStrEnum)` fails
5. I don't want the solution to feel hacky
   - I believe this is a common enough use case for the language syntax to support without much developer work

## Proposed Syntax
```python
from typing import LiteralEnum


class HttpMethod(LiteralEnum):
    GET = "GET"
    POST = "POST"
    DELETE = "DELETE"

# RUNTIME
assert isinstance(HttpMethod.GET, str)
assert HttpMethod.GET == "GET"
assert type(HttpMethod.GET) is str
assert HttpMethod.GET is "GET"

assert isinstance("GET", HttpMethod)
assert isinstance(HttpMethod.GET, HttpMethod)
assert not isinstance("git", HttpMethod)

options: list[HttpMethod] = list(HttpMethod)
options_by_name: dict[str, HttpMethod] = HttpMethod.mapping

# Static Checks
# HttpMethod should be treated like Literal["GET", "POST", "DELETE"] in static type checking
def handle(method: HttpMethod):
    pass

handle("GET") # good
handle(HttpMethod.GET) # good
handle("git") # bad
handle(HttpMethod.git) # AttributeError

# compatibility
assert HttpMethod("GET") == "GET"
```

## Requirements
1. **Namespaced access**
   - 1.1. Accessing attributes should work
       ```py
       method = HttpMethod.GET
       ```
   - 1.2. Accessing known variables should show the value through static type checking
       ```py
       method = HttpMethod.GET # the static type checker should know and show that method = "GET"
       ```
   - 1.3. Accessing known variables should show the type through static type checking
      ```py
       method = HttpMethod.GET # the static type checker should know and show that method: HttpMethod
       ```
   - 1.4. Static type checkers should know which attributes exist on HttpMethod
        ```py
       MethodType = HttpMethod # typing . or inspecting the type should show the options
       ```
   - 1.5. Accessing undefined attributes should raise an AttributeError
      ```py
       with pytest.raises(AttributeError):
            method = HttpMethod.got
       ```
   - 1.6. Accessing undefined attributes should result in static type checker warnings
      ```py
       with pytest.raises(AttributeError):
            method = HttpMethod.got  # static type checker should identify this as an error
       ```

2. **Namespace resolves true string values at runtime**
   - 2.1. Passes `==`
       ```python
       assert HttpMethod.GET == "GET"
       ```        

   - 2.2. Passes `isinstance`
       ```python
       assert isinstance(HttpMethod.GET, str)
       ```
     
   - 2.3. Prints as the string
       ```python
       assert str(HttpMethod.GET) == "GET"
       ```

   - 2.4. Repr as the string
       ```python
       assert repr(HttpMethod.GET) == "'GET'"
       ```
   
   - 2.5. Actually IS if type string (litmus test of simplicity)
       ```python
       # NOTE: I am fully aware the following check not ones a dev should actually be running
       # Clearly isinstance is known to be standard best practices
       # The following is a **litmus test** of simplicity, not a core requirement
       # This proves we are not doing something weird
       assert type(HttpMethod.GET) is str
       ```
     
   - 2.6. Actually IS if the literal (litmus test of simplicity)
       ```python
       # NOTE: I am fully aware the following checks are not ones a dev should actually be running
       # <input>:1: SyntaxWarning: "is" with 'str' literal. Did you mean "=="? is to be expected
       # The following is a litmus test of simplicity, not a core requirement 
       # This proves we are not doing something weird
       assert HttpMethod.GET is "GET"
       ```
   - 2.7. `json.dumps` should succeed
   
3. **The class can be used as a static type hint**
      - 3.1 This should work
           ```python
           def handle_request(method: HttpMethod) -> None:
                pass
           ```

      - 3.2. Typehints should allow namespace values to be passed in
          ```python
           handle_request(HttpMethod.GET)          # accepted by static type checker
           ```

      - 3.3. Typehints should allow variables to be passed in
          ```python
           x = HttpMethod.GET
           handle_request(x)          # accepted by static type checker
           ```
      
      - 3.4. Typehints should allow literals to be passed in, 
      NOT require it to come from the namespace, as long as the value is in the namespace
          ```python
           handle_request("GET")          # accepted by static type checker
           ```
      
      - 3.5. Typehints should warn for unknown values
          ```python
           handle_request("got")          # rejected by static type checker
           ```
      
      - 3.6. Typehints should warn for unknown values of the broader type
           ```python
           x: str = "got"
           handle_request(x)          # rejected by static type checker
           ```
      
      - 3.7. Typehints should pass for this
           ```python
           x = "GET"
           handle_request(x)          # accepted by static type checker
           ```
    
      - 3.8. Typehints should fail if a variable is interntionally typed to be generic
           ```python
           x: str = "GET"
           handle_request(x)          # rejected by static type checker
           ```

4. **Single source of truth of the literal**
   Each string literal (`"GET"`, `"POST"`, etc.) is written exactly once in the source code where the type is defined.

5. **There should be SOME way to iterate through the namespace**
    - 5.1. Should be easy to verify a string is in the options
      - maybe support one of the following
        - `options = [x for x in HttpMethod.__args__]` or 
        - `options = [x for x in HttpMethod.values()]` or
        - `options = [x for x in HttpMethod]`
      - as long as there is SOME standard and simple way to do this that should be fine
      - the options should be correctly typed to be `Iterable[HttpMethod]`
    - 5.2. would be nice if `isinstance("GET", HttpMethod)` passed
      - this is a bit in conflict with 2.5. and 2.6.

6. **One class, not two**
   It is preferable if the SAME type is used for namespace access and for type hinting.
   e.g. `x: HttpMethod = HttpMethod.GET` NOT `x: HttpMethodType = HttpMethodNamespace.GET`

7. **Not just strings**
   While `str` is I think the most painful and hence the focus, the LiteralEnum should support other literal values such as `bool | int | float | None`

---

## Existing Solutions (and why they are insufficient)

This section evaluates common approaches against the requirements listed above. In particular, the hardest combination to satisfy simultaneously is:

* **1.x** (a real namespace with known attributes and static attribute checking)
* **2.x** (members behave like *true* runtime strings)
* **3.x** (the namespace type accepts both namespace members *and* raw string literals, while rejecting unknown values)
* **4** (single source of truth)
* **6** (one class, not two)
* **7** (not limited to strings)

### 1) `StrEnum`

```py
from enum import StrEnum
import pytest

class HttpMethod(StrEnum):
    GET = "GET"
    POST = "POST"

def handle_request(method: HttpMethod) -> None:
    pass

handle_request(HttpMethod.GET)  # ✅
handle_request("GET")           # ❌ (static type error)
```

**Passes**

* **1.1 / 1.4 / 1.5 / 1.6**: Namespaced attributes exist, are discoverable, and unknown attributes are rejected both statically and at runtime.
* **2.1 / 2.2**: Members compare equal to strings and pass `isinstance(..., str)`.
* **3.1 / 3.2 / 3.3**: Works when callers pass enum members or variables holding enum members.
* **4**: Values are written once, in the enum definition.
* **5**: Iteration is supported (`for x in HttpMethod`).
* **6**: One class is used for both the namespace and the annotation.
* **7**: Can be generalized via `IntEnum`, `Enum`, etc.

**Fails / tradeoffs**

* **2.3 / 2.4**: By default, stringification/representation often show the enum member name (`"HttpMethod.GET"`) unless customized with `__str__`/`__repr__`.
* **2.5 / 2.6 (litmus tests)**: Members are *not* literally `str` objects (`type(HttpMethod.GET) is not str`) and will not be identical to a string object (`HttpMethod.GET is "GET"`).
* **3.4 / 3.7**: Call sites cannot pass raw string literals/values to a function annotated `HttpMethod` without widening the annotation.
* **3.6 / 3.8**: If the function is widened to accept `str`, static rejection of unknown values becomes much harder.

**Bottom line:** `StrEnum` provides a great namespace (1.x), but it does not allow **raw `"GET"`** to type-check as `HttpMethod` (3.4/3.7), which is a central requirement for many string-centric APIs.

---

### 2) `Literal[...]` (type alias only)

```py
from typing import Literal

HttpMethod = Literal["GET", "POST"]

def handle_request(method: HttpMethod) -> None:
    pass

handle_request("GET")  # ✅
handle_request("got")  # ❌
```

**Passes**

* **2.1 / 2.2 / 2.3 / 2.4**: Values are plain strings at runtime.
* **3.1 / 3.4 / 3.5 / 3.7**: Type checker accepts allowed literals and rejects unknown ones.
* **3.6 / 3.8**: Type checker rejects values typed as plain `str` (because they might be anything).
* **4**: Values are written once (in the alias).

**Fails / tradeoffs**

* **1.1 / 1.4**: No namespace attributes (`HttpMethod.GET` does not exist).
* **1.5 / 1.6**: No attribute access to fail (there are no attributes).
* **5**: You can often get values via `typing.get_args(HttpMethod)`, but the mechanism is not standardized as a runtime “enum-like” iteration API and differs by type-checker/runtime usage expectations.
* **6**: The name is a type alias, not a value namespace.
* **7**: Works for other literal types, but still lacks a namespace.

**Bottom line:** `Literal[...]` gives excellent static checking for raw values (3.x) and true runtime literals (2.x), but it is not a namespace (1.x, 6).

---

### 3) Constants + `Literal[...]` (two namespaces)

```py
from typing import Literal

class HttpMethod:
    GET = "GET"
    POST = "POST"

HttpMethodType = Literal["GET", "POST"]
```

**Passes**

* **1.1 / 1.4 / 1.5 / 1.6** (for the `class HttpMethod`): Namespaced constants exist and unknown attributes can be caught.
* **2.1 / 2.2 / 2.3 / 2.4**: Members are true strings.
* **3.x** (for `HttpMethodType`): Strong static checking is possible for literals.
* **4** (arguably): values can be written once *if* `HttpMethodType` is derived from the constants (but see below).
* **7**: Can be generalized to other literal types.

**Fails / tradeoffs**

* **6**: Violates “one class, not two” — you end up with `HttpMethod` (namespace) and `HttpMethodType` (type), which splits the concept.
* **1.2 / 1.3**: Type checkers generally won’t simultaneously show both “this is the literal `"GET"`” and “this is of type `HttpMethodType`” for `HttpMethod.GET` unless you heavily annotate and accept checker-specific behavior.
* **4** (in practice): if you write `HttpMethodType = Literal["GET", "POST"]`, you’ve duplicated the literals. If you try `Literal[HttpMethod.GET, HttpMethod.POST]`, some checkers won’t treat that as equivalent to `Literal["GET","POST"]`, and it becomes brittle.
* **5**: Iteration requires custom work (it’s just a class with attributes).

**Bottom line:** This can approximate the desired runtime behavior and static checking, but it typically requires **two different names** (type vs namespace) or ends up duplicating literals / relying on checker quirks.

---

### 4) Runtime validation

```py
def handle_request(method: str) -> None:
    if method not in {"GET", "POST"}:
        raise ValueError
```

**Passes**

* **2.x**: Plain runtime strings.
* **4**: Values can be written once (in the validation set).
* **5.1**: Easy membership checks and iteration (`{"GET", "POST"}`).

**Fails / tradeoffs**

* **3.4 / 3.5**: Type checker cannot reject unknown values at call sites because the parameter is `str`.
* **3.6 / 3.8**: Type checker cannot distinguish `str` variables that happen to contain allowed values from those that don’t.
* **1.x / 6**: No unified namespace/type object unless you add additional constructs, which reintroduces duplication or splitting.

**Bottom line:** Runtime validation can be pragmatic, but it does not provide the static guarantees that motivate `LiteralEnum` (3.x), and it does not naturally produce a unified namespace/type (6).


Below are additional “Existing Solutions” analyses for:

1. **`class HttpMethod(str, Enum)`**
2. **Your `Literal[...]` + attribute injection hack** (shown with `HttpMethod`)
3. **Two custom patterns** people often reach for (and why they still miss key requirements)

I’m keeping the same “passes/fails vs your requirements” style.

---

### 5) `Enum` with `str` mixin (`class HttpMethod(str, Enum)`)

```py
from enum import Enum
import pytest

class HttpMethod(str, Enum):
    GET = "GET"
    POST = "POST"

def handle_request(method: HttpMethod) -> None:
    pass

handle_request(HttpMethod.GET)  # ✅
handle_request("GET")           # ❌ (static type error)
assert HttpMethod.GET == "GET"  # ✅ (runtime)
assert isinstance(HttpMethod.GET, str)  # ✅ (runtime)

with pytest.raises(AttributeError):
    _ = HttpMethod.got  # ✅ static error + runtime error
```

**Passes**

* **1.1 / 1.4 / 1.5 / 1.6**: Namespace attributes exist; unknown attributes can be caught statically and raise at runtime.
* **2.1 / 2.2**: Equality to string and `isinstance(..., str)` pass.
* **3.1 / 3.2 / 3.3**: Passing enum members works.
* **4**: Values written once in the enum definition.
* **5**: Easy to iterate (`for m in HttpMethod:`).
* **6**: One class is used for both namespace and type hint.
* **7**: Generalizes naturally (can use `int`, etc., though `int` + `Enum` uses `IntEnum` typically).

**Fails / tradeoffs**

* **2.3 / 2.4**: `str(HttpMethod.GET)` may not be `"GET"` without customizing `__str__`. `repr()` is also typically `"HttpMethod.GET"`.
* **2.5 / 2.6 (litmus)**: `type(HttpMethod.GET) is not str`, and identity checks against `"GET"` won’t pass.
* **3.4 / 3.7**: `"GET"` is not accepted as `HttpMethod` in static typing (core pain point).
* **3.6 / 3.8**: If you widen the function to accept `str`, you lose static rejection power.

**Bottom line:** This is effectively the same story as `StrEnum` for typing: great namespace, but it does not accept raw string literals where `HttpMethod` is expected.

---

### 6) `Literal[...]` + attribute injection hack

In today's python, the following gets somewhat close to meeting many requirements, but is non-standard and has big drawbacks.

```py
from typing import Literal

HttpMethod = Literal["GET", "POST", "DELETE"]

HttpMethod.GET: HttpMethod = "GET"
HttpMethod.POST: HttpMethod = "POST"
HttpMethod.DELETE: HttpMethod = "DELETE"

def handle_request(method: HttpMethod) -> None:
    pass

handle_request("GET")           # ✅
handle_request(HttpMethod.GET)  # ✅
handle_request("PATCH")         # ❌ static error
```

**Passes**

* **1.1**: Attribute access works (`HttpMethod.GET`) after assignment.
* **1.4**: Many IDEs will show the attributes once they’re attached.
* **1.5**: Unknown attributes raise `AttributeError` at runtime.
* **1.6**: Unknown attributes *can* be caught statically if the checker indexes attributes on that object (often works in practice).
* **2.1 / 2.2 / 2.3 / 2.4**: Values are plain strings; printing/`repr` are normal strings.
* **2.5 / 2.6 (litmus)**: This can satisfy your “simplicity” litmus tests because the values literally are string objects.
* **3.1–3.5 / 3.7**: This is the standout: `HttpMethod` works as a finite literal union; `"GET"` passes; `"PATCH"` fails; `HttpMethod.GET` passes.
* **4**: You write each literal once (in the `Literal[...]` list), and the attributes are assigned to reuse those values.
* **6**: One name `HttpMethod` is both the type and the namespace.
* **7**: Works for other literal types too (`Literal[1,2]` etc.), at least conceptually.

**Fails / tradeoffs**

* **1.2 / 1.3**: Type checker “reveal” behavior is inconsistent: some tools will show `method: Literal["GET"]`, others show `method: HttpMethod`, others both; there’s no standardized expectation.
* **1.4** (reliability): whether “dot completion / inspection” works depends heavily on IDE + checker heuristics, because you’re attaching attrs to a typing object.
* **5**: Iteration is not standardized. You can usually do `typing.get_args(HttpMethod)` to recover the values, but that’s a typing-introspection API, not a normal runtime “enum” interface.
* **Stability / Spec:** This relies on runtime mutation of a `typing` construct. It’s not a pattern the typing spec guarantees will remain supported or consistent across Python/checker versions.

**Bottom line:** In terms of *your requirement list*, this is the closest match today with no external tooling. The main downside is that it relies on behavior that is not formally specified as a supported “namespace pattern” for typing objects.

---

### 7) Custom solution: “class namespace + `TypeAlias` literal” (two names)

```py
from typing import Literal, TypeAlias, Final

class HttpMethod:
    GET: Final = "GET"
    POST: Final = "POST"

HttpMethodType: TypeAlias = Literal["GET", "POST"]

def handle_request(method: HttpMethodType) -> None:
    pass
```

**Passes**

* **1.1 / 1.4 / 1.5 / 1.6**: Great namespace behavior (normal class attributes).
* **2.x / 2.5 / 2.6**: Plain strings.
* **3.x**: Strong static checking on the type alias.
* **4**: Can be single source of truth *if* the literal union is derived without rewriting strings (but see below).
* **5**: You can implement an iterator / `.values()` easily.

**Fails**

* **6**: Violates “one class, not two” (split between namespace and type).
* **4** (in practice): keeping the `Literal[...]` perfectly in sync with the class constants without duplication is difficult without relying on checker-specific behavior.

**Bottom line:** This is the most conventional “no hack” approach, but it fails requirement **6** (unified name) and often **4** (single source of truth) in practice.

---

### 8) Custom solution: “overload accepts literals + enum members” (requires writing literals twice)

```py
from typing import Literal, overload
from enum import Enum

class HttpMethod(str, Enum):
    GET = "GET"
    POST = "POST"

HttpMethodLiteral = Literal["GET", "POST"]

@overload
def handle_request(method: HttpMethod) -> None: ...
@overload
def handle_request(method: HttpMethodLiteral) -> None: ...

def handle_request(method) -> None:
    pass
```

**Passes**

* **1.x**: Namespace works via the enum.
* **3.2 / 3.4**: Accepts both `HttpMethod.GET` and `"GET"` statically.
* **5**: Enum iteration works.
* **6**: Still one canonical namespace name for values.

**Fails**

* **4**: Literal strings are written twice (in the enum and in the literal alias), unless you add tooling.
* **3.6 / 3.8**: Still rejects `x: str = "GET"` as intended, but you haven’t solved single source of truth.
* **7**: Can generalize, but duplication persists.

**Bottom line:** Works nicely for call sites, but violates your “write literals once” requirement unless you add stubs/codegen/plugins.

---

## Summary

Each existing approach covers part of the requirements, but none satisfies the full combination:

`StrEnum` gets the closest,


