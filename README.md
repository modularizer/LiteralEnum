# PEP XXX: LiteralEnum — Namespaced Runtime Literals with Static Exhaustiveness Checking

| PEP            | XXX                                                                           |
| -------------- |-------------------------------------------------------------------------------|
| Title          | LiteralEnum — Namespaced Runtime Literals with Static Exhaustiveness Checking |
| Author         | *Torin Halsted*                                                               |
| Status         | Draft                                                                         |
| Type           | Standards Track                                                               |
| Topic          | Typing                                                                        |
| Created        | 2026-02-03                                                                    |
| Python-Version | TBD                                                                           |
| Post-History   | TBD                                                                           |

---

## Abstract

This PEP proposes a new typing construct, `LiteralEnum`, that defines a **finite set of literal values** with:

* a **runtime namespace** (attribute access, iteration, validation),
* **true runtime values** (e.g. actual `str`, `int`, `bool`, or `None` objects),
* and **precise static type checking** equivalent to a `Literal[...]` union.

A `LiteralEnum` allows a single definition to serve simultaneously as:

* a namespace of named constants,
* a runtime validator and iterable of allowed values,
* and a static type that accepts only those values.

This construct addresses a common Python pattern—small, closed sets of string or scalar constants—without requiring duplication between `Enum` and `Literal`, checker-specific plugins, or separate runtime and typing definitions.

---

## Motivation

Python programs frequently rely on small, finite sets of values—such as HTTP methods, event names, command identifiers, status strings, configuration keys, or protocol fields—that are most naturally represented as **plain literals at runtime** but benefit from **exhaustive checking at type-check time**.

Today, developers must choose between two incomplete options:

* **`Enum` / `StrEnum`**, which provide a runtime namespace and iteration, but require passing enum members rather than raw literal values in typed APIs; or
* **`Literal[...]`**, which enables precise static checking of raw values, but provides no runtime namespace, iteration, or validation mechanism.

As a result, common APIs face an ergonomic mismatch:

```python
def handle_request(method: HttpMethod) -> None: ...
handle_request("GET")  # rejected with Enum, accepted with Literal
```

To bridge this gap, developers frequently resort to:

* duplicating values across a runtime enum and a `Literal` union,
* maintaining parallel “value” and “type” definitions,
* widening annotations to `str` and adding runtime validation,
* or relying on checker-specific behavior or undocumented patterns.

These approaches are verbose, error-prone, and obscure intent. They also violate the principle of a **single source of truth**, making refactors and extensions risky.

The core problem is that Python currently lacks a construct that directly represents:

> *a finite, named set of literal runtime values that is also statically exhaustive.*

`LiteralEnum` directly models this concept.

---

## Example

```python
from typing import LiteralEnum

class HttpMethod(LiteralEnum):
    GET = "GET"
    POST = "POST"
    DELETE = "DELETE"

def handle(method: HttpMethod) -> None:
    ...

handle("GET")            # accepted
handle(HttpMethod.GET)   # accepted
handle("git")            # type checker error
```

At runtime:

* `HttpMethod.GET` is the string `"GET"`,
* `isinstance("GET", HttpMethod)` is true,
* iteration yields the allowed values,
* and calling `HttpMethod(value)` validates membership.

At type-check time, `HttpMethod` is treated as equivalent to:

```python
Literal["GET", "POST", "DELETE"]
```

derived directly from the class definition.

---

## Goals

`LiteralEnum` is designed to:

* Provide **namespaced access** to a finite set of literals (e.g. `HttpMethod.GET`).
* Ensure members are **actual runtime literals**, not wrapper objects.
* Allow APIs annotated with a `LiteralEnum` to accept both:

  * namespace members (e.g. `HttpMethod.GET`), and
  * raw literal values (e.g. `"GET"`),
    while rejecting unknown values.
* Serve as a **single source of truth** for runtime behavior and static typing.
* Support **iteration, membership testing, and validation** at runtime.
* Support literal types beyond strings, including `int`, `bool`, and `None`.

---

## Non-Goals

This PEP does not:

* Introduce a general mechanism for arbitrary alternate static interpretations of runtime objects.
* Require type checkers to execute user code.
* Replace `Enum`, `StrEnum`, or `Literal`; it complements them for a specific, common use case.
* Change Python’s runtime type system or literal semantics.
* Guarantee object identity between members and literal constants (e.g. `x is "GET"`).

---

## Rationale

The absence of a construct representing “a finite set of runtime literals with names” has led to widespread patterns that split runtime values from static types.

