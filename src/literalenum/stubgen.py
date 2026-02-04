from __future__ import annotations

import argparse
import ast
import importlib
import importlib.util
import inspect
import pkgutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from literalenum import LiteralEnum


# ----------------------------
# Discovery
# ----------------------------

def _iter_modules(root: str) -> Iterable[str]:
    pkg = importlib.import_module(root)
    if not hasattr(pkg, "__path__"):
        yield root
        return

    yield root
    for modinfo in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
        yield modinfo.name


def _module_origin_py(module: str) -> Path | None:
    spec = importlib.util.find_spec(module)
    if not spec or not spec.origin or spec.origin in ("built-in", "namespace"):
        return None
    p = Path(spec.origin)
    return p if p.suffix == ".py" else None


def _module_to_adjacent_stub_path(module: str) -> Path | None:
    origin = _module_origin_py(module)
    if origin is None:
        return None
    if origin.name == "__init__.py":
        return origin.with_name("__init__.pyi")
    return origin.with_suffix(".pyi")


def _module_to_stub_path(stub_root: Path, module: str) -> Path:
    rel = Path(*module.split("."))
    return stub_root / (str(rel) + ".pyi")


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _py_literal(v: Any) -> str:
    # Emit double quotes for strings for nicer stubs.
    if isinstance(v, str):
        return '"' + v.replace('"', '\\"') + '"'
    return repr(v)


@dataclass(frozen=True)
class EnumInfo:
    module: str
    name: str
    qualname: str
    bases: tuple[type, ...]
    members: dict[str, Any]  # name -> value (from runtime mapping)


def _find_literal_enums(root: str) -> list[EnumInfo]:
    infos: list[EnumInfo] = []
    for modname in _iter_modules(root):
        try:
            mod = importlib.import_module(modname)
        except Exception:
            continue

        for _, obj in inspect.getmembers(mod, inspect.isclass):
            if obj is LiteralEnum:
                continue
            if issubclass(obj, LiteralEnum) and obj.__module__ == mod.__name__:
                members = dict(getattr(obj, "mapping"))
                infos.append(
                    EnumInfo(
                        module=obj.__module__,
                        name=obj.__name__,
                        qualname=f"{obj.__module__}.{obj.__name__}",
                        bases=getattr(obj, "__bases__", ()),
                        members=members,
                    )
                )
    return infos


# ----------------------------
# Rendering enum stubs
# ----------------------------

def _render_enum_blocks(enums: list[EnumInfo]) -> str:
    """
    Render ONLY enum-related stubs for a module:
      - <EnumName>T = Literal[...]
      - class <EnumName>(Base): ...
    """
    by_qual = {e.qualname: e for e in enums}

    def _qual_of(cls: type) -> str:
        return f"{getattr(cls, '__module__', '')}.{getattr(cls, '__name__', '')}"

    def _enum_base_decl(e: EnumInfo) -> str:
        # If base is another emitted enum in the same module, preserve that inheritance.
        for b in e.bases:
            if _qual_of(b) in by_qual:
                return b.__name__
        return f"LiteralEnum[{e.name}T]"

    def _inherited_member_names(e: EnumInfo) -> set[str]:
        names: set[str] = set()
        for b in e.bases:
            qb = _qual_of(b)
            if qb in by_qual:
                names |= set(by_qual[qb].members.keys())
        return names

    out: list[str] = []
    for e in sorted(enums, key=lambda x: x.name):
        alias = f"{e.name}T"
        values = list(e.members.values())
        literal_union = ", ".join(_py_literal(v) for v in values) if values else ""
        out.append(f"{alias}: TypeAlias = Literal[{literal_union}]\n\n")

        base = _enum_base_decl(e)
        inherited = _inherited_member_names(e)

        # Only emit new member attributes (avoid duplicating inherited ones).
        own_members = [(k, v) for (k, v) in e.members.items() if k not in inherited]

        out.append(f"class {e.name}({base}):\n")
        out.append(f"    T_ = Literal[{literal_union}]\n")
        if not own_members:
            out.append("    ...\n")
        else:
            for k, v in own_members:
                out.append(f"    {k}: Final[Literal[{_py_literal(v)}]] = {_py_literal(v)}\n")

        out.append(f"    values: ClassVar[Iterable[{alias}]]\n")
        out.append(f"    mapping: ClassVar[dict[str, {alias}]]\n\n")

        out.append("    @overload\n")
        out.append(f"    def __new__(cls, value: {alias}) -> {alias}: ...\n")
        out.append("    @overload\n")
        out.append(f"    def __new__(cls, value: object) -> {alias}: ...\n\n")

        out.append("    @classmethod\n")
        out.append(f"    def is_member(cls, value: object) -> TypeGuard[{alias}]: ...\n\n")

    return "".join(out)


