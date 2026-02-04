# PEP: Static Type Interpretation for Runtime Symbols

## Abstract

This PEP proposes a standardized mechanism for associating an **alternate static type** with a runtime symbol (class or function), allowing type checkers to treat a symbol as one type in type positions while preserving its runtime behavior as a value.

The mechanism supports two stages:

1. **Inference** of an alternate static type based on a declarative `InferSpec` (if resolvable).
2. A directly provided **static type**.

The proposal introduces:

* A decorator `@typing.static_type(...)` (initially in `typing_extensions`) that sets a `__static_type__` attribute.
* A new attribute `__static_type__` recognized by type checkers on classes and functions.
* An `InferSpec` object describing inference rules for checkers.

Resolution priority for a symbol `S` in a type position:

1. If `InferSpec` is present and inference succeeds → inferred type
2. Else if an explicit static type is provided → explicit type
3. Else → the original type of `S`

## Motivation

Python libraries frequently define runtime objects that serve as **namespaces, factories, validators, or protocol-like containers**, whose *runtime identity* is useful (attribute access, iteration, `isinstance` via metaclass hooks, etc.), while their *static meaning in annotations* is better modeled as a different type (e.g., a `Literal[...]` union or a structural type).

Today, achieving this typically requires one or more of:

* type-checker-specific plugins,
* generated stub files,
* parallel “alias types” and `TYPE_CHECKING` imports.

These approaches are fragmented and impose maintenance burdens.

This PEP standardizes an opt-in approach analogous in spirit to `typing.dataclass_transform` (PEP 681), enabling cross-checker support without requiring full plugin architectures.

## Goals

* Allow a library author to declare that a runtime symbol should be interpreted as a different type in type positions.
* Provide a checker-friendly, non-executing, declarative inference mechanism via `InferSpec`.
* Ensure safe fallback behavior when inference cannot be performed.
* Preserve runtime semantics and avoid requiring runtime-only dependencies.

## Non-Goals

* This PEP does not require type checkers to execute arbitrary code.
* This PEP does not standardize any particular inference algorithm beyond the `InferSpec` contract.
* This PEP does not mandate inference; inference is optional and must be safe to ignore.
* This PEP does not change Python runtime semantics.

## Rationale

### Why an attribute plus a decorator?

* An attribute (`__static_type__`) is a simple, discoverable convention that type checkers can read from stubs or source.
* A decorator provides ergonomic syntax and allows a standardized way to set the attribute.
* The decorator is defined as “sets the attribute,” so checkers only need to support one conceptual hook.

### Why a two-stage priority?

Inference is the most user-friendly and can eliminate stub generation. However, inference may fail due to dynamic definitions or checker limitations. The explicit fallback gives authors a reliable escape hatch.

Priority order:

1. inferred type if resolvable,
2. explicit static type,
3. original type

matches developer expectations: “use the best information available; otherwise fall back.”

## Specification

### 1. `__static_type__` attribute

A class or function may define a `__static_type__` attribute for use by type checkers.

`__static_type__` may take one of the following forms:

* A **static type expression** `T`
* An instance of **InferSpec**
* A composite structure containing both explicit static type and inference specification

This PEP standardizes the composite structure as:

* `StaticTypeInfo(static_type: object | None, infer: InferSpec | None)`

A conforming checker must accept any of the following as `__static_type__`:

* `T` (treated as explicit static type)
* `InferSpec(...)` (treated as inference-only)
* `StaticTypeInfo(static_type=T, infer=InferSpec(...))`

Checkers may also accept equivalent structural representations in stubs (e.g. `TypedDict`), but the above is the normative model.

### 2. `@static_type` decorator

A decorator is provided (initially in `typing_extensions`, later possibly `typing`) with this signature:

```python
@static_type(static_type: object | None = None, infer: InferSpec | None = None)
```

Runtime behavior:

* The decorator sets `__static_type__` on the decorated object.
* If both are provided, it sets `__static_type__ = StaticTypeInfo(static_type, infer)`.

Type-checker behavior:

* Type checkers should behave as if the decorated symbol has the specified `__static_type__` attribute.
* Type checkers must not require executing the decorator.

### 3. `InferSpec`

`InferSpec` is a declarative container that describes an inference request.

Minimal requirements:

* `InferSpec` must be identifiable by checkers (nominally via `typing_extensions.InferSpec`).
* It must carry a `kind` string and `params` mapping.

