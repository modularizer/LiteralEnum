# Original Post: 
https://discuss.python.org/t/proposal-literalenum-runtime-literals-with-static-exhaustiveness/106000

**Subject:** Proposal: LiteralEnum : runtime literals with static exhaustiveness

Hello typing community,

I’d like feedback on a possible typing construct tentatively called **`LiteralEnum`**, aimed at a common gap between `Enum/StrEnum` and `typing.Literal`.

**Problem**
Many APIs use small, closed sets of scalar values (often strings: HTTP methods, event names, config keys). At runtime, these are most ergonomic as *plain literals*, but statically we want *exhaustiveness checking*.

Today this usually leads to duplication, e.g. a constants namespace plus a parallel `Literal[...]` union, or forcing callers to pass enum members instead of raw values.

**Proposed idea**
`LiteralEnum` defines a finite, named set of literal values that:

* are plain runtime literals (`str`, `int`, `bool`, `None`, etc.),
* provide a runtime namespace, iteration, and validation, and
* are treated by type checkers as an exhaustive `Literal[...]` union.
* This is not intended to replace Enum or Literal, but to cover the narrow case where literal values themselves are the API surface.

Minimal example:

```python
from typing import LiteralEnum

class HttpMethod(LiteralEnum):
    GET = "GET"
    POST = "POST"
    DELETE = "DELETE"

def handle(method: HttpMethod) -> None:
    ...

handle("GET")          # accepted
handle(HttpMethod.GET) # accepted
handle("git")          # type checker error
```

At runtime:

* `HttpMethod.GET == "GET"`
* `list(HttpMethod) == ["GET", "POST", "DELETE"]`
* `"GET" in HttpMethod` can be used to check if a string is valid
* `HttpMethod("GET")` could optionally validate and return `"GET"` (acknowledging that callable classes usually construct instances)

At type-check time, `HttpMethod` is equivalent to:

```python
Literal["GET", "POST", "DELETE"]
```

Subclass extension is explicit (`extend=True`) to avoid accidental widening.

**Status**

* I have a small runtime prototype as a proof of concept (linked below, under 200 lines); it does not attempt to solve the type-checker side yet
* I’m interested in whether this direction seems:

  * useful enough to justify checker support, and
  * compatible with existing typing model assumptions.

Draft PEP (early): https://github.com/modularizer/LiteralEnum/blob/master/PEP.md
Runtime prototype: https://github.com/modularizer/LiteralEnum/blob/master/src/typing_literalenum.py

I’m not attached to the name or the source code, I'm looking to validate the *concept* and scope before going further.

Questions for discussion:
1. Do other people feel this pain point as much as me?
2. Have you found yourself writing duplicate types: a (`Literal` plus an `Enum` or just a bare class with attributes)?
3. Are there alternative designs that could provide a runtime namespace and an exhaustive type hint, without introducing a new core typing construct?


Thanks for any feedback,
Torin


Edit: I found these similar discussions which I believe stem from the same pain point but propose different solutions:
- https://discuss.python.org/t/amend-pep-586-to-make-enum-values-subtypes-of-literal/59456
- https://github.com/python/typing/issues/781

# Follow-up
Thanks for all the feedback : lots of great ideas here. I want to respond to a few points individually, then step back and frame what I'm personally looking for.

**Quick responses:**

@jorenham : yes, you can think of it like that. The extra value over a general sum type is primarily namespace, iteration, and validation out of the box

@Tinche : the `ParamOf` idea is creative. It seems very useful and I love that it is general. Is not quite the first-class treatment that I think is worth considering for `LiteralEnum` proposal, but I see its value

@Randolf Sholz : I like your PEP 586 amendment and think it solves an important direction: using `HttpMethod.GET` where `Literal["GET"]` is expected. I also understand Jelle's response and see value in having `Literal` typehints only match true literals. The gap is the other direction : passing a plain `"GET"` to a function typed `method: HttpMethod` still fails. LiteralEnum tries to make both directions work, which cannot be done by modifying `Enum` ( it would break stuff )

@peter : the `get_args` pattern is clean for getting runtime iterable from a `Literal`. The thing it's missing is namespace access : there's no `HttpMethod.GET` to write in code, and you still end up with two separate names to maintain.

@tmk : your `Final` + `__members__` class is almost exactly the pattern that motivated this proposal! I think it is a great pattern in the current ecosystem, but I would love to see a pattern supporting a single source of truth in future versions of Python

@Dutcho : good point about `type HttpMethod = ...` requiring `get_args(HttpMethod.__value__)`. Another example of how current tools make you choose between "nice for the type checker" and "nice at runtime."

@beauxq : making `in` work on `Literal` directly would be fantastic. It would not solve all pain points, but I see that as a step in the right direction

---

**What I'm aiming for**

Today, getting everything I want requires something like three separate constructs:

