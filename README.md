# LiteralEnum

**LiteralEnum** is an experiment/prototype for a proposed Python typing construct: 
a *finite, named set of runtime literals* (usually strings) that type checkers can treat as 
an **exhaustive `Literal[...]` union**.

> Status: Prototype / exploration for typing-sig discussion. Not an accepted PEP.

--- 

## Why this exists
In typed Python today you often have to pick one:

- `Enum` / `StrEnum`: great runtime namespace, but APIs want callers to pass enum members instead of raw strings
- `Literal[...]`: great static checking, but no runtime namespace/iteration/validation

So people duplicate values or accept `str` and validate at runtime.

LiteralEnum aims to make the common case a single source of truth.

---

## What is it?
1. A runtime python package provided with `pip install literalenum`
2. A mypy plugin for correctly type checking the new construct in a way that matches the runtime behavior
3. A Pycharm Plugin for correct syntax highlighting to match the runtime behavior
4. A discussion in hopes of creating support for a PEP to help solve these painpoints in the Python language, such that type checker plugins are not needed

---
## Table of Contents
- [Typing discussion](https://discuss.python.org/t/proposal-literalenum-runtime-literals-with-static-exhaustiveness/106000) with the Python community
- [PEP.md](/PEP.md) is a draft PEP
- [LITMUS.md](/LITMUS.md) describes the project goals
- [TYPING_DISCUSSION.md](/TYPING_DISCUSSION.md) is shows drafts from the discussion
- [src/typing_literalenum.py](/src/typing_literalenum.py) is a the draft of the core runtime functionality (proposed to become `typing.LiteralEnum` or `typing_extensions.LiteralEnum`)
- [src/literalenum](/src/literalenum) is the full proposed PyPi module
- [src/literalenum/mypy_plugin.py](/src/literalenum/mypy_plugin.py) is an experimental **mypy plugin**
- [src/literalenum/samples](/src/literalenum/samples) shows sample usage
- [src/literalenum/stubgen.py](/src/literalenum/stubgen.py) provides tools for generating stubs, usable through CLI tool `lestub`

---

## Quickstart

## Install

This repo is currently set up as a package under `src/`.

```bash
#python -m venv .venv
#source .venv/bin/activate
pip install literalenum
```
## Usage
The following is valid at runtime, but will not pass static type-checking correctly unless you use a provided plugin.
```python
from literalenum import LiteralEnum

class HttpMethod(LiteralEnum):
    GET = "GET"
    POST = "POST"
    DELETE = "DELETE"

def handle(method: HttpMethod) -> None:
    print(f"{method=}")

handle("GET")          # the GOAL is that this should type-check ✅ , in reality: it will not unless typecheckers change
handle(HttpMethod.GET) # the GOAL is that this should type-check ✅ , in reality: it will not unless typecheckers change
handle("git")          # ❌ should be rejected by a type checker

assert HttpMethod.GET == "GET"
assert list(HttpMethod) == ["GET", "POST", "DELETE"]
assert "GET" in HttpMethod
print(HttpMethod.keys())
print(HttpMethod.values())
print(HttpMethod.mapping)
```


---

## Contributing / discussion

Actively looking for feedback!
Please comment at https://discuss.python.org/t/proposal-literalenum-runtime-literals-with-static-exhaustiveness/106000

It would be especially helpful if you are familiar with mypy/pright/pylance and have suggestions on how
a future Python version could support the type hinting goals.

---

## License

This project is released into the **public domain** under **The Unlicense**.

You are free to copy, modify, publish, use, compile, sell, or distribute this software,
either in source code form or as a compiled binary, for any purpose, commercial or non-commercial,
and by any means.

See the `LICENSE` file for full details.

