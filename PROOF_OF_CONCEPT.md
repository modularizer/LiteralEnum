# LiteralEnum: Proof of Concept

## The Goal

```python
from typing import LiteralEnum

class HttpMethod(LiteralEnum):
    GET = "GET"
    POST = "POST"
    DELETE = "DELETE"
```

One class. Values written once. Works as both a namespace and a `Literal["GET", "POST", "DELETE"]` type.

### Required Runtime Behavior

```python
# Values are true strings
assert isinstance(HttpMethod.GET, str)
assert HttpMethod.GET == "GET"
assert type(HttpMethod.GET) is str
assert HttpMethod.GET is "GET"

# isinstance works for membership
assert isinstance("GET", HttpMethod)
assert isinstance(HttpMethod.GET, HttpMethod)
assert not isinstance("git", HttpMethod)

# Iterable + dict-able
options: list[HttpMethod] = list(HttpMethod)
options_by_name: dict[str, HttpMethod] = dict(HttpMethod)

# Constructor / validator
assert HttpMethod("GET") == "GET"
```

### Required Static Behavior

```python
# HttpMethod is treated as Literal["GET", "POST", "DELETE"]
def handle(method: HttpMethod):
    pass

handle("GET")            # OK
handle(HttpMethod.GET)   # OK
handle("git")            # type error
handle(HttpMethod.git)   # type error + AttributeError
```


---

## POC Part 1: Runtime Library

The runtime side is straightforward. A metaclass that collects uppercase members and provides the right protocols.
See 9_literal_enum.py

---

## POC Part 2: mypy Plugin

This is the hard part and where the real work lives. The runtime is simple; making type checkers understand the semantics is what makes this a language-level problem.

### What the Plugin Must Do

When mypy sees:

```python
class HttpMethod(LiteralEnum):
    GET = "GET"
    POST = "POST"
```

The plugin must make mypy behave as if:

1. `HttpMethod.GET` has type `Literal["GET"]`
2. `HttpMethod.POST` has type `Literal["POST"]`
3. `HttpMethod.git` is a type error (no such attribute)
4. `method: HttpMethod` in annotations means `Literal["GET", "POST"]`
5. `handle("GET")` passes when param is `HttpMethod`
6. `handle("git")` fails when param is `HttpMethod`
7. `HttpMethod("GET")` returns `HttpMethod` (i.e., `Literal["GET", "POST"]`)

### The Core Challenge

mypy internally represents classes and Literal types as fundamentally different objects:

- A **class** has a `TypeInfo` with attributes, methods, bases
- A **Literal type** is a `LiteralType` with a fixed value and a fallback type

`HttpMethod` needs to be both simultaneously:
- A class (for `HttpMethod.GET` attribute access)
- A Literal union (for `method: HttpMethod` annotation semantics)

No existing mypy construct does this. `TypedDict` is the closest precedent -- it's a class with special type-checking rules -- but even TypedDict doesn't need to act as a `Literal` union.

### Plugin Implementation Strategy

Using mypy's plugin API (`mypy.plugin.Plugin`):

**Hook 1: `get_base_class_hook("literalenum.LiteralEnum")`**

Triggered when mypy processes a class inheriting from `LiteralEnum`. The callback:

- Iterates over the class body's assignments
- For each uppercase member `GET = "GET"`, sets its type to `Final[Literal["GET"]]`
- Records the full set of literal values in metadata on the class's `TypeInfo`

This makes `HttpMethod.GET` correctly typed and `HttpMethod.git` an error.

**Hook 2: `get_type_analyze_hook` or semantic analysis pass**

This is the hard hook. When `HttpMethod` appears in an annotation position like `def handle(method: HttpMethod)`, the plugin needs to intercept type resolution and expand it to `Union[Literal["GET"], Literal["POST"]]`.

Options for implementing this:
- **Type alias injection**: During class processing, create a parallel type alias in mypy's symbol table so `HttpMethod` resolves to the Literal union in annotation context
- **Custom type**: Create a synthetic mypy type that wraps both the class info and the Literal union, dispatching to the right one based on context
- **Post-processing**: After mypy's main analysis, rewrite types that reference LiteralEnum subclasses

None of these are trivial. The type alias injection approach is probably most feasible because mypy already handles type aliases that resolve to Literal unions.

