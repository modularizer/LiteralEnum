from __future__ import annotations

import argparse
import importlib
import inspect
import pkgutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from literalenum import LiteralEnum  # your runtime base


def _iter_modules(package: str) -> Iterable[str]:
    """Yield module names under a package (including the package itself)."""
    pkg = importlib.import_module(package)
    if not hasattr(pkg, "__path__"):
        # It's a single module, not a package
        yield package
        return

    yield package
    for modinfo in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
        yield modinfo.name


def _py_literal(value: Any) -> str:
    # repr(...) is usually fine for Literal, including bytes and strings.
    # If you later support exotic values, you'll need to constrain.
    return repr(value)


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class EnumInfo:
    qualname: str
    module: str
    name: str
    members: dict[str, Any]


def _find_literal_enums(root_module_or_package: str) -> list[EnumInfo]:
    infos: list[EnumInfo] = []
    for modname in _iter_modules(root_module_or_package):
        try:
            mod = importlib.import_module(modname)
        except Exception:
            # Skip modules that can’t import (optional: add --fail-fast)
            continue

        for _, obj in inspect.getmembers(mod, inspect.isclass):
            if obj is LiteralEnum:
                continue
            if issubclass(obj, LiteralEnum) and obj.__module__ == mod.__name__:
                # Your runtime provides `mapping: dict[str, value]`
                members = dict(getattr(obj, "mapping"))
                infos.append(
                    EnumInfo(
                        qualname=f"{obj.__module__}.{obj.__name__}",
                        module=obj.__module__,
                        name=obj.__name__,
                        members=members,
                    )
                )
    return infos


def _render_enum_stub(info: EnumInfo) -> str:
    # Determine Literal union
    values = list(info.members.values())
    literal_union = ", ".join(_py_literal(v) for v in values) if values else ""

    alias = f"{info.name}T"
    # Choose a loose fallback constructor param type for overload 2
    # (You can get fancier by inferring a common supertype.)
    ctor_fallback = "object"

    member_lines = "\n".join(f"    {k}: Final[{alias}]" for k in info.members.keys())
    return f"""\
from __future__ import annotations

from typing import Final, Literal, Mapping, Sequence, TypeGuard, overload
from literalenum import LiteralEnum

{alias} = Literal[{literal_union}]

class {info.name}(LiteralEnum[{alias}]):
{member_lines if member_lines else "    ..."}
    values: Sequence[{alias}]
    mapping: Mapping[str, {alias}]

    @overload
    def __new__(cls, value: {alias}) -> {alias}: ...
    @overload
    def __new__(cls, value: {ctor_fallback}) -> {alias}: ...

    @classmethod
    def is_member(cls, value: object) -> TypeGuard[{alias}]: ...
"""


def _module_to_stub_path(stub_root: Path, module: str) -> Path:
    rel = Path(*module.split("."))
    return stub_root / (str(rel) + ".pyi")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="Root import (package or module) to scan, e.g. myapp")
    ap.add_argument("--out", default="typings", help="Stub output directory (stubPath)")
    args = ap.parse_args()

    stub_root = Path(args.out)
    infos = _find_literal_enums(args.root)

    for info in infos:
        out_path = _module_to_stub_path(stub_root, info.module)
        _ensure_parent(out_path)

        text = _render_enum_stub(info)
        out_path.write_text(text, encoding="utf-8")

    print(f"Wrote stubs for {len(infos)} LiteralEnum subclasses into: {stub_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
