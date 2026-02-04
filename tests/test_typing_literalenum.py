"""Runtime tests for LiteralEnum.

Run with: pytest tests/test_literalenum.py
"""
from __future__ import annotations

import pytest
from types import MappingProxyType
from typing_literalenum import LiteralEnum, LiteralEnumMeta, is_member, validate_is_member


# ===================================================================
# Fixtures — reusable enum definitions
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


class ByteTag(LiteralEnum):
    HEADER = b"\x00"
    FOOTER = b"\xff"


class Nullable(LiteralEnum):
    NOTHING = None
    SOMETHING = "yes"


class Empty(LiteralEnum):
    pass


class WithAliases(LiteralEnum):
    GET = "GET"
    get = "GET"
    POST = "POST"
    post = "POST"


# ===================================================================
# Basic member collection
# ===================================================================

class TestMemberCollection:
    def test_str_members(self):
        assert HttpMethod.GET == "GET"
        assert HttpMethod.POST == "POST"
        assert HttpMethod.DELETE == "DELETE"

    def test_int_members(self):
        assert StatusCode.OK == 200
        assert StatusCode.NOT_FOUND == 404

    def test_bool_members(self):
        assert Feature.ENABLED is True
        assert Feature.DISABLED is False

    def test_bytes_members(self):
        assert ByteTag.HEADER == b"\x00"
        assert ByteTag.FOOTER == b"\xff"

    def test_none_member(self):
        assert Nullable.NOTHING is None
        assert Nullable.SOMETHING == "yes"

    def test_empty_enum(self):
        assert list(Empty) == []
        assert len(Empty) == 0

    def test_values_are_plain_literals(self):
        """Members are plain scalars, not wrapper objects."""
        assert type(HttpMethod.GET) is str
        assert type(StatusCode.OK) is int
        assert type(Feature.ENABLED) is bool

    def test_private_names_excluded(self):
        class WithPrivate(LiteralEnum):
            _hidden = "secret"
            PUBLIC = "visible"

        assert list(WithPrivate) == ["visible"]
        assert not hasattr(WithPrivate.mapping, "_hidden") or "_hidden" not in WithPrivate.mapping

    def test_descriptors_excluded(self):
        class WithMethod(LiteralEnum):
            A = "a"

            def helper(self):
                pass

            @staticmethod
            def static_helper():
                pass

        assert list(WithMethod) == ["a"]

    def test_non_literal_value_rejected(self):
        with pytest.raises(TypeError, match="not a supported Literal value"):
            class Bad(LiteralEnum):
                X = [1, 2, 3]

    def test_non_literal_dict_rejected(self):
        with pytest.raises(TypeError, match="not a supported Literal value"):
            class Bad(LiteralEnum):
                X = {"a": 1}


# ===================================================================
# Container protocol
# ===================================================================

class TestContainerProtocol:
    def test_iter(self):
        assert list(HttpMethod) == ["GET", "POST", "DELETE"]

    def test_iter_order_preserved(self):
        class Ordered(LiteralEnum):
            C = "c"
            A = "a"
            B = "b"

        assert list(Ordered) == ["c", "a", "b"]

    def test_reversed(self):
        assert list(reversed(HttpMethod)) == ["DELETE", "POST", "GET"]

    def test_len(self):
        assert len(HttpMethod) == 3
        assert len(StatusCode) == 2
        assert len(Empty) == 0

    def test_bool_truthy(self):
        assert bool(HttpMethod) is True

    def test_bool_falsy(self):
        assert bool(Empty) is False

    def test_contains_valid(self):
        assert "GET" in HttpMethod
        assert "POST" in HttpMethod
        assert 200 in StatusCode
        assert True in Feature
        assert None in Nullable

    def test_contains_invalid(self):
        assert "git" not in HttpMethod
        assert 999 not in StatusCode
        assert 42 not in Feature

    def test_contains_unhashable_returns_false(self):
        assert [1, 2] not in HttpMethod

    def test_getitem(self):
        assert HttpMethod["GET"] == "GET"
        assert StatusCode["OK"] == 200

    def test_getitem_missing(self):
        with pytest.raises(KeyError, match="not a member"):
            HttpMethod["PATCH"]

    def test_repr_with_members(self):
        r = repr(HttpMethod)
        assert "LiteralEnum" in r
        assert "HttpMethod" in r
        assert "GET='GET'" in r

    def test_repr_empty(self):
        r = repr(Empty)
        assert "LiteralEnum" in r
        assert "Empty" in r


