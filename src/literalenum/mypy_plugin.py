"""
mypy plugin for LiteralEnum.

Makes LiteralEnum subclasses behave as Literal unions in type-annotation
context while keeping them as normal classes for attribute access.

    class HttpMethod(LiteralEnum):
        GET = "GET"
        POST = "POST"

    # In type context:  HttpMethod -> Literal["GET", "POST"]
    # In value context: HttpMethod.GET -> Literal["GET"]  (unchanged class)

Enable in mypy.ini / pyproject.toml:

    [mypy]
    plugins = literalenum.mypy_plugin
"""

from __future__ import annotations

import sys
from typing import Any, Callable

from mypy.nodes import (
    ARG_NAMED_OPT,
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
    AnyType,
    Instance,
    LiteralType,
    NoneType,
    Type,
    TypeOfAny,
    UnionType,
    get_proper_type,
)

print("[literalenum] PLUGIN MODULE IMPORTED", file=sys.stderr)


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
# Helpers
# ---------------------------------------------------------------------------


def _render_literal(value: Any, type_tag: str) -> str:
    """Render a literal value for error messages."""
    if type_tag == "str":
        return f'"{value}"'
    if type_tag == "none":
        return "None"
    return repr(value)


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
        return UnionType([])
    return UnionType.make_union(types)


def _get_bool_kwarg(ctx: ClassDefContext, name: str) -> bool | None:
    """Extract a boolean keyword argument from a class definition."""
    expr = ctx.cls.keywords.get(name)
    if expr is None:
        return None
    if isinstance(expr, NameExpr):
        if expr.name == "True":
            return True
        if expr.name == "False":
            return False
    return None


def _expected_list(members: Members) -> str:
    """Format member values for error messages: '"BLUE", "RED"'."""
    seen: set[tuple[Any, str]] = set()
    parts: list[str] = []
    for _name, (value, type_tag) in members.items():
        key = (value, type_tag)
        if key in seen:
            continue
        seen.add(key)
        parts.append(_render_literal(value, type_tag))
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------


