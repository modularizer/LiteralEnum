from typing import Literal

from literalenum import LiteralEnum
from literalenum.samples.http import HttpMethod


# ============================================================
# 1. Type annotation: HttpMethod treated as Literal["GET", "POST", ...]
# ============================================================

def handle(method: HttpMethod) -> None:
    print(method)

handle("GET")              # OK — valid member
handle("POST")             # OK — valid member
handle(HttpMethod.GET)     # OK — resolves to Literal["GET"]
handle(HttpMethod.POST)    # OK — resolves to Literal["POST"]
handle("git")              # ERROR — not a member of HttpMethod
handle("POS")              # ERROR — not a member of HttpMethod
handle(99)                 # ERROR — not a member of HttpMethod


# ============================================================
# 2. Member access typing
# ============================================================

m1 = HttpMethod.GET        # typed as Literal["GET"]
m2 = HttpMethod.DELETE     # typed as Literal["DELETE"]
# HttpMethod.NONEXISTENT  # would be unresolved reference (PyCharm built-in)

assert isinstance(HttpMethod.GET, str)   # True at runtime: values ARE strings
assert HttpMethod.GET == "GET"           # True
assert type(HttpMethod.GET) is str       # True


# ============================================================
# 3. isinstance / issubclass — not supported
# ============================================================

z1 = isinstance("GET", HttpMethod)   # ERROR — isinstance() not supported for LiteralEnum
z2 = issubclass(str, HttpMethod)     # ERROR — issubclass() not supported for LiteralEnum


# ============================================================
# 4. Calling / instantiation
# ============================================================

class Colors(LiteralEnum):
    BLUE = "BLUE"
    RED = "RED"

c1 = Colors("BLUE")       # ERROR — 'Colors' is not callable; use Colors.validate(x) or pass call_to_validate=True


class ValidatedColors(LiteralEnum, call_to_validate=True):
    BLUE = "BLUE"
    RED = "RED"

c2 = ValidatedColors("BLUE")    # OK — call_to_validate=True, valid member
c3 = ValidatedColors("GREEN")   # ERROR — "GREEN" is not a member of ValidatedColors


# ============================================================
# 5. extend=True — required when subclassing a populated LiteralEnum
# ============================================================

class MoreMethods(HttpMethod, extend=True):   # OK — extend=True present
    OPTIONS = "OPTIONS"
    HEAD = "HEAD"

class BadSubclass(HttpMethod):    # ERROR — Cannot subclass 'HttpMethod' without extend=True
    CONNECT = "CONNECT"

class EmptyBase(LiteralEnum):     # OK — no members
    pass

class FromEmpty(EmptyBase):       # OK — EmptyBase has no members, extend not needed
    ALPHA = "alpha"


# ============================================================
# 6. allow_aliases — duplicate value detection
# ============================================================

class WithAliases(LiteralEnum):               # OK — aliases allowed by default
    GET = "GET"
    get = "GET"

class StrictColors(LiteralEnum, allow_aliases=False):
    RED = "red"
    CRIMSON = "red"    # ERROR — Duplicate value "red": 'CRIMSON' is an alias for 'RED'

class InheritedStrict(StrictColors, extend=True):
    SCARLET = "red"    # ERROR — inherits allow_aliases=False from StrictColors


# ============================================================
# 7. Parameter type checking with another LiteralEnum
# ============================================================

def print_color(c: Literal["PURPLE"] | Colors) -> None:
    print(f"{c=}")

print_color("BLUE")         # OK — valid member
print_color("RED")           # OK — valid member
print_color("PURPLE")           # OK — valid member
print_color("GREEN")         # ERROR — not a member of Colors
print_color(Colors.BLUE)     # OK — resolves to Literal["BLUE"]


# ============================================================
# 8. Container protocol — runtime features
# ============================================================

x = "GET" in HttpMethod             # OK — containment check
y = "INVALID" in HttpMethod         # OK — returns False at runtime, not a type error

options: list[HttpMethod] = list(HttpMethod)
mapping = HttpMethod.mapping
all_values = HttpMethod.values()
all_keys = HttpMethod.keys()
all_items = HttpMethod.items()
is_valid = HttpMethod.is_valid("GET")
validated = HttpMethod.validate("GET")


# ============================================================
# 9. Mixed-type LiteralEnum
# ============================================================

class MixedTypes(LiteralEnum):
    NAME = "hello"
    CODE = 42
    FLAG = True
    NOTHING = None

def process(val: MixedTypes) -> None: ...

process("hello")    # OK
process(42)         # OK
process(True)       # OK
process(None)       # OK
process("other")    # ERROR — not a member
process(99)         # ERROR — not a member


# ============================================================
# 10. Extended class includes parent members in type
# ============================================================

def handle_extended(method: MoreMethods) -> None: ...

handle_extended("GET")       # OK — inherited from HttpMethod
handle_extended("OPTIONS")   # OK — own member
handle_extended("CONNECT")   # ERROR — not a member of MoreMethods
