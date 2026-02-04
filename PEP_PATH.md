# LiteralEnum: Path to a Python PEP

## What Would It Take to Write a PEP and Get It Accepted?

Getting a typing PEP accepted is one of the harder things to do in the Python ecosystem. This document lays out the full path honestly.

---

## Phase 1: Pre-PEP Groundwork

Before writing a single line of PEP text, you need community signal. PEPs that arrive without prior discussion almost universally fail.

### 1.1 Build a Working Prototype

The typing-sig will not seriously engage with a proposal that doesn't have a working proof of concept. You need:

- **A published PyPI package** (`literalenum` or similar) with the runtime metaclass
- **A mypy plugin** that demonstrates the static typing behavior is achievable
- **A test suite** that maps to the 7 requirement groups, showing green for both runtime and mypy
- **Real-world usage** -- even if just in your own projects, having code that uses the pattern strengthens the argument

### 1.2 Start a typing-sig Discussion

The [typing-sig mailing list](https://mail.python.org/mailman3/lists/typing-sig.python.org/) (now also on Discourse) is where typing proposals get vetted. Post a discussion thread that:

1. **States the problem clearly** -- the README's motivation section is a strong start
2. **Shows the requirement matrix** -- the 8-approach comparison table is compelling
3. **Presents the proposed syntax** -- what you want users to write
4. **Links the working prototype** -- proves it's not just theoretical
5. **Asks for feedback** -- genuinely. The typing-sig regulars will find edge cases you haven't considered

Key people who tend to engage on typing-sig discussions:
- Eric Traut (pyright author)
- Jelle Zijlstra (mypy core, typing module maintainer)
- Rebecca Chen (mypy)
- Guido van Rossum (occasionally, for typing topics)
- Carl Meyer (Instagram/Meta, typing pragmatist)

### 1.3 Gauge Interest and Iterate

Expect 2-4 rounds of feedback. Common objections you should prepare for:

| Likely Objection | Preparation                                                                                                                                                                          |
|---|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| "Just use StrEnum" | Show the requirement matrix. The gap is 3.4/3.7 (raw literals not accepted).                                                                                                         |
| "Just use Literal + class" | Show it violates requirements 4 and 6.                                                                                                                                               |
| "This adds complexity to the type system" | Show that the pattern is already common (HTTP methods, status codes, event names, API string constants) and currently solved with duplicated code.                                   |
| "mypy plugin is sufficient" | Argue that cross-checker consistency matters; plugins are fragile and checker-specific.                                                                                              |
| "Enums should just be fixed" | I agree. In fact I would prefer this too if others are open to it. If the typing-sig prefers "make StrEnum members accepted as Literal values," that solves the problem differently. |

There are two philosophically different solutions:

- **A: New construct** (`LiteralEnum`) -- what you're proposing
- **B: Fix StrEnum** -- make type checkers treat `StrEnum` members as their literal values

The goal is solving the problem, not getting my specific syntax adopted.

---

## Phase 2: Writing the PEP

### 2.1 PEP Structure

Follow [PEP 1](https://peps.python.org/pep-0001/) and use existing typing PEPs as templates. The most relevant precedents:

- **PEP 586** -- `Literal` types (your PEP extends this)
- **PEP 589** -- `TypedDict` (class-based syntax for a typing construct -- closest structural analogy)
- **PEP 591** -- `Final` qualifier
- **PEP 655** -- `Required`/`NotRequired` for TypedDict
- **PEP 681** -- `@dataclass_transform` (teaches type checkers about custom decorators -- similar in spirit)

### 2.2 Required PEP Sections

```
PEP: <number>
Title: LiteralEnum -- Namespaced Literal Constants
Author: <you>
Sponsor: <a core dev, see below>
Status: Draft
Type: Standards Track
Topic: Typing
Python-Version: 3.xx
```

**Abstract** -- 2-3 sentences.

**Motivation** -- Why existing solutions fail. The requirement matrix is your strongest asset. Focus on:
- StrEnum's inability to accept raw string literals (3.4)
- Literal's lack of namespace (1.x)
- The duplication/two-class problem (4, 6)
- How common the use case is (HTTP methods, DB column types, API constants, event names, GraphQL enums, CLI argument choices)

**Rationale** -- Why this specific design. Address alternatives considered.

**Specification** -- Exact semantics. Must cover:
- Syntax (what users write)
- Runtime behavior (what `type()`, `isinstance()`, `==`, `is`, iteration, `json.dumps` do)
- Static type checker behavior (what passes, what fails, what `reveal_type` shows)
- Interaction with existing constructs (`Literal`, `Enum`, `Union`, `isinstance`, `match`/`case`)
- Supported value types (`str`, `int`, `bool`, `bytes`, `None`, `Enum` -- matching what `Literal` supports)

**Backwards Compatibility** -- What breaks? Ideally nothing.

**Reference Implementation** -- Working code. Two parts:
1. Runtime support in `typing` (or `typing_extensions` first)
2. Type checker support in at least one of mypy or pyright

**Rejected Ideas** -- Every alternative you considered and why it was insufficient.

### 2.3 You Need a Sponsor

Standards Track PEPs require a core developer sponsor. This person:
- Champions the PEP through the review process
- Vouches that the PEP is worth the Steering Council's time
- Doesn't need to agree with every detail, just that the problem is worth solving

Best candidates for this topic:
- **Jelle Zijlstra** -- typing module maintainer, very active
- **Guido van Rossum** -- if the proposal is compelling enough, has sponsored typing PEPs before
- **Barry Warsaw** -- enum module maintainer

You get a sponsor by first proving the idea has merit on typing-sig. Don't cold-email asking for sponsorship.

### 2.4 Proposed Syntax Options

Based on the project's exploration, there are several possible syntaxes to propose. The PEP should pick one and defend it:

**Option A: New special form**
```python
from typing import LiteralEnum

class HttpMethod(LiteralEnum):
    GET = "GET"
    POST = "POST"

def handle(method: HttpMethod) -> None: ...
handle("GET")           # OK
handle(HttpMethod.GET)  # OK
handle("got")           # Error
```

Pros: Cleanest syntax, most intuitive.
Cons: New concept to learn; type checkers must add special-case support.

**Option B: Extend StrEnum semantics**
```python
from enum import StrEnum

class HttpMethod(StrEnum):
    GET = "GET"
    POST = "POST"

# Type checkers now treat HttpMethod as equivalent to Literal["GET", "POST"]
# when used as a type annotation
```

Pros: No new syntax; builds on existing concept; smaller spec change.
Cons: Changing StrEnum semantics could break existing code; only works for str (not int, bool).

**Option C: Decorator on Literal**
```python
from typing import Literal, literalenum

@literalenum
class HttpMethod:
    GET: Final = "GET"
    POST: Final = "POST"

# Equivalent to: HttpMethod = Literal["GET", "POST"] with namespace
```

Pros: Similar to `@dataclass_transform` approach.
Cons: Decorator magic; less obvious what's happening.

---

## Phase 3: The Review Process

### 3.1 PEP Submission

1. Fork the [peps repository](https://github.com/python/peps)
2. Write the PEP in reStructuredText
3. Submit a PR
4. A PEP editor assigns a number

### 3.2 Discussion Period

- The PEP gets discussed on typing-sig and python-dev/Discourse
- Expect 1-3 months of active discussion
- You will need to revise the PEP multiple times based on feedback
- Be responsive and willing to change your proposal

### 3.3 SC (Steering Council) Decision

For typing PEPs, the process typically involves:

1. typing-sig reaches rough consensus
2. The PEP author (with sponsor) requests a pronouncement
3. The Steering Council (or their delegate for typing topics) accepts or rejects

Typical outcomes:
- **Accepted** -- proceed to implementation
- **Deferred** -- good idea, not the right time
- **Rejected** -- fundamental issues with the approach
- **Withdrawn** -- author decides a different path is better

### 3.4 Reference Implementation

Even before acceptance, you need at minimum:

- **typing_extensions support** -- a working implementation in typing_extensions
- **One type checker** -- mypy or pyright must have a working branch/PR

After acceptance:

- **CPython PR** -- add to `typing` module in the stdlib
- **mypy PR** -- full support
- **pyright PR** -- full support
- **Documentation** -- update docs.python.org typing docs

---

## Phase 4: What Could Go Wrong

### Likely Failure Modes

**1. "Not enough demand"**
The typing-sig may argue that the two-class pattern (Literal + namespace) is "good enough" for the small number of people who need this. Counter: show real-world codebases with the pattern, show Stack Overflow questions, show the duplication/bug surface.

**2. "Just fix StrEnum"**
If the community prefers making `StrEnum` members accepted as their literal values in type checking context, your PEP becomes unnecessary. This is actually a win -- the problem gets solved, just differently. Be ready to pivot to supporting this alternative PEP instead.

**3. "Too much type system complexity"**
Every new typing feature adds cognitive load. The typing community is increasingly cautious about this. Counter: `LiteralEnum` replaces complexity (multiple workarounds) with a single clear pattern.

**4. "Implementation burden on type checkers"**
mypy and pyright maintainers may push back on the implementation cost. Counter: the mypy plugin proves the implementation is tractable; PEP 681 (`@dataclass_transform`) set precedent for "teach type checkers about custom patterns."

**5. Scope creep**
If the discussion turns into "well, what about literal dicts, literal tuples, literal..." -- the PEP may get bogged down. Keep the scope tight: finite sets of literal values with namespaced access.

---

## Realistic Timeline

| Phase | What happens |
|---|---|
| **Now** | Polish runtime library, build mypy plugin, publish to PyPI |
| **After POC** | Post to typing-sig, gather feedback |
| **After feedback** | Iterate on design based on community input |
| **When consensus forms** | Write the PEP draft, find a sponsor |
| **After PEP submission** | 1-3 months discussion, multiple revisions |
| **After acceptance** | Implement in CPython, mypy, pyright |
| **Release** | Ships in Python 3.xx |

The Python typing PEP process is slow by design. PEP 586 (Literal) took about a year from first discussion to acceptance. PEP 681 (dataclass_transform) took roughly 18 months. Budget accordingly.

---

## Is It Worth It?

The problem is real and well-defined. The requirement matrix in the README is the strongest artifact -- it clearly shows that no existing solution covers the full space. The question is whether the Python community considers this a large enough pain point to justify a new typing construct.

The strongest argument in your favor: every Python web framework, CLI tool, and API client has string constants that would benefit from this. HTTP methods, status codes, event names, database dialects, log levels, content types -- the pattern is everywhere.

The strongest argument against: `StrEnum` + `Literal["GET", "POST"]` as a union type in function signatures is "close enough" for most people, even if it's not a single source of truth.

Build the POC. Let the code make the argument.
