"""Tests for the ``literalenum`` package (extended metaclass + compatibility extensions).

These tests cover the ``literalenum.LiteralEnum`` and ``literalenum.LiteralEnumMeta``
subclasses that add compatibility conversion methods on top of the core
``typing_literalenum`` implementation.

Run with: pytest tests/test_literalenum.py
"""
from __future__ import annotations

import enum
import re
from typing import Literal, get_args

import pytest

from literalenum import LiteralEnum, LiteralEnumMeta
import typing_literalenum as core


# ===================================================================
# Fixtures — reusable enum definitions (via the *package* metaclass)
# ===================================================================

class HttpMethod(LiteralEnum):
    GET = "GET"
    POST = "POST"
    DELETE = "DELETE"


class StatusCode(LiteralEnum):
    OK = 200
    NOT_FOUND = 404


class Feature(LiteralEnum):
    ENABLED = True
    DISABLED = False


class Mixed(LiteralEnum):
    S = "hello"
    I = 42
    B = True


class WithAliases(LiteralEnum):
    GET = "GET"
    get = "GET"
    POST = "POST"
    post = "POST"


class Empty(LiteralEnum):
    pass


# ===================================================================
# Metaclass identity — package subclass of core
# ===================================================================

class TestMetaclassIdentity:
    def test_package_metaclass_is_subclass_of_core(self):
        assert issubclass(LiteralEnumMeta, core.LiteralEnumMeta)

    def test_package_metaclass_is_not_core(self):
        assert LiteralEnumMeta is not core.LiteralEnumMeta

    def test_enum_uses_package_metaclass(self):
        assert type(HttpMethod) is LiteralEnumMeta

    def test_isinstance_of_core(self):
        assert isinstance(HttpMethod, core.LiteralEnumMeta)

    def test_core_behavior_preserved(self):
        """Core container protocol works through the package metaclass."""
        assert list(HttpMethod) == ["GET", "POST", "DELETE"]
        assert "GET" in HttpMethod
        assert len(HttpMethod) == 3
        assert HttpMethod["GET"] == "GET"


# ===================================================================
# .literal() and T_ property
# ===================================================================

class TestLiteral:
    def test_literal_returns_literal_type(self):
        lit = HttpMethod.literal()
        args = get_args(lit)
        assert set(args) == {"GET", "POST", "DELETE"}

    def test_literal_int_values(self):
        lit = StatusCode.literal()
        args = get_args(lit)
        assert set(args) == {200, 404}

    def test_t_property_same_as_literal(self):
        assert HttpMethod.T_ == HttpMethod.literal()


# ===================================================================
# .enum()
# ===================================================================

class TestEnum:
    def test_enum_returns_stdlib_enum(self):
        e = HttpMethod.enum()
        assert issubclass(e, enum.Enum)

    def test_enum_has_correct_members(self):
        e = HttpMethod.enum()
        assert e["GET"].value == "GET"
        assert e["POST"].value == "POST"
        assert e["DELETE"].value == "DELETE"

    def test_enum_name(self):
        e = HttpMethod.enum()
        assert e.__name__ == "HttpMethod"


# ===================================================================
# .str_enum()
# ===================================================================

class TestStrEnum:
    def test_str_enum_returns_strenum(self):
        e = HttpMethod.str_enum()
        assert issubclass(e, enum.StrEnum)

    def test_str_enum_members(self):
        e = HttpMethod.str_enum()
        assert e["GET"].value == "GET"
        assert str(e["GET"]) == "GET"

    def test_str_enum_rejects_non_string(self):
        with pytest.raises(TypeError, match="string-valued"):
            StatusCode.str_enum()


# ===================================================================
# .int_enum()
# ===================================================================

class TestIntEnum:
    def test_int_enum_returns_intenum(self):
        e = StatusCode.int_enum()
        assert issubclass(e, enum.IntEnum)

    def test_int_enum_members(self):
        e = StatusCode.int_enum()
        assert e["OK"].value == 200
        assert int(e["NOT_FOUND"]) == 404

    def test_int_enum_rejects_non_int(self):
        with pytest.raises(TypeError, match="int-valued"):
            HttpMethod.int_enum()


# ===================================================================
# .json_schema()
# ===================================================================

