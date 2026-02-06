## Idea: `KeyOf[T]`, `TypeOf[T, K]`, `ValueOf[T]`

Python has lots of “schema-like” types (TypedDicts, dataclasses, annotated classes, etc.), 
but today we can’t *statically* reflect their keys and field types. 
That forces “magic strings” and `Any` holes in libraries and helpers. 
The proposal adds three small, orthogonal type operators:

* **`KeyOf[T]`**: the valid keys/field names of `T`
* **`TypeOf[T, K]`**: the type of field/key `K` on `T`
* **`ValueOf[T]`**: `TypeOf[T, KeyOf[T]]` (union of all possible field value types)

This unlocks type-safe dynamic access patterns without runtime cost and without duplicating literal unions by hand.

This is the same shape as the recent “FieldKey/FieldType” static reflection pitch—just with shorter, more general names 
and added support for `ValueOf[T]` which solves some painpints with `Enum` and `Literal` types. 
([Discussions on Python.org][1])

---

## What you can do with it

### TypedDict

```py
class User(TypedDict):
    id: int
    name: str
    
assert KeyOf[User] == Literal["id", "name"]
assert ValueOf[User] == (int | str)
assert TypeOf[User, "id"] == int
assert TypeOf[User, "unspecified"] == Never  # this would also give a Type check error

def get(u: User, k: KeyOf[User]) -> TypeOf[User, k]:
    return u[k]
```

* `KeyOf[User]` is `Literal["id", "name"]`
* `TypeOf[User, "id"]` is `int`
* `ValueOf[User]` is `int | str`

This directly solves the “magic string” problem the FieldKey/FieldType thread targets. ([Discussions on Python.org][1])

### Dataclasses

```py
@dataclass
class Point:
    x: float
    y: float

KeyOf[Point]        # Literal["x","y"]
TypeOf[Point,"x"]   # float
ValueOf[Point]      # float

get_keys(Point) == ["x", "y"]  # also valuable to have an easy, public way to iterate keys and values
get_value_type(Point) is float
get_typeof(Point, "x") is float
```

### Regular annotated classes

```py
class User:
    id: int
    name: str
```

Same as dataclasses: it’s about *declared* fields, not runtime mutation.

### `dict[str, int]` and other `Mapping[K, V]`

```python
T = dict[str, int]
assert KeyOf[T] is str
assert ValueOf[T] is int
assert TypeOf[T, "a"] == (int | Never)
```
So it’s still useful (generic helpers), just not literal-exhaustive.

### Enums (what it is *and isn’t*)

Enums don’t naturally fit the “schema key → field type” model people want. The pain in the enum/literal discussions is usually “I want a *closed value set* and exhaustiveness,” which is why the “Enum values are subtypes of Literal” idea came up. ([Discussions on Python.org][2])

With `KeyOf/TypeOf/ValueOf`, the *reasonable* enum interpretation is:

```python
class Color(StrEnum):
    RED = "RED"
    BLUE = "BLUE"
    
assert KeyOf[Color] == Literal["RED","BLUE"]
assert ValueOf[Color] is Color
assert TypeOf[Color, "RED"] is Color
assert TypeOf[Color, "apple"] is Never
```
That doesn’t solve “values as literals” by itself (that’s a separate feature area).

---

## Restrictions (to keep it implementable + not misleading)

### 1) Only “schema-defined” keys are reflected

For `KeyOf[T]` to be `Literal[...]`, `T` must be a *finite schema type*, like:

* `TypedDict`
* dataclass / NamedTuple
* normal class with annotated instance attributes (and possibly schema Protocols)

For these, keys come from **static annotations**, not from `__getattr__`, `__getitem__`, descriptors, metaclasses, etc. (Descriptors can change attribute behavior in ways static typing can’t soundly model.) ([Python documentation][3])

### 2) Mutations are not “picked up”

If code does `obj.new_attr = ...` or `del obj.field`, type checkers **do not** update `KeyOf[T]`. This is the same principle as the rest of Python typing: it reflects *declared types*, not all runtime side effects.

### 3) No `Final` requirement for schema fields

For TypedDict/dataclass/annotated-class fields, requiring `Final` would be a non-starter ergonomically and doesn’t match Python’s model. `Final` is more relevant to “reflecting literal *values* from runtime constants” (the LiteralEnum/value-set discussion), not to reflecting schema shapes. ([Discussions on Python.org][4])


---

## Prior work / why similar ideas get stuck

This “keyof/typeof” idea comes up a lot from TypeScript users. 
TypeScript can do it broadly because it’s deeply structural; 
Python typing is more nominal and cautious, so most “do TS keyof in Python” questions get answered with “not really” today. 
([Stack Overflow][5])

Inside the typing community, closely related proposals have circulated for years (often with Mapping/TypedDict operators like `KeyType`/`ElementType`, etc.). ([GitHub][6]) The recurring blockers tend to be:
* scope creep (trying to cover *all* objects, not just schema types)
* hard edge cases (descriptors, dynamic attrs, unions, partial TypedDicts)
* soundness (esp. around enums/literals, where equality and matching can be surprising) ([Discussions on Python.org][2])


If you want, I can turn this into a 1–2 page “spec skeleton” (definitions + supported types + union rules) that reads like a typing PEP section.

[1]: https://discuss.python.org/t/pep-idea-static-reflection-for-schema-types-fieldkey-and-fieldtype/105888?utm_source=chatgpt.com "Static Reflection for Schema Types (FieldKey and FieldType)"
[2]: https://discuss.python.org/t/amend-pep-586-to-make-enum-values-subtypes-of-literal/59456?utm_source=chatgpt.com "Amend PEP 586 to make `enum` values subtypes of `Literal`"
[3]: https://docs.python.org/3/howto/descriptor.html?utm_source=chatgpt.com "Descriptor Guide"
[4]: https://discuss.python.org/t/proposal-literalenum-runtime-literals-with-static-exhaustiveness/106000?utm_source=chatgpt.com "LiteralEnum — runtime literals with static exhaustiveness"
[5]: https://stackoverflow.com/questions/76018208/python-typing-equivalent-of-typescripts-keyof?utm_source=chatgpt.com "Python typing equivalent of TypeScript's keyof"
[6]: https://github.com/python/typing/discussions/1412?utm_source=chatgpt.com "Proposal: KeyType and ElementType for TypedDicts (also, ..."
