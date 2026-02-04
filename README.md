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
* provide a **runtime namespace** with iteration, validation, and membership testing,
* and are interpreted by type checkers as an **exhaustive `typing.Literal[...]` union**.

A `LiteralEnum` allows a single definition to serve simultaneously as:

* a namespace of named constants,
* a runtime validator and iterable of allowed values,
* and a static type that accepts only those values.

This construct addresses a common Python pattern—small, closed sets of string or scalar constants—without requiring duplication between `Enum` and `Literal`, checker-specific plugins, or parallel runtime and typing definitions.

---

## Motivation

Python programs frequently rely on small, finite sets of values—such as HTTP methods, event names, command identifiers, status strings, configuration keys, or protocol fields—that are most naturally represented as **plain literals at runtime** but benefit from **exhaustive checking at type-check time**.

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
* widening annotations to `str` and adding runtime validation,
* or relying on checker-specific behavior or undocumented patterns.

These approaches are verbose, error-prone, and obscure intent. They also violate the principle of a **single source of truth**, making refactors and extensions risky.

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

def handle(method: HttpMethod) -> None:
    ...

handle("GET")            # accepted
handle(HttpMethod.GET)   # accepted
handle("git")            # type checker error
```

At runtime:

* `HttpMethod.GET` evaluates to the string `"GET"`,
* iteration yields the allowed unique values by strict equality, first-seen order,
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
* Support literal types beyond strings, including `int`, `bool`, `bytes`, and `None`.

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

* are **runtime literal values**,
* are accessible by name on the class,
* and determine the **static type interpretation** of the subclass.

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
* `float` is included with restrictions (see next section)

Member values MUST be statically evaluable literal expressions, as defined
by the rules for `typing.Literal`.

---

#### Floating-Point Values

Float support is intentionally restricted to ensure total, deterministic equality semantics.

`float` member values are permitted with the following restrictions:

* NaN values are forbidden.
* Negative zero (`-0.0`) is forbidden.
* Membership and validation use strict equality (type and value).

These restrictions are required to ensure well-defined runtime membership
and validation semantics.


---

### Static Type Interpretation

In type positions, a `LiteralEnum` subclass `E` MUST be interpreted as:

```python
Literal[v1, v2, ...]
```

where `v1..vn` are the declared member values.

This implies:

* Matching literals are accepted.
* Non-member literals are rejected.
* Variables typed as a broader base type (e.g. `str`) are rejected unless narrowed to a known literal.

---

#### Subclassing and Type Relationships

A `LiteralEnum` subclass defines a **distinct finite set of literal values**
from its base class.

Subclassing a `LiteralEnum` does **not** imply substitutability:
a value of a subclass type is not assignable to a base `LiteralEnum` type
unless the subclass’s declared literal values form a **subset** of the base
class’s values.

Type checkers SHOULD treat each `LiteralEnum` subclass as a separate
`Literal[...]` union derived from its own declared members, regardless of
inheritance structure.

Extending a LiteralEnum produces a wider type (a superset of literals), analogous to widening a Literal[...] union.

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

#### Validation / Construction

Calling a `LiteralEnum` subclass validates membership:

```python
HttpMethod("GET")   # returns "GET"
HttpMethod("git")   # raises ValueError
```

---

#### Iteration

Iterating over a `LiteralEnum` yields unique member values by strict equality, first-seen order:

```python
list(HttpMethod) == ["GET", "POST", "DELETE"]
```

---

#### Membership and Equality Semantics

Membership testing and validation MUST use **strict equality**:

* Two values are equal only if both their **type and value** are equal.
* This prevents collisions such as `True` vs `1`.

```python
True in MyEnum   # distinct from 1
```

---

#### `isinstance`

A `LiteralEnum` subclass MAY support `isinstance(value, E)` returning
`True` if and only if `value` is a valid member value of `E`.

Pros:
- Enables familiar, concise runtime validation (`isinstance(x, E)`) in addition to `x in E` or `E(x)` or `E.is_valid(x)`.
- Plays nicely with many existing code patterns and third-party frameworks that already branch on `isinstance(...)` (e.g. validation/dispatch hooks).
- Keeps call sites readable when E is used like a “value class” in configuration parsing or boundary validation.
- given the core feature of `method = "GET"` passing a typehint like `method: HttpMethod`, `isinstance(method, HttpMethod)` fits a basic mental model

Cons:
- Can be surprising because E is not a traditional runtime type; it classifies literals rather than instances of a distinct runtime class.
- Risks confusion with normal subtyping expectations (e.g. readers may assume E is a real runtime type of str/int), especially given that members are plain literals.
- May interact unexpectedly with metaclass-based __instancecheck__ and tools that assume isinstance reflects concrete object inheritance.
- Provides no guaranteed static benefit: type checkers are not required to treat isinstance(value, E) as a narrowing guard, so it may encourage patterns that don’t improve type safety.

Type checkers are not required to use isinstance(value, E) for narrowing.


---

### Introspection API

A `LiteralEnum` subclass MUST expose:

```python
HttpMethod.__members__  # Mapping[str, value]
```

This mapping is read-only.

Implementations MAY also expose:

```python
HttpMethod.mapping      # alias of __members__
HttpMethod.values()     # iterable of values
```

---

## Type Checker Behavior

### Attribute Checking

Type checkers MUST:

* Validate attribute access for declared members.
* Reject access to undeclared members.
* Attribute access E.MEMBER has type Literal\[value\] and is assignable to E.

---

### Narrowing and Exhaustiveness

Type checkers SHOULD support:

* narrowing via comparisons,
* exhaustiveness checking in `match` statements,
* the same behaviors supported for equivalent `Literal[...]` unions.

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
   * validation,
   * `isinstance` support,
   * and introspection.

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

## Open Issues

1. Whether to make the `isinstance` a MUST, SHOULD, or MAY requirement or to remove it entirely
2. Whether `float` should ever be supported. (right now it is, but with restrictions)
3. Whether duplicate values under different names should be permitted. (right now they are)
4. Whether subclassing should allow extending or overriding members. (right now subclassing does allow extending)