**Hook 3: `get_method_hook` for `__call__`**

When mypy sees `HttpMethod("GET")`, the plugin should type the return as `HttpMethod` (the Literal union) and validate the argument is a member.

### Precedent and Feasibility

Plugins that do comparable type-rewriting:

| Plugin | What it does | Similarity |
|---|---|---|
| django-stubs | Makes `Model.objects` return typed querysets | Class attributes with special types |
| sqlalchemy-stubs | Maps ORM columns to Python types | Class body → type mapping |
| pydantic mypy plugin | Makes model fields act as both class attrs and constructor params | Dual behavior based on context |
| attrs mypy plugin | Generates `__init__` signature from class body | Deriving types from member definitions |

The LiteralEnum plugin is harder than any of these in one specific way: it needs a class to act as a type alias in annotation position. That's a novel requirement. But the individual pieces (reading class members, setting attribute types, creating Literal types) are all well-supported by the plugin API.

### Estimated Effort

The mypy plugin is the bulk of the POC work. Rough breakdown:

- Setting up the plugin scaffolding and test infrastructure: straightforward
- Hook 1 (class processing, member typing): moderate -- well-precedented
- Hook 2 (annotation expansion): hard -- novel requirement, may require creative use of mypy internals
- Hook 3 (constructor typing): moderate
- Testing against the full requirement matrix: moderate
- Edge cases (generics, unions, overloads, re-exports): hard -- long tail

Hook 2 is the make-or-break piece. If mypy's architecture allows a clean way to expand a class reference to a Literal union in annotation context, the plugin is very doable. If it doesn't, you may need to work around mypy internals in fragile ways, which weakens the argument for a PEP.

---

## POC Part 3: pyright Consideration

Pyright (used by Pylance/VS Code) is the second major type checker. Its extension model is more limited than mypy's.

For the POC, **focus on mypy only**. Pyright support strengthens the PEP argument but is not required to prove the concept. If the PEP gains traction, Eric Traut (pyright author) would likely add native support rather than relying on a plugin.

---

## Deliverables

A credible POC consists of:

1. **`literalenum` package** -- the runtime metaclass (~100 lines of code)
2. **`literalenum-mypy` plugin** -- makes mypy understand LiteralEnum (the real work)
3. **Test suite** -- two parts:
   - Runtime tests (pytest): all assertions from the spec above
   - Type-checking tests (using `pytest-mypy-testing` or mypy's `test-data` format): verify that correct code passes and incorrect code produces errors
4. **A single compelling example** -- e.g. `HttpMethod` used in a small web handler, showing the before (StrEnum or Literal+class) and after (LiteralEnum)

---

## Is There ANY Way to Do This Without Modifying How Python Works?

### Short Answer

**No.** Not completely.

### Why Not

The fundamental blocker is that Python's type system has no mechanism for a user to declare "this class is a `Literal` union." `Literal` is a special form hardcoded into type checkers. There is no protocol, no metaclass trick, no decorator, and no `__class_getitem__` override that makes a type checker treat a user-defined class as interchangeable with `Literal["GET", "POST"]`.

This means requirement 3.4 (`handle("GET")` passing when the parameter type is `HttpMethod`) is impossible in pure Python without type checker cooperation.

### The Spectrum of "Modifying Python"

| Approach | What you modify | What you get |
|---|---|---|
| Runtime library only | Nothing | Runtime works, static typing doesn't |
| + mypy plugin | mypy (via plugin API) | Full solution for mypy users only |
| + typing_extensions | typing_extensions package + type checkers | Cross-checker support, no CPython change |
| + PEP in stdlib | CPython + type checkers | First-class language feature |

The runtime library alone covers: `isinstance`, `==`, `is`, `type() is str`, `list()`, `dict()`, iteration, `HttpMethod("GET")`, `AttributeError` on bad access. That's real value.

But `handle("GET")` passing type checks when the parameter is `HttpMethod` -- the central static typing requirement -- requires teaching type checkers something new. There is no way around this.

### Recommended Path

1. Build the runtime library (quick, useful on its own)
2. Build the mypy plugin (proves the concept end-to-end)
3. Use that experience to push for typing_extensions support or a PEP
4. If typing_extensions accepts it, mypy and pyright add native support
5. Eventually, `from typing import LiteralEnum` in the stdlib
