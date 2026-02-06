"""
mypy plugin for LiteralEnum.

Makes LiteralEnum subclasses behave as Literal unions in type-annotation
context while keeping them as normal classes for attribute access.

    class HttpMethod(LiteralEnum):
        GET = "GET"
        POST = "POST"

    # In type context:  HttpMethod → Literal["GET", "POST"]
    # In value context: HttpMethod.GET → Literal["GET"]  (unchanged class)

Enable in mypy.ini / pyproject.toml:

    [mypy]
    plugins = literalenum.mypy_plugin
"""

from __future__ import annotations

import sys
print("[literalenum] PLUGIN MODULE IMPORTED", file=sys.stderr)
from typing import Any, Callable

from mypy.nodes import (
    ARG_POS,
    Argument,
    AssignmentStmt,
    BytesExpr,
    IntExpr,
    NameExpr,
    StrExpr,
    TypeInfo,
    Var,
)
from mypy.plugin import (
    AnalyzeTypeContext,
    ClassDefContext,
    FunctionContext,
    Plugin,
)
from mypy.plugins.common import add_method_to_class
from mypy.types import (
    Instance,
    LiteralType,
    NoneType,
    Type,
    UnionType,
    get_proper_type,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

METADATA_KEY = "literalenum"

# Fully-qualified names of the LiteralEnum base class.
_BASE_FULLNAMES: frozenset[str] = frozenset(
    {
        "literalenum.LiteralEnum",
        "literalenum.literal_enum.LiteralEnum",
        "typing_literalenum.LiteralEnum",
    }
)

_TAG_TO_BUILTIN: dict[str, str] = {
    "str": "builtins.str",
    "int": "builtins.int",
    "bool": "builtins.bool",
    "bytes": "builtins.bytes",
}

# Member storage: {name: (value, type_tag)}
#   e.g. {"GET": ("GET", "str"), "OK": (200, "int")}
# The type_tag is one of: "str", "int", "bool", "bytes", "none"
Members = dict[str, tuple[Any, str]]


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------


def _extract_literal(expr: Any) -> tuple[Any, str] | None:
    """Return (value, type_tag) for a literal AST node, or None."""
    if isinstance(expr, StrExpr):
        return (expr.value, "str")
    if isinstance(expr, IntExpr):
        return (expr.value, "int")
    if isinstance(expr, BytesExpr):
        return (expr.value, "bytes")
    if isinstance(expr, NameExpr):
        if expr.name == "True":
            return (True, "bool")
        if expr.name == "False":
            return (False, "bool")
        if expr.name == "None":
            return (None, "none")
    return None


def _make_literal_type(
    value: Any,
    type_tag: str,
    named_type: Callable[..., Instance],
) -> Type:
    """Build a single mypy LiteralType (or NoneType for None)."""
    if type_tag == "none":
        return NoneType()
    fallback = named_type(_TAG_TO_BUILTIN[type_tag], [])
    return LiteralType(value, fallback)


def _make_union(members: Members, named_type: Callable[..., Instance]) -> Type:
    """Build a UnionType of Literal types from all member values."""
    types: list[Type] = []
    seen: set[tuple[Any, str]] = set()
    for _name, (value, type_tag) in members.items():
        key = (value, type_tag)
        if key in seen:
            continue
        seen.add(key)
        types.append(_make_literal_type(value, type_tag, named_type))
    if not types:
        # Degenerate: empty LiteralEnum ⇒ Never (nothing is assignable)
        return UnionType([])
    return UnionType.make_union(types)


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------


class LiteralEnumPlugin(Plugin):
    """
    Two-hook architecture:

    1. get_base_class_hook  – processes class definitions, types members
       as Final[Literal[...]], stores metadata.

    2. get_type_analyze_hook – intercepts type references in annotations
       and expands  HttpMethod → Literal["GET", "POST", ...]

    3. get_function_hook – refines the return type of constructor calls
       HttpMethod("GET") → Literal["GET"]
    """

    def __init__(self, options: Any) -> None:
        super().__init__(options)
        self._classes: dict[str, Members] = {}

    # ── hook registration ─────────────────────────────────────────────

    def _log(self, msg: str) -> None:
        print(f"[literalenum] {msg}", file=sys.stderr)

    def get_base_class_hook(
        self,
        fullname: str,
    ) -> Callable[[ClassDefContext], None] | None:
        if fullname in _BASE_FULLNAMES:
            return self._on_class_def
        return None

    def _is_literalenum_typeinfo(self, info: TypeInfo) -> bool:
        # If we've already tagged it, great.
        if METADATA_KEY in info.metadata:
            return True
        # Otherwise, check MRO for the base class.
        return any(base.fullname in _BASE_FULLNAMES for base in info.mro[1:])

    def get_type_analyze_hook(
            self, fullname: str
    ) -> Callable[[AnalyzeTypeContext], Type] | None:
        self._log(f"get_type_analyze_hook asked about: {fullname}")
        sym = self.lookup_fully_qualified(fullname)
        if not sym or not isinstance(sym.node, TypeInfo):
            return None
        if not self._is_literalenum_typeinfo(sym.node):
            return None

        def callback(ctx: AnalyzeTypeContext) -> Type:
            self._log(f"function_hook: {fullname}")
            members = self._resolve(fullname)
            if members is None:
                return ctx.type  # fall back to whatever mypy inferred
            return _make_union(members, ctx.api.named_type)

        return callback

    def get_function_hook(
            self, fullname: str
    ) -> Callable[[FunctionContext], Type] | None:
        self._log(f"get_type_analyze_hook asked about: {fullname}")
        sym = self.lookup_fully_qualified(fullname)
        if not sym or not isinstance(sym.node, TypeInfo):
            return None
        if not self._is_literalenum_typeinfo(sym.node):
            return None

        def callback(ctx: FunctionContext) -> Type:
            self._log(f"type_analyze: {fullname}")
            members = self._resolve(fullname)
            if members is None:
                return ctx.default_return_type
            return self._on_constructor(fullname, members, ctx)

        return callback


    # ── member resolution (cache + metadata fallback) ─────────────────

    def _resolve(self, fullname: str) -> Members | None:
        if fullname in self._classes:
            return self._classes[fullname]
        # Incremental mode: reconstruct from persisted TypeInfo.metadata
        sym = self.lookup_fully_qualified(fullname)
        if sym and sym.node and isinstance(sym.node, TypeInfo):
            meta = sym.node.metadata.get(METADATA_KEY)
            if meta and "members" in meta:
                members: Members = {
                    k: tuple(v) for k, v in meta["members"].items()
                }
                self._classes[fullname] = members
                return members
        return None

    # ── hook 1: base class — process class definition ─────────────────

    def _on_class_def(self, ctx: ClassDefContext) -> None:
        self._log(f"class_def: {ctx.cls.info.fullname}")
        info = ctx.cls.info

        # Inherit parent members (walk MRO)
        members: Members = {}
        for base in info.mro[1:]:
            parent_meta = base.metadata.get(METADATA_KEY)
            if parent_meta and "members" in parent_meta:
                for name, pair in parent_meta["members"].items():
                    members[name] = tuple(pair)

        # Collect own members from the class body
        for stmt in ctx.cls.defs.body:
            if not isinstance(stmt, AssignmentStmt) or len(stmt.lvalues) != 1:
                continue
            lvalue = stmt.lvalues[0]
            if not isinstance(lvalue, NameExpr):
                continue
            name = lvalue.name
            if not name.isupper() or name.startswith("_"):
                continue
            result = _extract_literal(stmt.rvalue)
            if result is None:
                continue
            members[name] = result

        # Persist (JSON-safe) and cache
        info.metadata[METADATA_KEY] = {
            "members": {k: list(v) for k, v in members.items()},
        }
        self._classes[info.fullname] = members

        # Type each member as Final[Literal[<value>]]
        for name, (value, type_tag) in members.items():
            sym = info.names.get(name)
            if sym is None or not isinstance(sym.node, Var):
                continue
            var = sym.node
            var.is_final = True
            var.type = _make_literal_type(value, type_tag, ctx.api.named_type)

        # Add __init__(self, value: <base_type>) -> None
        # so that HttpMethod("GET") is syntactically valid.
        # The function hook (below) refines the return type.
        if members:
            base_tags = sorted({tag for _, (_, tag) in members.items()})
            param_types: list[Type] = []
            for tag in base_tags:
                if tag == "none":
                    param_types.append(NoneType())
                else:
                    param_types.append(
                        ctx.api.named_type(_TAG_TO_BUILTIN[tag], [])
                    )
            param_type = (
                UnionType.make_union(param_types)
                if len(param_types) > 1
                else param_types[0]
            )
            add_method_to_class(
                ctx.api,
                ctx.cls,
                "__init__",
                args=[
                    Argument(
                        Var("value", param_type), param_type, None, ARG_POS
                    )
                ],
                return_type=NoneType(),
            )

    # ── hook 3: constructor return type ───────────────────────────────

    def _on_constructor(
        self,
        fullname: str,
        members: Members,
        ctx: FunctionContext,
    ) -> Type:
        if not ctx.arg_types or not ctx.arg_types[0]:
            return ctx.default_return_type

        arg_type = get_proper_type(ctx.arg_types[0][0])

        # Literal argument: validate membership and narrow return type
        if isinstance(arg_type, LiteralType):
            # Determine the type tag of this argument
            arg_tag: str | None = None
            if isinstance(arg_type.fallback, Instance):
                fb_name = arg_type.fallback.type.fullname
                for tag, builtin in _TAG_TO_BUILTIN.items():
                    if fb_name == builtin:
                        arg_tag = tag
                        break

            member_keys = {(v, t) for _, (v, t) in members.items()}
            if arg_tag and (arg_type.value, arg_tag) in member_keys:
                return arg_type  # narrow: HttpMethod("GET") → Literal["GET"]

            # Not a member — report error
            class_name = fullname.rsplit(".", 1)[-1]
            valid = ", ".join(repr(v) for _, (v, _) in members.items())
            ctx.api.fail(
                f'Value {arg_type.value!r} is not a member of '
                f'"{class_name}"; expected one of {valid}',
                ctx.context,
            )
            return ctx.default_return_type

        # NoneType argument
        if isinstance(arg_type, NoneType):
            if any(t == "none" for _, (_, t) in members.items()):
                return NoneType()

        # Non-literal (bare str, variable, etc.) — return the full union.
        # This is the best we can do without knowing the runtime value.
        return _make_union(members, ctx.api.named_generic_type)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def plugin(version: str) -> type[Plugin]:
    return LiteralEnumPlugin