# ===================================================================
# Strict key — bool/int distinction
# ===================================================================

class TestStrictKey:
    def test_bool_int_distinct(self):
        class Mixed(LiteralEnum):
            YES = True
            ONE = 1

        assert True in Mixed
        assert 1 in Mixed
        assert len(Mixed) == 2
        assert list(Mixed) == [True, 1]

    def test_false_zero_distinct(self):
        class Mixed(LiteralEnum):
            NO = False
            ZERO = 0

        assert False in Mixed
        assert 0 in Mixed
        assert len(Mixed) == 2


# ===================================================================
# Mapping properties
# ===================================================================

class TestMappings:
    def test_mapping_returns_mappingproxy(self):
        assert isinstance(HttpMethod.mapping, MappingProxyType)

    def test_mapping_includes_all_names(self):
        assert dict(WithAliases.mapping) == {
            "GET": "GET", "get": "GET",
            "POST": "POST", "post": "POST",
        }

    def test_unique_mapping_excludes_aliases(self):
        assert dict(WithAliases.unique_mapping) == {"GET": "GET", "POST": "POST"}

    def test_unique_mapping_equals_mapping_when_no_aliases(self):
        assert dict(HttpMethod.unique_mapping) == dict(HttpMethod.mapping)

    def test_keys(self):
        assert HttpMethod.keys() == ("GET", "POST", "DELETE")

    def test_keys_excludes_aliases(self):
        assert WithAliases.keys() == ("GET", "POST")

    def test_values(self):
        assert HttpMethod.values() == ("GET", "POST", "DELETE")

    def test_values_excludes_aliases(self):
        assert WithAliases.values() == ("GET", "POST")

    def test_items(self):
        assert HttpMethod.items() == (("GET", "GET"), ("POST", "POST"), ("DELETE", "DELETE"))

    def test_items_excludes_aliases(self):
        assert WithAliases.items() == (("GET", "GET"), ("POST", "POST"))

    def test_members_dunder(self):
        assert isinstance(HttpMethod.__members__, MappingProxyType)
        assert dict(HttpMethod.__members__) == dict(HttpMethod.mapping)


# ===================================================================
# Aliases
# ===================================================================

class TestAliases:
    def test_aliases_allowed_by_default(self):
        class A(LiteralEnum):
            X = "val"
            Y = "val"

        assert len(A) == 1
        assert list(A) == ["val"]

    def test_names_returns_all(self):
        assert WithAliases.names("GET") == ("GET", "get")
        assert WithAliases.names("POST") == ("POST", "post")

    def test_names_no_alias(self):
        assert HttpMethod.names("GET") == ("GET",)

    def test_canonical_name(self):
        assert WithAliases.canonical_name("GET") == "GET"
        assert WithAliases.canonical_name("POST") == "POST"

    def test_names_invalid_value(self):
        with pytest.raises(KeyError, match="not a member"):
            HttpMethod.names("PATCH")

    def test_canonical_name_invalid_value(self):
        with pytest.raises(KeyError, match="not a member"):
            HttpMethod.canonical_name("PATCH")

    def test_allow_aliases_false(self):
        with pytest.raises(TypeError, match="Duplicate value"):
            class Strict(LiteralEnum, allow_aliases=False):
                A = "x"
                B = "x"

    def test_allow_aliases_false_unique_ok(self):
        class Strict(LiteralEnum, allow_aliases=False):
            A = "a"
            B = "b"

        assert list(Strict) == ["a", "b"]

    def test_allow_aliases_inherited(self):
        class Base(LiteralEnum, allow_aliases=False):
            X = 1

        with pytest.raises(TypeError, match="Duplicate value"):
            class Child(Base, extend=True):
                Y = 1

    def test_allow_aliases_override(self):
        class Base(LiteralEnum, allow_aliases=False):
            X = 1

        class Child(Base, extend=True, allow_aliases=True):
            Y = 1

        assert list(Child) == [1]
        assert Child.names(1) == ("X", "Y")