While `Enum` emphasizes identity and membership, and `Literal` emphasizes exhaustiveness, many real-world APIs require **both simultaneously**. In particular, string-centric protocols and configuration values are most ergonomic when passed as plain literals, yet benefit greatly from static exhaustiveness checking.

`LiteralEnum` occupies a narrow but important middle ground:

* **At runtime**, it behaves as a namespace and validator over literal values.
* **In type positions**, it is treated as a `Literal[...]` union derived from its declared members.

By standardizing this pattern, Python can eliminate a class of boilerplate, reduce duplication, and improve both readability and correctness across a wide range of applications.

---

## Specification

### Overview

`LiteralEnum` is a base class in the `typing` module. Subclassing `LiteralEnum` defines a **finite set of members** declared as class attributes. These declared members:

* are **runtime literal values** (e.g. `str`, `int`, `bool`, `None`, `bytes`, optionally `float`),
* are accessible by name on the class (e.g. `HttpMethod.GET`),
* and determine the **static type interpretation** of the subclass, which type checkers must treat as an equivalent `typing.Literal[...]` union of the declared values.

In type positions, a `LiteralEnum` subclass is treated as:

```python
Literal[v1, v2, ...]
```

where `v1..vn` are the member values declared on the class.

### Declaring Members

A subclass of `LiteralEnum` declares members using class attributes:

```python
class HttpMethod(LiteralEnum):
    GET = "GET"
    POST = "POST"
```

A class attribute is considered a `LiteralEnum` member if it meets all of the following:

1. The attribute name is a valid identifier and does not start with `_`.
2. The attribute value is a **supported literal value** (see below).
3. The attribute is defined directly in the class body (not via runtime mutation).

Type checkers should consider only statically visible assignments in the class body. Runtime assignment to add new members is not supported.

#### Supported Literal Value Types

Member values MUST be one of:

* `str`
* `bytes`
* `int`
* `bool`
* `None`

Member values MAY include `float`, but type checkers and the runtime MUST be consistent about whether `float` is permitted. (See “Open Issues”.)

Type checkers MUST reject member values that are not statically evaluable literals of a supported type.

### Static Type Interpretation

In type positions, a `LiteralEnum` subclass `E` MUST be interpreted by type checkers as:

```python
Literal[<member values of E>]
```

For example:

```python
class HttpMethod(LiteralEnum):
    GET = "GET"
    POST = "POST"
    DELETE = "DELETE"
```

Type checkers must treat `HttpMethod` as equivalent to:

```python
Literal["GET", "POST", "DELETE"]
```

This implies:

* Passing a matching literal is accepted:

  ```python
  def handle(m: HttpMethod) -> None: ...
  handle("GET")  # OK
  ```

* Passing a non-member literal is rejected:

  ```python
  handle("git")  # error
  ```

* Passing a value typed as the broader base type (e.g. `str`) is rejected unless it is a known literal:

  ```python
  x: str = "GET"
  handle(x)  # error
  y = "GET"
  handle(y)  # OK (y inferred as Literal["GET"])
  ```

### Runtime Semantics

#### Member Values

Each member attribute evaluates at runtime to the literal value assigned:

```python
assert HttpMethod.GET == "GET"
assert isinstance(HttpMethod.GET, str)
assert type(HttpMethod.GET) is str
```

`LiteralEnum` does not introduce wrapper objects for members.

#### Validation / Construction

Calling a `LiteralEnum` subclass as a function validates membership and returns the passed value:

```python
assert HttpMethod("GET") == "GET"
HttpMethod("git")  # raises ValueError
```

The raised `ValueError` message SHOULD include the allowed values in a readable form.

#### Iteration

Iterating over a `LiteralEnum` subclass yields the member values in definition order:

```python
list(HttpMethod) == ["GET", "POST", "DELETE"]
```

The iteration result SHOULD be typed as `Iterator[HttpMethod]` by type checkers.

#### Membership Testing

Membership MAY be supported as:

```python
"GET" in HttpMethod  # True
"git" in HttpMethod  # False
```

If supported, membership MUST test against the set of member values using normal equality (`==`) and must preserve `bool`/`int` distinctions (see below).

#### `isinstance`

A `LiteralEnum` subclass SHOULD support:

```python
isinstance("GET", HttpMethod)        # True
isinstance(HttpMethod.GET, HttpMethod)  # True
isinstance("git", HttpMethod)        # False
```

This is achieved via metaclass instance checking; it does not require member values to have runtime type `HttpMethod`.

