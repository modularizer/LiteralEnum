# Contributing to LiteralEnum

Thanks for your interest in contributing. This document covers setup, project layout, and guidelines.

## Setup

```bash
git clone https://github.com/modularizer/LiteralEnum.git
cd LiteralEnum
python -m venv .venv
source .venv/bin/activate
pip install -e .
pip install pytest
```

Requires Python 3.10+.

## Project layout

```
src/
  typing_literalenum.py              # Core module (proposed for typing_extensions / stdlib)
  literalenum/
    __init__.py                      # Package entry point
    literal_enum.py                  # Extended metaclass wrapping the core
    mypy_plugin.py                   # mypy plugin
    stubgen.py                       # .pyi stub generator (lestub CLI)
    compatibility_extensions/        # Converters to other frameworks
      enum.py, str_enum.py, ...
tests/
  test_typing_literalenum.py         # Tests for the core module
  test_literalenum.py                # Tests for the package (extended metaclass + compat)
  test_typing.py                     # mypy type-checking validation
```

The two-module split is intentional:

- **`typing_literalenum`** is the minimal, zero-dependency core proposed for the standard library. It should stay lean.
- **`literalenum`** is the full package with ecosystem integrations (Pydantic, SQLAlchemy, Django, GraphQL, etc.). This is what gets published to PyPI.

## Running tests

```bash
# All tests
pytest

# Core module only
pytest tests/test_typing_literalenum.py

# Package only
pytest tests/test_literalenum.py

# Verbose
pytest -v
```

Tests for optional dependencies (strawberry, graphene, sqlalchemy, pydantic, click) are automatically skipped if the dependency isn't installed.

## What goes where

| Change                                                                      | File(s)                                                                                                                                                     |
|-----------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Core runtime behavior (iteration, containment, validation, aliases, extend) | `src/typing_literalenum.py` + `tests/test_typing_literalenum.py`                                                                                            |
| New compatibility converter (e.g. marshmallow, attrs)                       | New file in `compatibility_extensions/`, method in `literal_enum.py`, export in `compatibility_extensions/__init__.py`, test in `tests/test_literalenum.py` |
| Stub generation                                                             | `src/literalenum/stubgen.py`                                                                                                                                |
| mypy plugin                                                                 | `src/literalenum/mypy_plugin.py`                                                                                                                            |

## Adding a compatibility extension

1. Create `src/literalenum/compatibility_extensions/my_thing.py`:
   ```python
   def my_thing(cls):
       # cls is a LiteralEnum class with _ordered_values_, _members_, etc.
       ...
   ```

2. Export it in `compatibility_extensions/__init__.py`:
   ```python
   from .my_thing import my_thing
   ```

3. Add the method to `LiteralEnumMeta` in `literal_enum.py`:
   ```python
   def my_thing(cls):
       return compat.my_thing(cls)
   ```

4. Add tests in `tests/test_literalenum.py`. If the extension requires an optional dependency, use `pytest.importorskip`:
   ```python
   def test_my_thing(self):
       pytest.importorskip("some_library")
       result = HttpMethod.my_thing()
       assert ...
   ```

## Guidelines

- **Don't add dependencies.** The core module has zero dependencies and must stay that way. The package has zero required dependencies; optional integrations use local imports.
- **Keep the core minimal.** `typing_literalenum.py` is a standard library proposal. Only add features there if they belong in `typing_extensions`.
- **Test what you add.** Every new method needs tests. Core features go in `test_typing_literalenum.py`, package features in `test_literalenum.py`.
- **Avoid breaking changes to the metaclass protocol.** Existing LiteralEnum subclasses shouldn't break when upgrading.

## Stub generation

The `lestub` CLI generates `.pyi` stubs for LiteralEnum subclasses:

```bash
# From a dotted import
lestub myapp.models

# From a file
lestub src/myapp/models.py

# From a directory
lestub src/myapp/

# Write overlay stubs to a directory
lestub myapp --out typings
```

If you change the public API surface of `LiteralEnumMeta`, update `_render_enum_blocks` in `stubgen.py` to match.

## Reporting issues

Open an issue at https://github.com/modularizer/LiteralEnum/issues.

## License

This project is released under [The Unlicense](LICENSE) (public domain). By contributing, you agree that your contributions are released under the same terms.