# ===================================================================
# Validation
# ===================================================================

class TestValidation:
    def test_is_valid_true(self):
        assert HttpMethod.is_valid("GET") is True

    def test_is_valid_false(self):
        assert HttpMethod.is_valid("git") is False

    def test_validate_returns_value(self):
        result = HttpMethod.validate("GET")
        assert result == "GET"
        assert type(result) is str

    def test_validate_raises_on_invalid(self):
        with pytest.raises(ValueError, match="not a valid HttpMethod"):
            HttpMethod.validate("git")

    def test_is_member_function(self):
        assert is_member(HttpMethod, "GET") is True
        assert is_member(HttpMethod, "git") is False

    def test_validate_is_member_function(self):
        assert validate_is_member(HttpMethod, "POST") == "POST"
        with pytest.raises(ValueError):
            validate_is_member(HttpMethod, "git")


# ===================================================================
# call_to_validate
# ===================================================================

class TestCallToValidate:
    def test_default_not_callable(self):
        with pytest.raises(TypeError, match="not instantiable"):
            HttpMethod("GET")

    def test_call_to_validate_valid(self):
        class Callable(LiteralEnum, call_to_validate=True):
            GET = "GET"
            POST = "POST"

        assert Callable("GET") == "GET"
        assert type(Callable("GET")) is str

    def test_call_to_validate_invalid(self):
        class Callable(LiteralEnum, call_to_validate=True):
            GET = "GET"

        with pytest.raises(ValueError, match="not a valid Callable"):
            Callable("git")

    def test_call_to_validate_inherited(self):
        class Base(LiteralEnum, call_to_validate=True):
            X = 1

        class Child(Base, extend=True):
            Y = 2

        assert Child(1) == 1
        assert Child(2) == 2

    def test_call_to_validate_override_to_false(self):
        class Base(LiteralEnum, call_to_validate=True):
            X = 1

        class Child(Base, extend=True, call_to_validate=False):
            Y = 2

        with pytest.raises(TypeError, match="not instantiable"):
            Child(1)


# ===================================================================
# Inheritance and extend
# ===================================================================

class TestInheritance:
    def test_subclass_without_extend_raises(self):
        with pytest.raises(TypeError, match="extend=True"):
            class Sub(HttpMethod):
                PATCH = "PATCH"

    def test_extend_inherits_members(self):
        class Extended(HttpMethod, extend=True):
            PATCH = "PATCH"
            PUT = "PUT"

        assert "GET" in Extended
        assert "PATCH" in Extended
        assert list(Extended) == ["GET", "POST", "DELETE", "PATCH", "PUT"]

    def test_extend_name_conflict_raises(self):
        with pytest.raises(TypeError, match="conflicts with inherited"):
            class Bad(HttpMethod, extend=True):
                GET = "GET_V2"

    def test_extend_preserves_parent(self):
        """Extending does not mutate the parent."""
        class Extended(HttpMethod, extend=True):
            PATCH = "PATCH"

        assert "PATCH" not in HttpMethod
        assert list(HttpMethod) == ["GET", "POST", "DELETE"]

    def test_multiple_bases_raises(self):
        class A(LiteralEnum):
            X = 1

        class B(LiteralEnum):
            Y = 2

        with pytest.raises(TypeError, match="multiple LiteralEnum bases"):
            class C(A, B, extend=True):
                pass

    def test_extend_empty_parent(self):
        class Child(Empty, extend=True):
            A = "a"

        assert list(Child) == ["a"]

    def test_subclass_empty_parent_no_extend(self):
        """Subclassing an empty LiteralEnum doesn't require extend=True."""
        class Child(Empty):
            A = "a"

        assert list(Child) == ["a"]


