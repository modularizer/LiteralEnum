# PEP XXX: LiteralEnum — Namespaced Runtime Literals with Static Exhaustiveness Checking

| PEP            | XXX                                                                           |
| -------------- | ----------------------------------------------------------------------------- |
| Title          | LiteralEnum — Namespaced Runtime Literals with Static Exhaustiveness Checking |
| Author         | Torin Halsted                                                                 |
| Status         | Draft                                                                         |
| Type           | Standards Track                                                               |
| Topic          | Typing                                                                        |
| Created        | 2026-02-03                                                                    |
| Python-Version | TBD                                                                           |
| Post-History   | TBD                                                                           |

---

## Abstract

This PEP proposes a new typing construct, `LiteralEnum`, for defining **finite, named sets of literal values** that:

* behave as **ordinary runtime literals** (e.g. `str`, `int`, `bool`, `None`),
* provide a **runtime namespace** with iteration, validation, and membership testing, and
* are interpreted by type checkers as an **exhaustive `typing.Literal[...]` union**.

A `LiteralEnum` definition serves simultaneously as:

* a namespace of named constants,
* a runtime validator and iterable of allowed values, and
* a static type that accepts only those values.

This construct addresses a common Python pattern—small, closed sets of string or scalar constants—without requiring duplication between `Enum` and `Literal`, checker-specific plugins, or parallel runtime and typing definitions.

---

## Motivation

Python programs frequently rely on small, finite sets of values—such as HTTP methods, event names, command identifiers, status strings, configuration keys, or protocol fields—that are most naturally represented as **plain literals at runtime**, but benefit from **exhaustive checking at type-check time**.

Today, developers must choose between two incomplete options:

* **`Enum` / `StrEnum`**, which provide a runtime namespace and iteration, but require passing enum members rather than raw literal values in typed APIs; or
* **`Literal[...]`**, which enables precise static checking of raw values, but provides no runtime namespace, iteration, or validation mechanism.

This leads to an ergonomic mismatch in common APIs:

```python
def handle_request(method: HttpMethod) -> None: ...
handle_request("GET")  # rejected with Enum, accepted with Literal
```

To bridge this gap, developers frequently resort to:

* duplicating values across a runtime enum and a `Literal` union,
* maintaining parallel “value” and “type” definitions,
* widening annotations to `str` and adding runtime validation, or
* relying on checker-specific behavior or undocumented patterns.

These approaches are verbose, error-prone, and obscure intent. They violate the principle of a **single source of truth**, making refactors and extensions risky.

The core problem is that Python lacks a construct that directly represents:

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

class MoreHttpMethods(HttpMethod, extend=True):
    PATCH = "PATCH"
    PUT = "PUT"
    OPTIONS = "OPTIONS"
    HEAD = "HEAD"
    TRACE = "TRACE"

def handle(method: HttpMethod) -> None:
    ...

handle("GET")            # accepted
handle(HttpMethod.GET)   # accepted
handle("git")            # type checker error
```

### Semantics

At runtime:

* `HttpMethod.GET` evaluates to the string `"GET"`,
* iteration yields the allowed unique values by strict equality, in declaration order,
* calling `HttpMethod(value)` validates membership and returns the literal value.

At type-check time, `HttpMethod` is treated as equivalent to:

```python
Literal["GET", "POST", "DELETE"]
```

Extending an existing `LiteralEnum` requires an explicit opt-in via `extend=True`, preventing accidental widening when subclassing.

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
* Support literal types beyond strings, including `int`, `bool`, `bytes`, and `None`.

---

## Non-Goals

This PEP does not:

* Introduce a general mechanism for arbitrary alternate static interpretations of runtime objects.
* Require type checkers to execute user code.
* Replace `Enum`, `StrEnum`, or `Literal`; it complements them for a specific, common use case.
* Change Python’s runtime type system or literal semantics.
* Guarantee object identity between members and literal constants (e.g. `x is "GET"`).
* Define `isinstance` semantics for literal values.
* Treat `LiteralEnum` classes as instantiable runtime object types

---

## Rationale

While `Enum` emphasizes identity and membership, and `Literal` emphasizes exhaustiveness, many real-world APIs require **both simultaneously**. In particular, string-centric protocols and configuration values are most ergonomic when passed as plain literals, yet benefit greatly from static exhaustiveness checking.

`LiteralEnum` occupies a narrow but important middle ground:

* **At runtime**, it behaves as a namespace and validator over literal values.
* **In type positions**, it is treated as a `Literal[...]` union derived from its declared members.

By standardizing this pattern, Python can eliminate a class of boilerplate, reduce duplication, and improve both readability and correctness.

---

## Specification

### Overview

`LiteralEnum` is a base class proposed to be provided by the `typing` module.

Subclassing `LiteralEnum` defines a **finite set of members** declared as class attributes. These members:

* are runtime literal values,
* are accessible by name on the class, and
* determine the static type interpretation of the subclass.

In type positions, a `LiteralEnum` subclass is interpreted as a `typing.Literal[...]` union of its declared values.

---

### Declaring Members

Members are declared using **UPPERCASE public class attributes**:

```python
class HttpMethod(LiteralEnum):
    GET = "GET"
    POST = "POST"