```python
FieldTypeT = Literal["A", "B"]

class FieldType:
    A: Final[Literal["A"]] = "A"
    B: Final[Literal["B"]] = "B"

FieldTypes: Iterable[FieldTypeT] = {"A", "B"}
```

...but it KILLS me that this has no single source of truth : every value is written three times.

(To @peter's point, `get_args` does give you a single source of truth for the `Literal` + `Iterable`, but not the namespace. And as @Dutcho noted, even `get_args` gets clunkier with the `type` statement.)

I wanted to lay out my personal litmus tests for what I'd want from a solution. You are more than welcome to disagree with these goals and voice your own preferences : it would be interesting to hear where people draw different lines. For me:

1. **Namespace** for member access, e.g. `FieldType.A`
    - `Literal` fails this, and I see it as `Literal`'s biggest weakness
2. **Raw literals accepted**: `"A"` should be an acceptable input to a param typed as `t: FieldType`
    - `Enum/StrEnum` fail this and I see it as their biggest weakness for SOME use cases
    - NOTE: there are definitely times devs WANT to reject raw strings to avoid floating literals : I would not want to change `Enum/StrEnum` behavior here
3. **Named members accepted**: `FieldType.A` should be an acceptable input to a param typed as `t: FieldType`
    - comparing an `Enum` member against a `Literal` type hint currently fails, and I think this is one thing @Randolf Sholz was trying to address with his PEP 586 amendment
4. **Iteration and containment**: `x in FieldType` and `for x in FieldType` should be first-class
    - both `Literal` and `Enum` provide ways to do this, but it could be more natural (and as @beauxq suggested, even `Literal` could benefit from `in` support)
5. **Single source of truth**: if I have to write `"A"` more than once when defining my type, it fails this test
6. **One type, not two**: most current solutions require separate variables for different parts of the functionality, which I find error-prone

Here's how the current approaches score:

| Approach                               | #1 Namespace | #2 Raw lit | #3 Member | #4 Iterate | #5 Single source | #6 One type that does it all |
|----------------------------------------|--------------|------------|-----------|------------|------------------|------------------------------|
| `Literal` alone                        | ❌            | ✅          | ❌         | ❌          | ✅                | ❌                            |
| `Literal` + `get_args` (@peter)        | ❌            | ✅          | ❌         | ✅          | ✅                | ❌                           |
| `StrEnum`                              | ✅            | ❌          | ✅         | ✅          | ✅                | ❌                            |
| `StrEnum` + PEP 586 amend (@Randolf)   | ✅            | ❌          | ✅         | ✅          | ✅                | ❌                            |
| `Enum` + `ParamOf` (@Tinche)           | ✅            | ✅          | ✅         | ✅          | ✅                | ❌                            |
| `Final` class + `Literal` alias (@tmk) | ✅            | ⚠️         | ✅         | ⚠️         | ❌                | ❌                           |
| Runtime `in` on `Literal` (@beauxq)    | ❌            | ✅          | ❌         | ⚠️         | ✅                | ❌                            |
| **LiteralEnum (proposed)**             | ✅            | ✅          | ✅         | ✅          | ✅                | ✅                            |

As far as why I'm suggesting a new type rather than modifying an existing one:
1. I worry about accidentally breaking existing behavior
    - I like @Randolf Sholz's suggestion, and think it's a reasonable addition to `Enum` that would help with #3, although Jelle's response there makes sense as well
    - I don't see a way to make `Enum` pass #2 without conflicting with code that intentionally requires enum members
    - My suggestion is much closer to "`Literal` with namespace features" than it is to being an actual `Enum` (certainly open to a rename if that's a point of tension)

---

@randolf-scholz you make a great point and that is definitely a key discussion point I am eager to get feedback on.

Should `FieldType.A` be ...
 A. (Proposed) of type `str` (JUST the raw literal) or of 
 B. (similar to StrEnum) having a type which is a subclass like `str, FieldType`?

My thoughts:
- I absolutely see value in what you are proposing, but for me, the value add is not enough to justify  the added complication
- Your proposal would make `LiteralEnum` lean towards being more like `Enum` and less like `Literal`
- option B. has some niceties, but also may lead to a lack of trust and immediate recognition
  - when I see the subclassing, I immediately jump to "what broke?"
  - with a good implementation, the answer may very well be that absolutely nothing broke
  - BUT... if I do not have the time to verify myself, I don't have the immediate trust
  - So... I wind up doing extra work like casting `str(HttpMethod.GET)`, etc. until I read the source code or get convinced
- I do not personally feel any pain points with the values not being an instance of the special type
  - If I wanted a `StrEnum` I could use one. It has value on its own, and yes maybe `StrEnum` could be improved by your PEP propsal or something similar
  - I am more focused on building off of the functionality of `Literal` than on extending the functionality of `StrEnum`

While I lean towards continuing to propose option A, I would still be thrilled if option B gained traction, and would help advocate for it.

Do others see advantages of the members having a special type as opposed to being more like a namespace that retains the true raw literal type?