class TestJsonSchema:
    def test_string_enum_schema(self):
        schema = HttpMethod.json_schema()
        assert schema["type"] == "string"
        assert set(schema["enum"]) == {"GET", "POST", "DELETE"}
        assert schema["title"] == "HttpMethod"

    def test_int_enum_schema(self):
        schema = StatusCode.json_schema()
        assert schema["type"] == "integer"
        assert set(schema["enum"]) == {200, 404}

    def test_custom_title_and_description(self):
        """The compatibility extension accepts kwargs when called directly."""
        from literalenum.compatibility_extensions import json_schema
        schema = json_schema(HttpMethod, title="Method", description="HTTP verb")
        assert schema["title"] == "Method"
        assert schema["description"] == "HTTP verb"

    def test_mixed_types_uses_oneof(self):
        schema = Mixed.json_schema()
        assert "oneOf" in schema

    def test_empty_enum_raises(self):
        with pytest.raises(ValueError):
            Empty.json_schema()


# ===================================================================
# .regex_str() / .regex_pattern()
# ===================================================================

class TestRegex:
    def test_regex_str_format(self):
        pattern = HttpMethod.regex_str()
        assert pattern.startswith("^(?:")
        assert pattern.endswith(")$")
        assert "GET" in pattern
        assert "POST" in pattern
        assert "DELETE" in pattern

    def test_regex_str_matches_valid(self):
        pattern = HttpMethod.regex_str()
        assert re.match(pattern, "GET")
        assert re.match(pattern, "POST")

    def test_regex_str_rejects_invalid(self):
        pattern = HttpMethod.regex_str()
        assert not re.match(pattern, "PATCH")
        assert not re.match(pattern, "get")

    def test_regex_pattern_returns_compiled(self):
        pat = HttpMethod.regex_pattern()
        assert isinstance(pat, re.Pattern)

    def test_regex_pattern_matches(self):
        pat = HttpMethod.regex_pattern()
        assert pat.match("GET")
        assert not pat.match("PATCH")

    def test_regex_pattern_flags(self):
        pat = HttpMethod.regex_pattern(flags=re.IGNORECASE)
        assert pat.match("get")
        assert pat.match("GET")

    def test_regex_rejects_non_string(self):
        with pytest.raises(TypeError, match="string-valued"):
            StatusCode.regex_str()


# ===================================================================
# Collection converters: .set(), .list(), .frozenset(), .dict(), .tuple()
# ===================================================================

class TestCollectionConverters:
    def test_set(self):
        result = HttpMethod.set()
        assert isinstance(result, set)
        assert result == {"GET", "POST", "DELETE"}

    def test_list(self):
        result = HttpMethod.list()
        assert isinstance(result, list)
        assert result == ["GET", "POST", "DELETE"]

    def test_frozenset(self):
        result = HttpMethod.frozenset()
        assert isinstance(result, frozenset)
        assert result == frozenset({"GET", "POST", "DELETE"})

    def test_dict(self):
        result = HttpMethod.dict()
        assert isinstance(result, dict)
        assert result == {"GET": "GET", "POST": "POST", "DELETE": "DELETE"}

    def test_dict_with_aliases(self):
        result = WithAliases.dict()
        assert result == {"GET": "GET", "get": "GET", "POST": "POST", "post": "POST"}

    def test_tuple(self):
        result = HttpMethod.tuple()
        assert isinstance(result, tuple)
        assert result == ("GET", "POST", "DELETE")


# ===================================================================
# .str()
# ===================================================================

class TestStr:
    def test_str_string_values(self):
        result = HttpMethod.str()
        assert result == '"GET"|"POST"|"DELETE"'

    def test_str_int_values(self):
        result = StatusCode.str()
        assert result == "200|404"

    def test_str_bool_values(self):
        result = Feature.str()
        assert result == "True|False"


# ===================================================================
# .stub()
# ===================================================================

class TestStub:
    def test_stub_returns_string(self):
        result = HttpMethod.stub()
        assert isinstance(result, str)

    def test_stub_contains_class_name(self):
        result = HttpMethod.stub()
        assert "HttpMethod" in result

    def test_stub_contains_literal_alias(self):
        result = HttpMethod.stub()
        assert "HttpMethodT" in result

    def test_stub_contains_members(self):
        result = HttpMethod.stub()
        assert "GET" in result
        assert "POST" in result
        assert "DELETE" in result


