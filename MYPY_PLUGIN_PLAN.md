# mypy Plugin Plan for LiteralEnum

## The Key Insight

`get_type_analyze_hook(fullname)` fires for **every** unbound type reference during
semantic analysis — including plain `method: HttpMethod`. This is confirmed by mypy's
source (`typeanal.py:visit_unbound_type_nonoptional`) and the docstring on the hook.

This means we can give `HttpMethod` **split-brain** behavior:

- **Value context** (`HttpMethod.GET`, `list(HttpMethod)`) → normal class with attributes
- **Type context** (`method: HttpMethod`, `x: HttpMethod`) → `Literal["GET", "POST", "DELETE"]`

These are resolved by different parts of mypy's pipeline and do not interfere with each other.

---

## Architecture: Two Hooks

```
┌─────────────────────────────────────────────────────────────┐
│ get_base_class_hook("literalenum.LiteralEnum")              │
│                                                             │
│  Fires when mypy processes:                                 │
│    class HttpMethod(LiteralEnum):                           │
│        GET = "GET"                                          │
│        POST = "POST"                                        │
│                                                             │
│  Actions:                                                   │
│    1. Extract member names + values from class body         │
│    2. Set each member type to Final[Literal["GET"]] etc.    │
│    3. Store member list in TypeInfo.metadata + plugin state │
│    4. Add __new__ overloads for constructor                 │
└─────────────────────────────────────────────────────────────┘
                           │
                     plugin state:
              _literalenum_classes = {
                "mymod.HttpMethod": ["GET", "POST"]
              }
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ get_type_analyze_hook("mymod.HttpMethod")                   │
│                                                             │
│  Fires when mypy encounters:                                │
│    def handle(method: HttpMethod) -> None: ...              │
│    x: HttpMethod = "GET"                                    │
│    items: list[HttpMethod] = ...                            │
│                                                             │
│  Action:                                                    │
│    Return UnionType([LiteralType(str, "GET"),               │
│                      LiteralType(str, "POST")])             │
│                                                             │
│  Result:                                                    │
│    handle("GET")          ✅  Literal["GET"] <: the union   │
│    handle(HttpMethod.GET) ✅  Literal["GET"] <: the union   │
│    handle("git")          ❌  Literal["git"] not in union   │
└─────────────────────────────────────────────────────────────┘
```

### Why This Doesn't Break Attribute Access

`HttpMethod.GET` is a **value expression**, not a type reference. mypy resolves it
through the class's `SymbolTable`, not through the type analyzer. The type analyze
hook is never called. The class remains intact with its attributes, and the base
class hook has already typed `GET` as `Final[Literal["GET"]]`.

### Verification Walkthrough

```python
class HttpMethod(LiteralEnum):
    GET = "GET"
    POST = "POST"

def handle(method: HttpMethod) -> None: ...

handle("GET")            # mypy resolves HttpMethod → Literal["GET", "POST"]
                         # checks: Literal["GET"] <: Literal["GET", "POST"] → ✅

handle(HttpMethod.GET)   # HttpMethod.GET has type Literal["GET"] (from Final)
                         # checks: Literal["GET"] <: Literal["GET", "POST"] → ✅

handle("git")            # checks: Literal["git"] <: Literal["GET", "POST"] → ❌

HttpMethod.GET           # value expr → class attr lookup → Literal["GET"] ✅
HttpMethod.git           # value expr → class attr lookup → no such attr → ❌
```

---

## Implementation Phases

### Phase 0: Project Scaffolding

```
literalenum/
├── __init__.py              # LiteralEnum runtime class (9_runtime_literal_enum.py content)
├── _mypy_plugin.py          # the mypy plugin
├── py.typed                 # PEP 561 marker
├── pyproject.toml           # package config, declares mypy plugin entrypoint
└── tests/
    ├── test_runtime.py      # pytest: runtime behavior
    ├── test_mypy.py         # pytest-mypy-plugins: type checking behavior
    └── mypy_test_cases/
        ├── pass_cases.py    # code that must typecheck cleanly
        └── fail_cases.py    # code with expected mypy errors
```