class LiteralEnumPlugin(Plugin):
    """
    Hooks:

    1. get_base_class_hook  -- processes class definitions, types members,
       stores metadata, validates extend/allow_aliases, adds __init_subclass__.

    2. get_type_analyze_hook -- intercepts type references in annotations
       and expands  HttpMethod -> Literal["GET", "POST", ...]
       Returns the original class Instance in base-class context.

    3. get_function_hook -- validates constructor calls (call_to_validate),
       refines return types, and checks isinstance/issubclass misuse.
    """

    def __init__(self, options: Any) -> None:
        super().__init__(options)
        self._classes: dict[str, Members] = {}

    # -- hook registration -------------------------------------------------

    def _log(self, msg: str) -> None:
        # print(f"[literalenum] {msg}", file=sys.stderr)
        pass

    def get_base_class_hook(
        self,
        fullname: str,
    ) -> Callable[[ClassDefContext], None] | None:
        if fullname in _BASE_FULLNAMES:
            return self._on_class_def
        if fullname in self._classes:
            return self._on_class_def
        sym = self.lookup_fully_qualified(fullname)
        if sym and isinstance(sym.node, TypeInfo):
            if self._is_literalenum_typeinfo(sym.node):
                return self._on_class_def
        return None

    def _is_literalenum_typeinfo(self, info: TypeInfo) -> bool:
        if METADATA_KEY in info.metadata:
            return True
        return any(base.fullname in _BASE_FULLNAMES for base in info.mro[1:])

    def get_type_analyze_hook(
        self, fullname: str
    ) -> Callable[[AnalyzeTypeContext], Type] | None:
        sym = self.lookup_fully_qualified(fullname)
        if not sym or not isinstance(sym.node, TypeInfo):
            return None
        if not self._is_literalenum_typeinfo(sym.node):
            return None

        def callback(ctx: AnalyzeTypeContext) -> Type:
            # Detect base-class context: TypeAnalyser sets
            # allow_placeholder=True when analyzing base classes.
            # Return the original class Instance so subclassing works.
            if getattr(ctx.api, "allow_placeholder", False):
                inner_sym = self.lookup_fully_qualified(fullname)
                if inner_sym and isinstance(inner_sym.node, TypeInfo):
                    return Instance(inner_sym.node, [])

            members = self._resolve(fullname)
            if members is None:
                return ctx.type
            return _make_union(members, ctx.api.named_type)

        return callback

    def get_function_hook(
        self, fullname: str
    ) -> Callable[[FunctionContext], Type] | None:
        # Hook isinstance/issubclass to warn about LiteralEnum misuse.
        if fullname in ("builtins.isinstance", "builtins.issubclass"):
            return self._on_isinstance_or_issubclass

        # Hook LiteralEnum constructor calls.
        sym = self.lookup_fully_qualified(fullname)
        if not sym or not isinstance(sym.node, TypeInfo):
            return None
        if not self._is_literalenum_typeinfo(sym.node):
            return None

        def callback(ctx: FunctionContext) -> Type:
            members = self._resolve(fullname)
            if members is None:
                return ctx.default_return_type
            return self._on_constructor(fullname, members, ctx)

        return callback

    # -- member resolution -------------------------------------------------

    def _resolve(self, fullname: str) -> Members | None:
        if fullname in self._classes:
            return self._classes[fullname]
        sym = self.lookup_fully_qualified(fullname)
        if sym and sym.node and isinstance(sym.node, TypeInfo):
            meta = sym.node.metadata.get(METADATA_KEY)
            if meta and "members" in meta:
                members: Members = {k: tuple(v) for k, v in meta["members"].items()}
                self._classes[fullname] = members
                return members
        return None

    def _resolve_meta(self, fullname: str) -> dict[str, Any] | None:
        sym = self.lookup_fully_qualified(fullname)
        if sym and sym.node and isinstance(sym.node, TypeInfo):
            return sym.node.metadata.get(METADATA_KEY)
        return None

    # -- hook 1: class definition ------------------------------------------

    def _on_class_def(self, ctx: ClassDefContext) -> None:
        info = ctx.cls.info

        # --- Extract keyword arguments ---
        extend = _get_bool_kwarg(ctx, "extend") or False
        call_to_validate_kwarg = _get_bool_kwarg(ctx, "call_to_validate")
        allow_aliases_kwarg = _get_bool_kwarg(ctx, "allow_aliases")

        # --- Inherit parent metadata ---
        parent_call_to_validate = False
        parent_allow_aliases = True
        parent_has_members = False
        parent_name = ""
        members: Members = {}
        for base in info.mro[1:]:
            parent_meta = base.metadata.get(METADATA_KEY)
            if parent_meta:
                if not parent_has_members and parent_meta.get("members"):
                    parent_has_members = True
                    parent_name = base.name
                if "call_to_validate" in parent_meta:
                    parent_call_to_validate = parent_meta["call_to_validate"]
                if "allow_aliases" in parent_meta:
                    parent_allow_aliases = parent_meta["allow_aliases"]
                for name, pair in parent_meta.get("members", {}).items():
                    members[name] = tuple(pair)

        # Resolve inherited flags
        call_to_validate = (
            call_to_validate_kwarg
            if call_to_validate_kwarg is not None
            else parent_call_to_validate
        )
        allow_aliases = (
            allow_aliases_kwarg
            if allow_aliases_kwarg is not None
            else parent_allow_aliases
        )

        # --- Validate: subclassing without extend=True ---
        if parent_has_members and not extend:
            ctx.api.fail(
                f"Cannot subclass '{parent_name}' without extend=True; "
                f"it already has members",
                ctx.cls,
            )

        # --- Collect own members ---
        own_members: Members = {}
        for stmt in ctx.cls.defs.body:
            if not isinstance(stmt, AssignmentStmt) or len(stmt.lvalues) != 1:
                continue
            lvalue = stmt.lvalues[0]
            if not isinstance(lvalue, NameExpr):
                continue
            name = lvalue.name
            if name.startswith("_"):
                continue
            result = _extract_literal(stmt.rvalue)
            if result is None:
                continue
            own_members[name] = result

        # --- Validate: duplicate values with allow_aliases=False ---
        if not allow_aliases:
            # Build a map of (value, tag) -> canonical name from
            # inherited members first.
            seen_values: dict[tuple[Any, str], str] = {}
            for mname, (mvalue, mtag) in members.items():
                key = (mvalue, mtag)
                if key not in seen_values:
                    seen_values[key] = mname

            for name, (value, type_tag) in own_members.items():
                key = (value, type_tag)
                if key in seen_values:
                    existing = seen_values[key]
                    ctx.api.fail(
                        f"Duplicate value {_render_literal(value, type_tag)}: "
                        f"'{name}' is an alias for '{existing}' "
                        f"(allow_aliases=False)",
                        ctx.cls,
                    )
                else:
                    seen_values[key] = name

        members.update(own_members)

        # --- Persist metadata and cache ---
        info.metadata[METADATA_KEY] = {
            "members": {k: list(v) for k, v in members.items()},
            "call_to_validate": call_to_validate,
            "allow_aliases": allow_aliases,
        }
        self._classes[info.fullname] = members

        # --- Type each own member as Literal[...] ---
        for name, (value, type_tag) in own_members.items():
            sym = info.names.get(name)
            if sym and isinstance(sym.node, Var):
                var = sym.node
                var.type = _make_literal_type(
                    value, type_tag, ctx.api.named_type
                )

        # --- Add __init__ so the function hook can fire for calls ---
        # We always add __init__ accepting member types; the function hook
        # checks call_to_validate and reports errors for non-callable classes.
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

        # --- Add __init_subclass__ with keyword args ---
        bool_type = ctx.api.named_type("builtins.bool", [])
        add_method_to_class(
            ctx.api,
            ctx.cls,
            "__init_subclass__",
            args=[
                Argument(
                    Var("extend", bool_type),
                    bool_type,
                    NameExpr("False"),
                    ARG_NAMED_OPT,
                ),
                Argument(
                    Var("allow_aliases", bool_type),
                    bool_type,
                    NameExpr("True"),
                    ARG_NAMED_OPT,
                ),
                Argument(
                    Var("call_to_validate", bool_type),
                    bool_type,
                    NameExpr("False"),
                    ARG_NAMED_OPT,
                ),
            ],
            return_type=NoneType(),
            is_classmethod=True,
        )

    # -- hook: isinstance / issubclass ------------------------------------

    def _on_isinstance_or_issubclass(self, ctx: FunctionContext) -> Type:
        """Warn when isinstance/issubclass is used with a LiteralEnum."""
        if len(ctx.args) >= 2 and ctx.args[1]:
            cls_expr = ctx.args[1][0]
            if isinstance(cls_expr, NameExpr) and cls_expr.node:
                node = cls_expr.node
                if isinstance(node, TypeInfo) and self._is_literalenum_typeinfo(node):
                    # Determine function name from the callee
                    func_name = "isinstance"
                    if hasattr(ctx.context, "callee"):
                        callee = getattr(ctx.context, "callee")
                        if isinstance(callee, NameExpr):
                            func_name = callee.name
                    ctx.api.fail(
                        f"{func_name}() is not supported for LiteralEnum "
                        f"subclass '{node.name}'; LiteralEnum values are "
                        f"plain literals, not class instances",
                        ctx.context,
                    )
        return ctx.default_return_type

    # -- hook: constructor calls -------------------------------------------

    def _on_constructor(
        self,
        fullname: str,
        members: Members,
        ctx: FunctionContext,
    ) -> Type:
        class_name = fullname.rsplit(".", 1)[-1]

        # Check call_to_validate flag
        meta = self._resolve_meta(fullname)
        call_to_validate = meta.get("call_to_validate", False) if meta else False

        if not call_to_validate:
            ctx.api.fail(
                f"'{class_name}' is not callable; use {class_name}.validate(x) "
                f"or pass call_to_validate=True",
                ctx.context,
            )
            return ctx.default_return_type

        if not ctx.arg_types or not ctx.arg_types[0]:
            return ctx.default_return_type

        arg_type = get_proper_type(ctx.arg_types[0][0])

        # Extract LiteralType: either directly, or from Instance.last_known_value
        literal: LiteralType | None = None
        if isinstance(arg_type, LiteralType):
            literal = arg_type
        elif isinstance(arg_type, Instance) and arg_type.last_known_value is not None:
            literal = arg_type.last_known_value

        # Literal argument: validate membership and narrow return type
        if literal is not None:
            arg_tag: str | None = None
            if isinstance(literal.fallback, Instance):
                fb_name = literal.fallback.type.fullname
                for tag, builtin in _TAG_TO_BUILTIN.items():
                    if fb_name == builtin:
                        arg_tag = tag
                        break

            member_keys = {(v, t) for _, (v, t) in members.items()}
            if arg_tag and (literal.value, arg_tag) in member_keys:
                return literal  # narrow: ValidatedColors("BLUE") -> Literal["BLUE"]

            # Not a member
            expected = _expected_list(members)
            ctx.api.fail(
                f'Value {_render_literal(literal.value, arg_tag or "str")} '
                f'is not a member of {class_name}; '
                f'expected one of: {expected}',
                ctx.context,
            )
            return ctx.default_return_type

        # NoneType argument
        if isinstance(arg_type, NoneType):
            if any(t == "none" for _, (_, t) in members.items()):
                return NoneType()

        # Non-literal (bare str, variable, etc.) -- return the full union.
        return _make_union(members, ctx.api.named_generic_type)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def plugin(version: str) -> type[Plugin]:
    """Mypy plugin entry point."""
    return LiteralEnumPlugin
