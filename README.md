# LiteralEnum

**LiteralEnum** is an experiment/prototype for a proposed Python typing construct: a *finite, named set of runtime literals* (usually strings) that type checkers can treat as an **exhaustive `Literal[...]` union**.

It’s designed for “protocol token” style values—HTTP methods, event names, command identifiers, config keys—where you want:

- **plain literals at runtime** (e.g. `"GET"`),
- **namespaced constants** (e.g. `HttpMethod.GET`), and
- **static exhaustiveness checking** (i.e. the type is equivalent to `Literal["GET", "POST", ...]`).

This repo contains:
- a runtime implementation (`literalenum.LiteralEnum`)
- typing stubs (`.pyi`)
- an experimental **mypy plugin**
- sample usage + comparisons against alternative patterns
- optional helpers for **Pydantic** and **JSON Schema**

> Status: Prototype / exploration for typing-sig discussion. Not an accepted PEP.


---
## Table of Contents
- [Typing discussion](https://discuss.python.org/t/proposal-literalenum-runtime-literals-with-static-exhaustiveness/106000) with the Python community
- [PEP.md](/PEP.md) is a draft PEP
- [TYPING_DISCUSSION.md](/TYPING_DISCUSSION.md) is shows drafts from the discussion
- [src/typing_literalenum.py](/src/typing_literalenum.py) is a the draft of the core runtime functionality (proposed to become `typing.LiteralEnum` or `typing_extensions.LiteralEnum`)
- [src/literalenum](/src/literalenum) is the full proposed PyPi module
- [src/literalenum_sample](/literalenum_samples) shows a proposed usage example

---

## Why this exists

In typed Python today you often have to pick one:

- `Enum` / `StrEnum`: great runtime namespace, but APIs want callers to pass enum members instead of raw strings
- `Literal[...]`: great static checking, but no runtime namespace/iteration/validation

So people duplicate values or accept `str` and validate at runtime.

LiteralEnum aims to make the common case a single source of truth.

---

## Quick example

```python
from literalenum import LiteralEnum

class HttpMethod(LiteralEnum):
    GET = "GET"
    POST = "POST"
    DELETE = "DELETE"

def handle(method: HttpMethod) -> None:
    ...

handle("GET")          # ✅ should type-check
handle(HttpMethod.GET) # ✅ should type-check
handle("git")          # ❌ should be rejected by a type checker
````

Runtime behavior:

```python
assert HttpMethod.GET == "GET"
assert list(HttpMethod) == ["GET", "POST", "DELETE"]

HttpMethod("GET")   # returns "GET"
HttpMethod("git")   # raises ValueError
```

---

## Install (local dev)

This repo is currently set up as a package under `src/`.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

---

## Samples and comparisons

### Alternative patterns (today’s options)

The directory `src/sample_str_enum_solutions/` contains small examples of common approaches:

* `StrEnum`
* `Enum`
* plain `Literal[...]`
* `Literal + namespace`
* “literal hacks” and custom types

These are included to ground the motivation with real code.

---

## Optional integrations

### Pydantic

There’s a helper module:

* `src/literalenum/pydantic.py`

Goal: treat `LiteralEnum` values as their underlying runtime literal type while still validating membership.

### JSON Schema

There’s a helper module:

* `src/literalenum/json_schema.py`

Goal: generate an enum-like schema from the finite set of values.

(These are prototypes; APIs may change.)

---

## Design notes (current prototype)

* Members are declared as **UPPERCASE public class attributes**
* Member values are **plain runtime literals** (no wrapper objects)
* Iteration yields **unique values** in declaration order
* Membership uses **strict equality** (type + value) to avoid `True == 1` collisions
* Calling the class validates and returns the literal value:

  * `E(value) -> value` if valid, else `ValueError`

---

## Project layout

```
src/literalenum/
  literal_enum.py     # runtime implementation
  __init__.py / .pyi  # public API + typing surface
  mypy_plugin.py      # prototype mypy plugin
  stubgen.py          # stub generation helpers (prototype)
  pydantic.py         # optional integration
  json_schema.py      # optional integration

src/literalenum_sample/
  http.py             # sample enums
  use.py, use2.py      # usage examples
```

---

## Contributing / discussion

If you’re interested in typing semantics or checker integration, the most useful contributions are:

* confirming the ergonomics in real codebases,
* testing how this interacts with `match` exhaustiveness,
* feedback on the surface API (`extend=True`, introspection, strict equality, etc.),
* proposals for how checkers could support this without plugins.

---

## License

This project is released into the **public domain** under **The Unlicense**.

You are free to copy, modify, publish, use, compile, sell, or distribute this software,
either in source code form or as a compiled binary, for any purpose, commercial or non-commercial,
and by any means.

See the `LICENSE` file for full details.