```

A class attribute is considered a `LiteralEnum` member if and only if:

1. Its name is all-uppercase and does not start with `_`.
2. Its value is a supported literal value.
3. It is defined directly in the class body.

Runtime mutation to add, remove, or reassign members is not supported.

Multiple member names MAY refer to the same literal value.

---

### Supported Literal Value Types

Member values MUST be one of:

* `str`
* `bytes`
* `int`
* `bool`
* `None`

Member values MUST be statically evaluable literal expressions, as defined by the rules for `typing.Literal`.

#### Floating-Point Values

`float` values are not permitted.

Floating-point literals introduce equality and reproducibility pitfalls that undermine `LiteralEnum`’s goal of simple, predictable runtime validation and membership testing. IEEE 754 behavior includes edge cases such as NaN values, negative zero, and rounding artifacts that make finite set membership surprising in practice.

Excluding `float` ensures deterministic semantics across runtimes and platforms while covering the overwhelming majority of real-world closed-set use cases.

---

### Static Type Interpretation

In type positions, a `LiteralEnum` subclass `E` MUST be interpreted as:

```python
Literal[v1, v2, ...]
```

where `v1..vn` are the effective declared member values.

This implies:

* Matching literals are accepted.
* Non-member literals are rejected.
* Values typed as a broader base type (e.g. `str`) are rejected unless narrowed to a known literal.

---

### Subclassing and Extension Semantics

A `LiteralEnum` subclass defines a **distinct finite set of literal values**.

Subclassing a `LiteralEnum` does **not** imply substitutability. A value of a subclass type is not assignable to the base type unless the subclass’s literal values form a subset of the base class’s values.

#### Extending Existing LiteralEnums

A subclass MAY extend the members of an existing `LiteralEnum` **only** by specifying the class keyword argument `extend=True`:

```python
class MoreHttpMethods(HttpMethod, extend=True):
    PATCH = "PATCH"