def _render_overlay_stub_module(enums: list[EnumInfo]) -> str:
    """
    Overlay stub intended for pyright stubPath:
    only contains the enum stubs (module is "typing overlay").
    """
    out: list[str] = []
    out.append("from __future__ import annotations\n")
    out.append("from typing import ClassVar, Final, Literal, Iterable, TypeGuard, TypeAlias, overload\n")
    out.append("from literalenum import LiteralEnum\n\n")
    out.append(_render_enum_blocks(enums))
    return "".join(out)


# ----------------------------
# Adjacent stubs (preserve module)
# ----------------------------

_TYPING_INJECT = "from typing import ClassVar, Final, Literal, Iterable, TypeGuard, TypeAlias, overload"
_LITERALENUM_INJECT = "from literalenum import LiteralEnum"
_FUTURE = "from __future__ import annotations"


def _read_source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _collect_docstring(tree: ast.Module, src: str) -> str | None:
    if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant):
        if isinstance(tree.body[0].value.value, str):
            seg = ast.get_source_segment(src, tree.body[0])
            return seg.strip() if seg else None
    return None


def _collect_import_lines(tree: ast.Module, src: str) -> list[str]:
    lines: list[str] = []
    for stmt in tree.body:
        if isinstance(stmt, (ast.Import, ast.ImportFrom)):
            seg = ast.get_source_segment(src, stmt)
            if seg:
                lines.append(seg.strip())
    return lines


def _normalize_imports(import_lines: list[str]) -> list[str]:
    """
    Remove imports we will inject exactly once to avoid dupes.
    """
    out: list[str] = []
    for line in import_lines:
        s = line.strip()
        if s == _FUTURE:
            continue
        if s.startswith("from literalenum import") and "LiteralEnum" in s:
            continue
        if s.startswith("from typing import"):
            # drop any typing line that imports our injected symbols
            # (simple heuristic: if it mentions any of them, drop it)
            symbols = ["ClassVar", "Final", "Literal", "Iterable", "TypeGuard", "overload"]
            if any(sym in s for sym in symbols):
                continue
        out.append(s)
    return out


def _is_enum_classdef(stmt: ast.stmt, enum_names: set[str]) -> bool:
    return isinstance(stmt, ast.ClassDef) and stmt.name in enum_names


def _is_safe_preserve_stmt(stmt: ast.stmt) -> bool:
    """
    Preserve harmless top-level statements verbatim.
    - imports handled separately
    - docstring handled separately
    """
    return isinstance(stmt, (ast.Assign, ast.AnnAssign))


def _stub_skeleton(stmt: ast.stmt, src: str) -> str | None:
    # Keep names for everything else, but as stubs.
    if isinstance(stmt, ast.FunctionDef):
        header = (ast.get_source_segment(src, stmt) or f"def {stmt.name}(...):").splitlines()[0]
        if not header.rstrip().endswith(":"):
            header = header.rstrip() + ":"
        return header + "\n    ...\n"
    if isinstance(stmt, ast.AsyncFunctionDef):
        header = (ast.get_source_segment(src, stmt) or f"async def {stmt.name}(...):").splitlines()[0]
        if not header.rstrip().endswith(":"):
            header = header.rstrip() + ":"
        return header + "\n    ...\n"
    if isinstance(stmt, ast.ClassDef):
        # Non-enum class: preserve header with bases, stub body
        bases = ""
        if stmt.bases:
            bases_src = ", ".join(ast.get_source_segment(src, b) or "object" for b in stmt.bases)
            bases = f"({bases_src})"
        return f"class {stmt.name}{bases}:\n    ...\n"
    return None