**Testing infrastructure:**
- [`pytest-mypy-plugins`](https://github.com/typeddjango/pytest-mypy-plugins): YAML-based mypy test cases. Each case specifies input code and expected mypy output. This is what django-stubs and pydantic use.
- Alternative: mypy's own `mypy/test/testcheck.py` infrastructure, but it's harder to set up externally.

**Plugin registration** (in `pyproject.toml` or `mypy.ini`):
```ini
[mypy]
plugins = literalenum._mypy_plugin
```

### Phase 1: Base Class Hook — Member Processing

**Hook:** `get_base_class_hook(fullname)` — return callback when `fullname == "literalenum.LiteralEnum"`

**Callback receives:** `ClassDefContext` with:
- `ctx.cls` — the `ClassDef` AST node
- `ctx.cls.info` — the `TypeInfo` (symbol table, metadata, flags)
- `ctx.api` — `SemanticAnalyzerPluginInterface`

**Actions:**

1. **Extract members** from the class body:
   ```python
   members: dict[str, object] = {}
   for stmt in ctx.cls.defs.body:
       if isinstance(stmt, AssignmentStmt):
           # Check: uppercase name, literal value
           name = stmt.lvalues[0].name  # "GET"
           value = extract_literal_value(stmt.rvalue)  # "GET"
           members[name] = value
   ```
   Use `ctx.api.parse_str_literal()` for string values. For int/bool, inspect the `IntExpr`/`NameExpr` AST nodes directly.

2. **Set member types** to `Final[Literal[<value>]]`:
   ```python
   for name, value in members.items():
       # Look up the existing Var in the class's symbol table
       var = ctx.cls.info.names[name].node  # Var
       var.type = ctx.api.anal_type(...)    # LiteralType
       var.is_final = True
   ```
   Use `mypy.plugins.common.add_attribute_to_class()` if needed, or modify existing `Var` nodes.

3. **Store member data** in two places:
   - `ctx.cls.info.metadata["literalenum"] = {"members": {"GET": "GET", "POST": "POST"}}`
     (persisted across incremental runs)
   - `self._literalenum_classes[fullname] = members`
     (in-memory for fast lookup by type analyze hook)

4. **Handle inheritance**: If the class has a LiteralEnum parent with existing members,
   merge parent members into child members:
   ```python
   for base_info in ctx.cls.info.mro[1:]:
       parent_meta = base_info.metadata.get("literalenum")
       if parent_meta:
           parent_members = parent_meta["members"]
           all_members = {**parent_members, **own_members}
   ```

**Tests for Phase 1:**
```python
class HttpMethod(LiteralEnum):
    GET = "GET"
    POST = "POST"

reveal_type(HttpMethod.GET)   # N: Revealed type is "Literal['GET']"
reveal_type(HttpMethod.POST)  # N: Revealed type is "Literal['POST']"
HttpMethod.git                # E: "type[HttpMethod]" has no attribute "git"
```

### Phase 2: Type Analyze Hook — Annotation Expansion

**Hook:** `get_type_analyze_hook(fullname)` — return callback when `fullname in self._literalenum_classes`

**Callback receives:** `AnalyzeTypeContext` with:
- `ctx.type` — the `UnboundType` (includes `.args` for parameterized usage)
- `ctx.api` — `TypeAnalyzerPluginInterface` (has `named_type()`, `fail()`, `analyze_type()`)

**Action:** Construct and return the Literal union type:
```python
def _expand_literalenum(self, ctx: AnalyzeTypeContext) -> Type:
    fullname = ...  # extracted from ctx.type
    members = self._literalenum_classes[fullname]

    literal_types = []
    for value in members.values():
        if isinstance(value, str):
            lit = LiteralType(value, ctx.api.named_type("builtins.str", []))
            literal_types.append(lit)
        elif isinstance(value, int):
            lit = LiteralType(value, ctx.api.named_type("builtins.int", []))
            literal_types.append(lit)
        elif isinstance(value, bool):
            lit = LiteralType(value, ctx.api.named_type("builtins.bool", []))
            literal_types.append(lit)
        # ... bytes, None

    return UnionType.make_union(literal_types)
```

**Critical concern: timing.** The type analyze hook fires during semantic analysis.
If `HttpMethod` is used as a type BEFORE the class definition is processed (forward
reference), the plugin won't know it's a LiteralEnum yet. Solutions:

- **Same file, class defined first (common case):** mypy processes statements sequentially.
  Base class hook fires first. Type analyze hook has the data. ✅
- **Same file, forward reference:** mypy defers and re-analyzes in a later pass.
  On the second pass, the class is known. ✅ (but needs testing)
- **Cross-module import:** imported module is processed first. ✅
- **Incremental mode (mypy daemon):** `_literalenum_classes` dict is lost between runs.
  Reconstruct it from `TypeInfo.metadata` at plugin startup or lazily in the hook.

**Lazy reconstruction for incremental mode:**
```python
def get_type_analyze_hook(self, fullname: str):
    # Fast path: already known
    if fullname in self._literalenum_classes:
        return self._expand_literalenum

    # Slow path: check if this is a LiteralEnum from a previous run
    sym = self.lookup_fully_qualified(fullname)
    if sym and sym.node and hasattr(sym.node, 'metadata'):
        meta = sym.node.metadata.get("literalenum")
        if meta:
            self._literalenum_classes[fullname] = meta["members"]
            return self._expand_literalenum

    return None
```

**Tests for Phase 2:**
```python
def handle(method: HttpMethod) -> None: ...

handle("GET")            # ok
handle(HttpMethod.GET)   # ok
handle("git")            # E: Argument 1 to "handle" has incompatible type "Literal['git']"...

x: HttpMethod = "GET"    # ok
y: HttpMethod = "git"    # E: Incompatible types in assignment

reveal_type(x)           # N: Revealed type is "Literal['GET']"

def returns_method() -> HttpMethod:
    return "POST"         # ok

def returns_bad() -> HttpMethod:
    return "PATCH"        # E: ...
```

### Phase 3: Constructor Typing

**Goal:** `HttpMethod("GET")` returns the Literal union type. `HttpMethod("git")` is an error.

**Approach:** In the base class hook (Phase 1), add a synthetic `__new__` with overloads:
```python
# Synthesize:
@overload
def __new__(cls, value: Literal["GET"]) -> Literal["GET"]: ...
@overload
def __new__(cls, value: Literal["POST"]) -> Literal["POST"]: ...
def __new__(cls, value: str) -> HttpMethod: ...
```

Use `mypy.plugins.common.add_method_to_class()` to add the overloaded `__new__`.

Alternatively, use `get_function_hook` keyed to `HttpMethod.__init__` or `HttpMethod`
(for constructor calls) to refine the return type after type-checking.

**Wait — there's a complication.** Since the type analyze hook replaces `HttpMethod` with
the Literal union in type contexts, what happens with `HttpMethod("GET")`?

`HttpMethod("GET")` is a **call expression** on the **value** `HttpMethod`. The type
analyze hook doesn't affect this — it only fires for type references. So mypy sees a
call to the class `HttpMethod` and uses the class's `__new__`/`__init__` signature.

But the return type of `__new__` should be... what? If we say it returns `HttpMethod`
(the class instance), that's useless since the user wants it to act as a string. If we
say it returns `str`, that's too broad. If we say it returns the Literal union... we can
use `get_function_hook("literalenum.HttpMethod")` to set the return type to the
appropriate Literal union.

**Best approach:** Use `get_function_hook` keyed to the class fullname. When mypy
processes `HttpMethod("GET")`, the hook fires. Inspect the argument type:
- If arg is `Literal["GET"]`, return `Literal["GET"]`
- If arg is `Literal["GET", "POST"]` (union), return the same union
- If arg is bare `str`, return the full Literal union (or raise an error)

```python
def get_function_hook(self, fullname: str):
    if fullname in self._literalenum_classes:
        return self._constructor_hook
    return None

def _constructor_hook(self, ctx: FunctionContext):
    if ctx.arg_types and ctx.arg_types[0]:
        arg_type = ctx.arg_types[0][0]
        # If arg is a specific literal that's a member, return it
        if isinstance(arg_type, LiteralType) and arg_type.value in members:
            return arg_type
    # Fallback: return the full union
    return self._make_literal_union(fullname)
```

**Tests:**
```python
reveal_type(HttpMethod("GET"))   # N: Revealed type is "Literal['GET']"
HttpMethod("git")                # E: ...
x = HttpMethod("GET")
handle(x)                        # ok (x is Literal["GET"], union accepts it)
```

### Phase 4: Iterator / Container Typing

Lower priority. Goal: type `list(HttpMethod)` and `dict(HttpMethod)` correctly.

**`list(HttpMethod)`** calls `__iter__` on the class. The metaclass defines `__iter__`
yielding values. mypy would need to know the return type of `HttpMethod.__iter__`.

In the base class hook, add:
```python
# __iter__ returns Iterator[Literal["GET", "POST", ...]]
add_method_to_class(ctx.api, ctx.cls, "__iter__",
    args=[], return_type=iterator_of_literal_union)
```

But `__iter__` is on the **metaclass**, not the class. For `list(HttpMethod)`, Python calls
`type(HttpMethod).__iter__(HttpMethod)`, i.e., the metaclass method. mypy handles
metaclass methods specially. This needs investigation:

- Does mypy resolve `iter(HttpMethod)` through the metaclass's `__iter__`?
- Can we type the metaclass's `__iter__` return correctly?

This might require `get_method_hook` for `LiteralEnumMeta.__iter__`.

**`dict(HttpMethod)`** uses the mapping protocol (`keys()` + `__getitem__`). Similar
metaclass considerations.

For the POC, these can have imperfect types and be refined later.

### Phase 5: Edge Cases

1. **`isinstance` narrowing:**
   ```python
   x: str = get_input()
   if isinstance(x, HttpMethod):  # runtime: works (metaclass __instancecheck__)
       reveal_type(x)             # static: mypy narrows to HttpMethod (class), not Literal union
   ```
   mypy doesn't know about custom `__instancecheck__`. This would narrow to the class
   type, not the Literal union. Could add special handling via `get_method_hook` for
   `builtins.isinstance`, but this is complex. **Accept as known limitation for POC.**

2. **`match`/`case`:**
   ```python
   match method:
       case "GET": ...    # works because method has type Literal["GET", "POST", ...]
   ```
   Should work naturally since the type is a Literal union. ✅

3. **Re-exports:**
   ```python
   # module_a.py
   class HttpMethod(LiteralEnum): GET = "GET"

   # module_b.py
   from module_a import HttpMethod  # fullname is still module_a.HttpMethod
   ```
   mypy resolves imports to original module. Should work. Needs testing.

4. **`reveal_type`:**
   ```python
   def handle(method: HttpMethod) -> None:
       reveal_type(method)  # Literal['GET', 'POST']  (not "HttpMethod")
   ```
   The revealed type would show the expanded Literal union, not "HttpMethod". This is
   technically correct but might surprise users. No fix without deeper mypy changes.

5. **Error messages:**
   ```python
   handle(123)
   # E: Argument 1 to "handle" has incompatible type "int";
   #    expected "str | str"  ← confusing, should say "HttpMethod"
   ```
   Error messages would reference the expanded union, not the original name. This is
   a known issue with type alias expansion in mypy. Could be partially addressed by
   using `TypeAliasType` instead of raw `UnionType`, but needs investigation.

6. **Non-string members:**
   ```python
   class StatusCode(LiteralEnum):
       OK = 200
       NOT_FOUND = 404
   ```
   The type analyze hook must construct `LiteralType` with the correct fallback type
   (`builtins.int` instead of `builtins.str`). The base class hook must detect the
   value type from the AST. `IntExpr` → int, `StrExpr` → str, `NameExpr("True")` → bool,
   `NameExpr("None")` → None.

---

## Risk Assessment

| Risk | Severity | Mitigation |
|---|---|---|
| Type analyze hook doesn't fire for forward references | Medium | mypy's multi-pass analysis re-analyzes deferred types. Test with forward refs early. |
| Incremental mode loses plugin state | Medium | Persist in TypeInfo.metadata, reconstruct lazily. |
| Error messages show expanded union, not "HttpMethod" | Low | Cosmetic. Investigate TypeAliasType wrapping. |
| `reveal_type` shows union, not class name | Low | Cosmetic. Same mitigation as above. |
| `isinstance` narrowing doesn't use Literal union | Medium | Accept for POC. Document as limitation. |
| Metaclass methods (__iter__, __contains__) not typed | Low | Iterator/container typing is Phase 4, not critical for POC. |
| Other mypy plugins conflict | Low | Standard plugin chaining. Test with common plugins. |

---

## Suggested Build Order

```
Step 1: Scaffold (project, tests, CI)
Step 2: Base class hook — member extraction + Final[Literal[...]] typing
Step 3: Type analyze hook — annotation expansion (THE critical test)
Step 4: Test the full matrix: handle("GET") ✅, handle("git") ❌, HttpMethod.GET ✅
Step 5: Constructor hook
Step 6: Inheritance (subclass adds members)
Step 7: Non-string types (int, bool, bytes, None)
Step 8: Incremental mode / caching
Step 9: Edge cases from Phase 5
Step 10: Package and publish
```

Step 3 is the moment of truth. If the type analyze hook successfully replaces
`HttpMethod` with the Literal union in annotation context while preserving class
attribute access, the entire approach is validated. Everything after that is
incremental.

---

## Minimal Spike (validate step 3 before building anything else)

Write the smallest possible plugin that proves the two-hook architecture works:

```python
# spike_plugin.py
from mypy.plugin import Plugin, ClassDefContext, AnalyzeTypeContext
from mypy.types import UnionType, LiteralType, Type

class SpikePlugin(Plugin):
    _known: dict[str, list[str]] = {}

    def get_base_class_hook(self, fullname: str):
        if fullname == "spike.LiteralEnum":
            return self._class_hook
        return None

    def _class_hook(self, ctx: ClassDefContext) -> None:
        # Hardcode for spike: just record that this class exists
        # Extract string values from uppercase assignments
        members = []
        for stmt in ctx.cls.defs.body:
            # ... extract literal values ...
            pass
        self._known[ctx.cls.fullname] = members

    def get_type_analyze_hook(self, fullname: str):
        if fullname in self._known:
            return self._type_hook
        return None

    def _type_hook(self, ctx: AnalyzeTypeContext) -> Type:
        members = self._known[...]
        str_type = ctx.api.named_type("builtins.str", [])
        literal_types = [LiteralType(v, str_type) for v in members]
        return UnionType.make_union(literal_types)

def plugin(version: str):
    return SpikePlugin
```

Test with:
```python
# test_spike.py
from spike import LiteralEnum

class HttpMethod(LiteralEnum):
    GET = "GET"
    POST = "POST"

def handle(method: HttpMethod) -> None: ...

handle("GET")            # should pass
handle(HttpMethod.GET)   # should pass
handle("git")            # should fail
```

Run: `mypy --plugin spike_plugin test_spike.py`

**If this works, the architecture is validated. Build everything else on top.**