Implementations MUST ensure correct behavior for `bool` values, since `bool` is a subclass of `int` and `True == 1` is `True`. Membership and `isinstance` checks MUST treat `True` and `1` as distinct member values.

### Introspection API

A `LiteralEnum` subclass MUST expose a mapping of member names to values:

```python
HttpMethod.mapping == {"GET": "GET", "POST": "POST", "DELETE": "DELETE"}
```

The `.mapping` attribute MUST be a `dict[str, HttpMethod]` (or `Mapping[str, HttpMethod]` if returned as a view).

A `LiteralEnum` subclass SHOULD expose the ordered member values as:

```python
HttpMethod.values()  # returns an iterable of member values
```

or alternatively via a standardized attribute:

```python
HttpMethod.__members__  # mapping of names to values (similar to Enum)
```

The final API surface (e.g. `.mapping` vs `__members__`) is specified in “Open Issues”.

---

## Type Checker Behavior

### Attribute Checking

Type checkers MUST:

* Provide attribute completion / checking for declared members:

  ```python
  HttpMethod.GET  # OK
  HttpMethod.got  # error
  ```

* Treat access to a declared member as both:

  * the specific literal value, and
  * the `LiteralEnum` type.

Concretely, for:

```python
x = HttpMethod.GET
```

type checkers SHOULD infer:

* `x` has type `HttpMethod` (equivalently `Literal["GET"]`),
* and can reveal the value `"GET"` as a `Literal` if the checker supports value display.

### Exhaustiveness / Narrowing

Type checkers SHOULD allow narrowing when comparing against member values, consistent with normal `Literal` unions:

```python
def f(m: HttpMethod) -> None:
    if m == "GET":
        ...
    else:
        ...
```

Type checkers MAY support exhaustiveness checking in `match` statements as for `Literal` unions:

```python
def f(m: HttpMethod) -> int:
    match m:
        case "GET":
            return 1
        case "POST":
            return 2
        case "DELETE":
            return 3
```

---

## Backwards Compatibility

This PEP adds a new construct. It does not change runtime behavior of existing programs.

Because `LiteralEnum` members are plain literals, it composes naturally with existing code expecting base types such as `str` or `int`.

---

## Reference Implementation

A reference implementation consists of:

1. A runtime implementation of `LiteralEnum` (likely via a metaclass) providing:

   * member collection,
   * iteration,
   * membership testing,
   * `isinstance` support,
   * `E(value)` validation,
   * and member mapping introspection.

2. Type checker support to interpret `LiteralEnum` subclasses as `Literal[...]` unions derived from class members.

A provisional implementation can be shipped in `typing_extensions` to enable experimentation and early checker adoption before inclusion in `typing`.

---

## Rejected Alternatives

This section summarizes common approaches and why they do not satisfy the goals of this PEP.

### `StrEnum` and `Enum`-based Solutions

`StrEnum` and `Enum`-based patterns provide excellent namespacing and iteration, but require enum members at call sites and do not allow raw literals to type-check as the enum type:

```python
def handle(m: HttpMethod) -> None: ...
handle("GET")  # rejected by type checkers
```

They also produce member objects that are not plain literals at runtime.

### `Literal[...]` Type Aliases

`Literal[...]` provides precise static checking of raw values but provides no runtime namespace (`HttpMethod.GET`), no iteration API, and no runtime validation.

### Parallel Namespace + Type Alias

Defining both a constant namespace and a `Literal[...]` alias introduces duplication and violates the “single source of truth” goal.

### Runtime Validation of `str`

Accepting `str` and validating membership at runtime is pragmatic but loses static rejection of unknown values and does not support exhaustiveness checking.

---

## Open Issues

1. **`float` membership**

   * `Literal` allows floats, but floats have edge cases (`NaN`, `-0.0`, rounding). This PEP must decide whether to include `float` values as supported members.

2. **Introspection surface**

   * Should the standardized mapping attribute be named `__members__` (like `Enum`), `.mapping`, or both?
   * Should `.values()` / `.items()` / `.keys()` be standardized?

3. **Iteration order**

   * This PEP specifies definition order. Confirm whether base-class member inheritance should append, override, or disallow duplicates.

4. **Duplicate values**

   * Should duplicate member values be permitted with different names?
   * If permitted, how should `.mapping` behave?

5. **Subclassing and inheritance**

   * Should subclasses inherit members from base `LiteralEnum` classes?
   * If yes, what are the rules for overriding names and values?