def _render_adjacent_preserving_stub(module: str, enums: list[EnumInfo]) -> str:
    origin = _module_origin_py(module)
    if origin is None:
        return _render_overlay_stub_module(enums)

    src = _read_source(origin)
    tree = ast.parse(src, filename=str(origin))

    enum_names = {e.name for e in enums}

    doc = _collect_docstring(tree, src)
    imports = _normalize_imports(_collect_import_lines(tree, src))

    out: list[str] = []
    out.append(_FUTURE + "\n")
    if doc:
        out.append(doc + "\n\n")

    # Original imports (minus ones we inject)
    if imports:
        out.extend(line + "\n" for line in imports)
        out.append("\n")

    # Inject what enum blocks need, exactly once
    out.append(_TYPING_INJECT + "\n")
    out.append(_LITERALENUM_INJECT + "\n\n")

    # Walk original statements in order:
    for stmt in tree.body:
        # skip docstring/imports (already handled)
        if stmt is tree.body[0] and doc:
            continue
        if isinstance(stmt, (ast.Import, ast.ImportFrom)):
            continue

        # Replace enum classdefs with generated blocks later; skip here.
        if _is_enum_classdef(stmt, enum_names):
            continue

        # Preserve simple assignments verbatim
        if _is_safe_preserve_stmt(stmt):
            seg = ast.get_source_segment(src, stmt)
            if seg:
                out.append(seg.strip() + "\n\n")
            continue

        # For everything else, emit skeleton stubs so names remain
        sk = _stub_skeleton(stmt, src)
        if sk:
            out.append(sk + "\n")
            continue

        # Drop other statements (loops, runtime code, etc.)—not valid/meaningful in stubs.

    # Now append enum stubs (aliases + class stubs)
    out.append(_render_enum_blocks(enums))

    return "".join(out)


# ----------------------------
# CLI
# ----------------------------

def _parse_out_args(raw: list[str] | None) -> list[Path]:
    """
    Supports:
      --out typings
      --out typings --out stubs
      --out "typings,stubs"
      --out "typings;stubs"
    """
    if not raw:
        return [Path("typings")]
    out: list[Path] = []
    for item in raw:
        parts = [p.strip() for p in item.replace(";", ",").split(",") if p.strip()]
        out.extend(Path(p) for p in parts)

    # de-dupe while preserving order
    seen: set[Path] = set()
    uniq: list[Path] = []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def main(adjacent: bool = False) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="Root import (package or module) to scan, e.g. myapp")
    ap.add_argument(
        "--out",
        action="append",
        help="Overlay stub output directory (repeatable, or comma/semicolon-separated). Default: typings",
    )
    ap.add_argument(
        "--adjacent",
        action="store_true",
        help="Also write module.pyi next to module.py, preserving the rest of the module (useful for PyCharm).",
    )
    args = ap.parse_args()

    out_roots = _parse_out_args(args.out)
    infos = _find_literal_enums(args.root)

    by_module: dict[str, list[EnumInfo]] = {}
    for e in infos:
        by_module.setdefault(e.module, []).append(e)

    written = 0
    for module, enums in by_module.items():
        overlay_text = _render_overlay_stub_module(enums)
        adjacent_text = _render_adjacent_preserving_stub(module, enums)

        # Overlay stubs for pyright stubPath
        for stub_root in out_roots:
            out_path = _module_to_stub_path(stub_root, module)
            _ensure_parent(out_path)
            out_path.write_text(overlay_text, encoding="utf-8")
            written += 1

        # Adjacent stubs for PyCharm
        if adjacent or args.adjacent:
            adj_path = _module_to_adjacent_stub_path(module)
            if adj_path is not None:
                _ensure_parent(adj_path)
                adj_path.write_text(adjacent_text, encoding="utf-8")
                written += 1

    print(f"Wrote {written} stub file(s) for {len(infos)} LiteralEnum subclasses.")
    return 0


def maina() -> int:
    return main(adjacent=True)


if __name__ == "__main__":
    raise SystemExit(main())