# ===================================================================
# _ignore_
# ===================================================================

class TestIgnore:
    def test_ignore_string(self):
        class I(LiteralEnum):
            _ignore_ = "SKIP"
            A = "a"
            SKIP = "skip"

        assert list(I) == ["a"]
        assert "skip" not in I

    def test_ignore_list(self):
        class I(LiteralEnum):
            _ignore_ = ["SKIP1", "SKIP2"]
            A = "a"
            SKIP1 = "s1"
            SKIP2 = "s2"

        assert list(I) == ["a"]

    def test_ignore_comma_separated(self):
        class I(LiteralEnum):
            _ignore_ = "SKIP1, SKIP2"
            A = "a"
            SKIP1 = "s1"
            SKIP2 = "s2"

        assert list(I) == ["a"]

    def test_ignore_none(self):
        class I(LiteralEnum):
            _ignore_ = None
            A = "a"

        assert list(I) == ["a"]

    def test_ignore_invalid_type(self):
        with pytest.raises(TypeError, match="_ignore_"):
            class I(LiteralEnum):
                _ignore_ = 42
                A = "a"


# ===================================================================
# __or__ — combining enums
# ===================================================================

class TestOr:
    def test_combine_disjoint(self):
        class A(LiteralEnum):
            X = "x"

        class B(LiteralEnum):
            Y = "y"

        C = A | B
        assert list(C) == ["x", "y"]
        assert "x" in C
        assert "y" in C
        assert C.__name__ == "A|B"

    def test_combine_overlapping(self):
        class A(LiteralEnum):
            X = "shared"

        class B(LiteralEnum):
            Y = "shared"
            Z = "unique"

        C = A | B
        assert list(C) == ["shared", "unique"]
        assert C.names("shared") == ("X", "Y")

    def test_or_non_literalenum_returns_not_implemented(self):
        result = HttpMethod.__or__("not a literal enum")
        assert result is NotImplemented

    def test_or_preserves_both_as_literalenum(self):
        class A(LiteralEnum):
            X = 1

        class B(LiteralEnum):
            Y = 2

        C = A | B
        assert isinstance(C, LiteralEnumMeta)
        assert C.validate(1) == 1
        assert C.validate(2) == 2


# ===================================================================
# Edge cases
# ===================================================================

class TestEdgeCases:
    def test_single_member(self):
        class One(LiteralEnum):
            ONLY = "only"

        assert list(One) == ["only"]
        assert len(One) == 1
        assert "only" in One

    def test_none_only(self):
        class NoneOnly(LiteralEnum):
            N = None

        assert None in NoneOnly
        assert list(NoneOnly) == [None]
        assert NoneOnly.validate(None) is None

    def test_mixed_types(self):
        class Mixed(LiteralEnum):
            S = "hello"
            I = 42
            B = True
            N = None
            BY = b"x"

        assert len(Mixed) == 5
        assert "hello" in Mixed
        assert 42 in Mixed
        assert True in Mixed
        assert None in Mixed
        assert b"x" in Mixed

    def test_attribute_access_returns_plain_value(self):
        """Dotted access returns the literal, not a descriptor or wrapper."""
        val = HttpMethod.GET
        assert val == "GET"
        assert val is HttpMethod._members_["GET"]

    def test_metaclass_identity(self):
        assert type(HttpMethod) is LiteralEnumMeta
        assert isinstance(HttpMethod, LiteralEnumMeta)
