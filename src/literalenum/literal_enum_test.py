"""Verify native Pydantic support for namespaced scalar annotations."""

from typing import Literal, assert_type

import pytest
from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from literalenum import LiteralEnum


class Method(LiteralEnum):
    """Exercise aliases without duplicating accepted values in a schema."""

    GET = "GET"
    POST = "POST"
    GET_ALIAS = "GET"


class Message(BaseModel):
    """Use a LiteralEnum directly in a validated public field."""

    model_config = ConfigDict(validate_assignment=True)
    method: Method


@pytest.mark.parametrize("method", [Method.GET, Method.POST])
def test_native_pydantic_round_trip(method: Method) -> None:
    """Plain strings round-trip and expose an exhaustive JSON schema."""
    message = Message(method=method)
    assert_type(message.method, Method)
    if message.method == "GET":
        assert_type(message.method, Literal["GET"])
    assert isinstance(message.method, str)
    assert Message.model_validate_json(message.model_dump_json()) == message
    schema = Message.model_json_schema()["properties"]["method"]
    assert schema["enum"] == ["GET", "POST"]
    assert schema["type"] == "string"


@pytest.mark.parametrize("invalid", ["DELETE", " GET ", b"GET", True, 1, None, [], {}])
def test_native_pydantic_rejects_invalid_values(invalid: object) -> None:
    """Unknown/coercible inputs and assignments cannot bypass membership validation."""
    with pytest.raises(ValidationError):
        Message.model_validate({"method": invalid})
    message = Message(method=Method.GET)
    with pytest.raises(ValidationError):
        message.method = invalid  # type: ignore[assignment]  # Deliberately untyped input.
    assert message.method == Method.GET


def test_native_pydantic_type_adapter() -> None:
    """Direct TypeAdapter use requires neither a model factory nor annotation metadata."""
    adapter: TypeAdapter[Method] = TypeAdapter(Method)
    assert adapter.validate_python("GET") == "GET"
    assert adapter.validate_json(b'"POST"') == "POST"
    assert adapter.dump_json(Method.GET) == b'"GET"'


def test_native_pydantic_preserves_scalar_identity() -> None:
    """Integer literals distinguish booleans while nullable literals retain None."""

    class Code(LiteralEnum):
        """Integer values must not accidentally accept Python boolean equality."""

        OK = 1
        MISSING = 404

    adapter: TypeAdapter[Code] = TypeAdapter(Code)
    assert adapter.validate_python(1) == 1
    for invalid in (True, 1.0, "1"):
        with pytest.raises(ValidationError):
            adapter.validate_python(invalid)

    class MaybeMethod(LiteralEnum):
        """Nullable scalar namespaces remain usable in Pydantic."""

        GET = "GET"
        UNSET = None

    nullable_adapter: TypeAdapter[MaybeMethod] = TypeAdapter(MaybeMethod)
    assert nullable_adapter.validate_json(b"null") is None


def test_native_pydantic_preserves_mixed_scalar_types() -> None:
    """Python's equal boolean and integer values stay distinct through validation."""

    class FlagOrCount(LiteralEnum):
        """Include equal values with distinct scalar types."""

        ENABLED = True
        ONE = 1

    adapter: TypeAdapter[FlagOrCount] = TypeAdapter(FlagOrCount)
    assert adapter.validate_python(True) is True
    assert adapter.dump_json(adapter.validate_python(1)) == b"1"
    assert adapter.validate_json(b"true") is True
    assert adapter.dump_json(adapter.validate_json(b"1")) == b"1"


def test_native_pydantic_extended_namespace() -> None:
    """Inherited and newly added values share the same native Pydantic contract."""

    class ExtendedMethod(Method, extend=True):
        """Add a third verb to the existing namespace."""

        DELETE = "DELETE"

    adapter: TypeAdapter[ExtendedMethod] = TypeAdapter(ExtendedMethod)
    assert adapter.validate_python("GET") == "GET"
    assert adapter.validate_python("DELETE") == "DELETE"
    assert adapter.json_schema()["enum"] == ["GET", "POST", "DELETE"]