Example conceptual shape:

```python
class InferSpec:
    kind: str
    params: Mapping[str, object]
```

Checkers may support one or more `kind` values. Unsupported kinds must be treated as “inference failed.”

This PEP does not initially standardize a long list of kinds; it specifies the protocol and one initial kind for usefulness.

### 4. Resolution rules in type positions

When a name `S` appears in a type position, and `S` resolves to a runtime symbol (class or function), a checker must determine its “static interpretation” as follows:

1. If `S` has `__static_type__` with an `InferSpec`:

   * Attempt inference according to the spec.
   * If inference succeeds, use that inferred type.
   * If inference fails or is unsupported, continue.

2. If `S` has `__static_type__` containing an explicit `static_type`:

   * Use that explicit type.

3. Otherwise:

   * Use the original type `S` normally represents.

These rules apply to:

* parameter annotations,
* return annotations,
* variable annotations,
* type aliases,
* generic arguments where `S` appears as a type.

### 5. Initial standardized inference kind (optional but recommended)

To make the PEP immediately valuable, define one initial inference kind:

**Kind:** `"literal_union_from_class_attributes"`

**Purpose:** infer `Literal[...]` union from statically evaluable class attribute assignments.

Parameters:

* `include_bases: bool` (default `True`)
* `allowed_value_types: tuple[type, ...]` (default `(str,)`)
* `exclude_private: bool` (default `True`)
* `exclude_dunder: bool` (default `True`)

Inference algorithm outline (checker-side, purely static):

* Collect class attributes defined with simple assignments where RHS is a statically evaluable literal of an allowed type.
* If `include_bases` is true, include compatible attributes from base classes that also participate under the same rules.
* Form a `Literal[v1, v2, ...]` union from the collected values (deduped).
* Inference succeeds if the resulting set is non-empty (or may succeed with `Never`/`NoReturn` if empty; this is checker-defined but should be consistent).

This inference kind is explicitly limited to avoid requiring evaluation.

## Examples

### Example A: explicit static type only (Phase 1)

```python
from typing_extensions import static_type
from typing import Literal

@static_type(Literal["GET", "POST", "DELETE"])
class HttpMethod:
    GET = "GET"
    POST = "POST"
    DELETE = "DELETE"

def handle(m: HttpMethod) -> None:
    ...
```

Type checker behavior:

* `HttpMethod` in the annotation of `handle` is interpreted as `Literal["GET","POST","DELETE"]`.

### Example B: inference (Phase 2)

```python
from typing_extensions import static_type, InferSpec

@static_type(infer=InferSpec(
    kind="literal_union_from_class_attributes",
    params={"include_bases": True, "allowed_value_types": (str,)}
))
class HttpMethod:
    GET = "GET"
    POST = "POST"
    DELETE = "DELETE"
```

Type checker behavior:

* `HttpMethod` used in type positions is inferred as `Literal["GET","POST","DELETE"]`.
* If the checker can’t infer (unsupported kind), it falls back to explicit static type if provided, else the original class.

### Example C: both inference + explicit fallback

```python
@static_type(
    static_type=Literal["GET","POST","DELETE"],
    infer=InferSpec(kind="literal_union_from_class_attributes", params={})
)
class HttpMethod:
    GET = "GET"
    POST = "POST"
    DELETE = "DELETE"
```

Priority:

* inferred if possible; else explicit; else original.

## Backwards Compatibility

* Runtime behavior is unchanged unless code reads `__static_type__`.
* Type checkers that do not implement this PEP will simply treat the symbol as its normal type.
* Because `__static_type__` is a dunder-like name, risk of collision is low; however, libraries using the same name for other purposes may need coordination.

## Security / Safety Considerations

* Checkers must not execute arbitrary code to resolve `__static_type__` or perform inference.
* Inference must be based on static analysis only.

## Reference Implementation Plan

1. Provide `static_type`, `InferSpec`, and `StaticTypeInfo` in `typing_extensions`.
2. Implement resolution logic and one inference kind in at least one checker (e.g., Pyright) behind a feature flag.
3. Collect feedback, extend inference kinds if needed, then consider moving into `typing` for a later Python version.

## Open Questions

* Should `__static_type__` also be supported on modules (module-level alternate typing)?
* Should the inference kinds be standardized centrally or left to checker-defined extensions?
* How should generic parameters interact (e.g., `@static_type(List[T])` on generic classes)?

