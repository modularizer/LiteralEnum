from __future__ import annotations

from typing import Any, Dict, List

JsonSchema = Dict[str, Any]


def literal_enum_schema(
    enum_cls: type,
    *,
    title: str | None = None,
    description: str | None = None,
    nullable: bool | None = None,
    openapi: bool = False,
) -> JsonSchema:
    """
    Build a JSON Schema (and OpenAPI-friendly) schema for a LiteralEnumMeta class.

    Expects `enum_cls` to have:
      - _ordered_values_: list/tuple of literal values in order
      - _members_: dict[str, value]

    Supports literals: str, int, bool, None, bytes.
    For mixed types, emits a union schema (oneOf / anyOf).

    Params:
      - nullable:
          * None (default): inferred from presence of None in values
          * True/False: force nullable behavior
      - openapi:
          * If True: emits OpenAPI 3.0-friendly shape (uses nullable: true)
          * If False: emits JSON Schema 2020-12-friendly shape (uses type: "null" or oneOf)
    """
    values: List[Any] = list(getattr(enum_cls, "_ordered_values_", ()))
    if not values:
        raise ValueError(f"{enum_cls!r} has no _ordered_values_")

    # JSON Schema can't represent bytes directly; common convention is base64 string.
    def _json_type(v: Any) -> str:
        if v is None:
            return "null"
        if isinstance(v, bool):
            return "boolean"
        if isinstance(v, int) and not isinstance(v, bool):
            return "integer"
        if isinstance(v, str):
            return "string"
        if isinstance(v, (bytes, bytearray, memoryview)):
            return "string"
        # float literal support not listed in your metaclass, but easy to add if you want:
        if isinstance(v, float):
            return "number"
        raise TypeError(f"Unsupported LiteralEnum value {v!r} (type {type(v).__name__})")

    # Normalize bytes -> base64-ish string representation? (You can swap this.)
    def _normalize(v: Any) -> Any:
        if isinstance(v, (bytes, bytearray, memoryview)):
            # JSON can't carry bytes. Convention: base64 string.
            # If you prefer "binary" format in OpenAPI, keep as string and add format.
            return bytes(v).decode("base64", errors="strict")
        return v

    normalized_values = [_normalize(v) for v in values]
    types = [_json_type(v) for v in values]
    unique_types = sorted(set(types))

    has_null = "null" in unique_types
    inferred_nullable = has_null
    if nullable is None:
        nullable = inferred_nullable

    # Remove nulls from enum list if we represent null via nullable/type: null separately.
    enum_no_null = [v for v, t in zip(normalized_values, types) if t != "null"]

    schema: JsonSchema = {}
    schema["title"] = title or getattr(enum_cls, "__name__", "LiteralEnum")
    if description:
        schema["description"] = description

    # If only one non-null type, simplest representation.
    non_null_types = [t for t in unique_types if t != "null"]

    def _apply_nullable_oas(s: JsonSchema) -> JsonSchema:
        if nullable:
            s["nullable"] = True
        return s

    # Helper: JSON Schema style nullability (2020-12-ish)
    def _apply_nullable_jsonschema(s: JsonSchema) -> JsonSchema:
        if not nullable:
            return s
        # If already unioned, add {"type": "null"} via oneOf
        if "oneOf" in s:
            s["oneOf"].append({"type": "null"})
            return s
        # If type is a single string, allow null via type array
        t = s.get("type")
        if isinstance(t, str):
            s["type"] = [t, "null"]
        elif isinstance(t, list) and "null" not in t:
            t.append("null")
        else:
            # Fallback: union with null
            s = {"oneOf": [s, {"type": "null"}], **{k: v for k, v in s.items() if k not in ("type", "enum")}}
        return s

    # Build
    if len(non_null_types) == 1:
        t = non_null_types[0]
        schema["type"] = t
        if enum_no_null:
            schema["enum"] = enum_no_null

        # bytes convention: if any bytes present, add format hint
        if any(isinstance(v, (bytes, bytearray, memoryview)) for v in values):
            schema.setdefault("format", "byte")  # OpenAPI convention for base64

        if openapi:
            schema = _apply_nullable_oas(schema)
        else:
            schema = _apply_nullable_jsonschema(schema)

        return schema

    # Mixed types: use union
    # In OpenAPI 3.0, "oneOf" is supported; "anyOf" also works but oneOf is clearer.
    alts: List[JsonSchema] = []
    for t in sorted(set(non_null_types)):
        vals_for_t = [v for v, tt in zip(normalized_values, types) if tt == t]
        alt: JsonSchema = {"type": t, "enum": vals_for_t}
        if t == "string" and any(isinstance(v, (bytes, bytearray, memoryview)) for v in values):
            # Only add if those strings are actually from bytes;
            # leaving this hint in case you mix bytes + str.
            alt.setdefault("format", "byte")
        alts.append(alt)

    schema["oneOf"] = alts

    if openapi:
        schema = _apply_nullable_oas(schema)
    else:
        schema = _apply_nullable_jsonschema(schema)

    return schema