# ===================================================================
# Inheritance / extend through package metaclass
# ===================================================================

class TestPackageInheritance:
    def test_extend_works(self):
        class Extended(HttpMethod, extend=True):
            PATCH = "PATCH"

        assert "GET" in Extended
        assert "PATCH" in Extended
        assert list(Extended) == ["GET", "POST", "DELETE", "PATCH"]

    def test_extend_preserves_metaclass(self):
        class Extended(HttpMethod, extend=True):
            PATCH = "PATCH"

        assert type(Extended) is LiteralEnumMeta

    def test_call_to_validate_through_package(self):
        class Callable(LiteralEnum, call_to_validate=True):
            X = "x"
            Y = "y"

        assert Callable("x") == "x"
        with pytest.raises(ValueError):
            Callable("z")

    def test_default_not_callable(self):
        with pytest.raises(TypeError, match="not instantiable"):
            HttpMethod("GET")

    def test_allow_aliases_false(self):
        with pytest.raises(TypeError, match="Duplicate value"):
            class Strict(LiteralEnum, allow_aliases=False):
                A = "x"
                B = "x"


# ===================================================================
# .django_choices()
# ===================================================================

class TestDjangoChoices:
    def test_returns_list_of_tuples(self):
        result = HttpMethod.django_choices()
        assert isinstance(result, list)
        assert all(isinstance(item, tuple) and len(item) == 2 for item in result)

    def test_format_is_value_name(self):
        result = HttpMethod.django_choices()
        assert result == [("GET", "GET"), ("POST", "POST"), ("DELETE", "DELETE")]

    def test_int_values(self):
        result = StatusCode.django_choices()
        assert result == [(200, "OK"), (404, "NOT_FOUND")]

    def test_excludes_aliases(self):
        result = WithAliases.django_choices()
        assert result == [("GET", "GET"), ("POST", "POST")]

    def test_empty(self):
        result = Empty.django_choices()
        assert result == []


# ===================================================================
# .click_choice()
# ===================================================================

class TestClickChoice:
    def test_returns_click_choice(self):
        click = pytest.importorskip("click")
        result = HttpMethod.click_choice()
        assert isinstance(result, click.Choice)

    def test_contains_values(self):
        pytest.importorskip("click")
        result = HttpMethod.click_choice()
        assert list(result.choices) == ["GET", "POST", "DELETE"]


# ===================================================================
# .random_choice()
# ===================================================================

class TestRandomChoice:
    def test_returns_valid_member(self):
        result = HttpMethod.random_choice()
        assert result in HttpMethod

    def test_returns_from_values(self):
        results = {HttpMethod.random_choice() for _ in range(200)}
        assert results <= {"GET", "POST", "DELETE"}

    def test_int_enum(self):
        result = StatusCode.random_choice()
        assert result in StatusCode


# ===================================================================
# .bare_class()
# ===================================================================

class TestBareClass:
    def test_returns_plain_class(self):
        cls = HttpMethod.bare_class()
        assert type(cls) is type  # plain type, not LiteralEnumMeta

    def test_has_member_attributes(self):
        cls = HttpMethod.bare_class()
        assert cls.GET == "GET"
        assert cls.POST == "POST"
        assert cls.DELETE == "DELETE"

    def test_preserves_name(self):
        cls = HttpMethod.bare_class()
        assert cls.__name__ == "HttpMethod"

    def test_not_iterable(self):
        cls = HttpMethod.bare_class()
        with pytest.raises(TypeError):
            list(cls)


# ===================================================================
# Optional-dependency integrations (import-gated)
# ===================================================================

class TestOptionalIntegrations:
    def test_strawberry_enum(self):
        pytest.importorskip("strawberry")
        result = HttpMethod.strawberry_enum()
        assert result is not None

    def test_graphene_enum(self):
        pytest.importorskip("graphene")
        result = HttpMethod.graphene_enum()
        assert result is not None

    def test_sqlalchemy_enum(self):
        pytest.importorskip("sqlalchemy")
        result = HttpMethod.sqlalchemy_enum()
        assert result is not None

    def test_base_model(self):
        pytest.importorskip("pydantic")
        result = HttpMethod.base_model()
        assert result is not None