```

When `extend=True` is specified:

* The subclass’s value set begins with the base class’s values.
* Members declared in the subclass body are added.
* The resulting static type is widened accordingly.

When `extend=True` is **not** specified:

* The subclass MUST NOT inherit from a `LiteralEnum` that defines one or more members.
* Subclassing without `extend=True` is only permitted when inheriting directly from `LiteralEnum` itself.

This explicit opt-in prevents accidental widening of literal sets when subclassing is used for organizational or implementation purposes.

#### Inheritance Restrictions

To avoid ambiguity and complexity, implementations MUST reject multiple inheritance from more than one `LiteralEnum` base class.

---

### Runtime Semantics

#### Member Values

Each member evaluates to its literal value at runtime:

```python
assert HttpMethod.GET == "GET"
assert isinstance(HttpMethod.GET, str)
```

No wrapper objects are introduced.

---

#### Validation

Calling a `LiteralEnum` subclass validates membership:

```python
HttpMethod("GET")   # returns "GET"
HttpMethod("git")   # raises ValueError
```

---

#### Iteration

Iterating over a `LiteralEnum` yields unique member values by strict equality, in declaration order:

```python
list(HttpMethod) == ["GET", "POST", "DELETE"]
```

---

#### Membership Semantics

Membership testing MUST use **strict equality**:

* Two values are equal only if both their **type and value** are equal.
* This prevents collisions such as `True` vs `1`.

```python
True in MyEnum   # distinct from 1
```

---

### Introspection API

A `LiteralEnum` subclass MUST expose:

```python
HttpMethod.__members__  # Mapping[str, value]
```

This mapping is read-only.

Implementations MAY also expose:

```python
HttpMethod.mapping
HttpMethod.values()
```

---

## Type Checker Behavior

### Attribute Checking

Type checkers MUST:

* Validate attribute access for declared members.
* Reject access to undeclared members.
* Assign `E.MEMBER` the type `Literal[value]`, assignable to `E`.

---

### Narrowing and Exhaustiveness

Type checkers SHOULD support:

* narrowing via comparisons,
* exhaustiveness checking in `match` statements,
* all behaviors supported for equivalent `Literal[...]` unions.

---

## Backwards Compatibility

This PEP introduces a new construct and does not affect existing code.

Because members are plain literals, `LiteralEnum` composes naturally with APIs expecting base types such as `str` or `int`.

---

## Reference Implementation

A reference implementation consists of:

1. A runtime implementation (likely via a metaclass) providing:

   * member collection,
   * strict membership semantics,
   * iteration,
   * validation, and
   * introspection.
2. Type checker support interpreting `LiteralEnum` subclasses as `Literal[...]` unions.

An experimental implementation may be provided in `typing_extensions`.

---

## Rejected Alternatives

### `Enum` / `StrEnum`

Enums require enum members at call sites and introduce wrapper objects at runtime.

---

### `Literal[...]` Alone

`Literal[...]` provides no runtime namespace, validation, or iteration.

---

### Parallel Namespace + Type Alias

Splits runtime values from static types and duplicates literals.

---

### Runtime Validation of `str`

Loses static exhaustiveness checking.

---


### Implicit Subclass Extension

An alternative design considered was to allow subclasses of a `LiteralEnum` to implicitly inherit 
and extend the base class’s members without requiring an explicit opt-in.

This approach was rejected because implicit extension makes it easy to accidentally widen a literal set 
when subclassing is used for organizational, documentation, or implementation purposes. 
In typical Python code, subclassing implies an “is-a” relationship and behavioral specialization, not set union. 
Implicit widening conflicts with this intuition and can lead to subtle bugs and surprising type behavior.

Requiring an explicit `extend=True` keyword argument makes the widening operation deliberate 
and visible at the class definition site. This mirrors other areas of Python’s type system 
where potentially surprising behavior requires explicit syntax 
(e.g. `typing.Annotated`, `dataclasses.field`, or `enum.auto`). 
The explicit opt-in improves readability, prevents accidental misuse, 
and simplifies both the runtime and static semantics of `LiteralEnum`.

---

## Comparison with `Enum` and `Literal`

| Feature / Property                | `Enum` / `StrEnum`         | `Literal[...]`        | `LiteralEnum`  |
| --------------------------------- | -------------------------- | --------------------- | -------------- |
| Runtime values                    | Wrapper objects            | Plain literals        | Plain literals |
| Namespaced constants              | Yes                        | No                    | Yes            |
| Iteration                         | Yes (members)              | No                    | Yes (values)   |
| Runtime validation                | Yes                        | No                    | Yes            |
| Accepts raw literals in APIs      | No                         | Yes                   | Yes            |
| Static exhaustiveness checking    | Limited / indirect         | Yes                   | Yes            |
| Single source of truth            | Often requires duplication | No runtime source     | Yes            |
| Intended for protocol-like values | Awkward                    | Common but incomplete | Yes            |

`LiteralEnum` is not intended to replace `Enum` or `Literal` or `StrEnum`. 
Instead, it fills a specific gap for small, closed sets of scalar values 
particularly string-based protocol tokens and configuration values
where runtime literals are desirable but static exhaustiveness is still required.

---

## FAQ

### Why isn’t this just an `Enum` or `StrEnum`?

`Enum` and `StrEnum` introduce distinct runtime objects that must be passed at call sites. Many real-world APIs—particularly protocol-oriented APIs—naturally operate on raw literals such as strings or integers.

`LiteralEnum` preserves the ergonomics of plain literals at runtime while still providing namespacing, validation, and static exhaustiveness checking. It is intended for cases where literal values are the API surface, not enum members.

---

### Why not just use `typing.Literal[...]`?

`typing.Literal` provides static checking only. It does not define a runtime namespace, does not support iteration, and does not provide validation.

In practice, developers often define a set of constants at runtime and a separate `Literal[...]` type alias, duplicating values and risking drift. `LiteralEnum` unifies these roles into a single definition.

---

### Why doesn’t `LiteralEnum` define `isinstance` semantics?

Although it may be tempting to allow `isinstance(value, E)` as a shorthand for membership testing, `LiteralEnum` does not represent a true runtime type. Its members are plain literals, not instances of a distinct class.

Providing `isinstance` semantics would blur the distinction between runtime object identity and static classification, and could be misleading to readers and tools. Runtime validation is instead performed explicitly via membership testing (`value in E`) or construction (`E(value)`).

---

### Why is `extend=True` required to extend an existing `LiteralEnum`?

Subclassing in Python typically implies behavioral specialization or substitutability. Implicitly widening a finite set of allowed values via subclassing would conflict with this intuition and could lead to accidental bugs.

Requiring an explicit `extend=True` keyword makes widening deliberate and visible at the class definition site. This avoids accidental extension while still supporting common use cases such as protocol versioning or incremental expansion of allowed values.

---

### Why is multiple inheritance not supported?

Allowing multiple `LiteralEnum` base classes would introduce ambiguity around ordering, conflict resolution, and static interpretation. Restricting extension to a single base class keeps both the runtime and static semantics simple and predictable.

This restriction may be revisited in the future if compelling use cases emerge.

---

### Why are floating-point values not supported?

Floating-point literals introduce edge cases such as NaN values, negative zero, and rounding artifacts that undermine the predictability of finite set membership.

Because `LiteralEnum` is intended for closed, deterministic sets of values—such as protocol tokens and configuration keys—excluding floating-point values simplifies the model while covering the vast majority of real-world use cases.

---

### Does `LiteralEnum` replace `Enum` or `Literal`?

No. `LiteralEnum` complements existing constructs.

* Use `Enum` when identity, behavior, or rich member objects matter.
* Use `Literal` when only static typing is required.
* Use `LiteralEnum` when you want **runtime literals with namespacing and static exhaustiveness checking**.

---

## Open Issues

1. Whether to support optional `isinstance` semantics (`isinstance(x, E)` behaving like `x in E`) in a future PEP.
2. Whether duplicate values under different names should continue to be permitted.
3. Whether future versions should support controlled multi-base extension.

