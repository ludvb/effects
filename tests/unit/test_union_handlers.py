"""Unit tests for union effect handlers."""

import pytest

from effects.effects import Effect, NoHandlerError, get_stack, handler, send


class EffectA(Effect[str]):
    """First test effect with string return."""

    def __init__(self, value: str):
        self.value = value


class EffectB(Effect[str]):
    """Second test effect with string return."""

    def __init__(self, number: int):
        self.number = number


class EffectC(Effect[int]):
    """Third test effect with int return."""

    def __init__(self, data: str):
        self.data = data


def test_union_handler_basic():
    """Test basic union handler functionality."""

    @handler
    def handle_a_or_b(eff: EffectA | EffectB) -> str:
        if isinstance(eff, EffectA):
            return f"A:{eff.value}"
        elif isinstance(eff, EffectB):
            return f"B:{eff.number}"
        return "unknown"

    with handle_a_or_b:
        assert send(EffectA("hello")) == "A:hello"
        assert send(EffectB(42)) == "B:42"


def test_union_handler_with_union_import():
    """Test union handler using Union from typing."""

    @handler
    def handle_union(eff: EffectA | EffectB) -> str:
        if isinstance(eff, EffectA):
            return eff.value.upper()
        else:
            return str(eff.number * 2)

    with handle_union:
        assert send(EffectA("test")) == "TEST"
        assert send(EffectB(21)) == "42"


def test_union_handler_three_types():
    """Test union handler with three effect types."""

    class EffectD(Effect[str]):
        def __init__(self, flag: bool):
            self.flag = flag

    @handler
    def handle_multiple(eff: EffectA | EffectB | EffectD) -> str:
        if isinstance(eff, EffectA):
            return f"a:{eff.value}"
        elif isinstance(eff, EffectB):
            return f"b:{eff.number}"
        elif isinstance(eff, EffectD):
            return f"d:{eff.flag}"
        return "?"

    with handle_multiple:
        assert send(EffectA("x")) == "a:x"
        assert send(EffectB(1)) == "b:1"
        assert send(EffectD(True)) == "d:True"


def test_nested_union_handlers():
    """Test that union handlers nest correctly."""

    @handler
    def outer_handler(eff: EffectA | EffectB) -> str:
        return "outer"

    @handler
    def inner_handler(eff: EffectA) -> str:
        return "inner"

    with outer_handler:
        assert send(EffectA("test")) == "outer"
        assert send(EffectB(1)) == "outer"

        with inner_handler:
            # Inner handler shadows outer for EffectA
            assert send(EffectA("test")) == "inner"
            # But EffectB still handled by outer
            assert send(EffectB(1)) == "outer"


def test_union_handler_not_handling_other_effects():
    """Test that union handler doesn't catch unrelated effects."""

    @handler
    def handle_a_b(eff: EffectA | EffectB) -> str:
        return "handled"

    with handle_a_b:
        assert send(EffectA("x")) == "handled"
        assert send(EffectB(1)) == "handled"

        # EffectC should not be handled
        with pytest.raises(NoHandlerError):
            send(EffectC("data"))


def test_union_with_non_effect_type_error():
    """Test that union with non-Effect type raises error."""

    class NotAnEffect:
        pass

    with pytest.raises(TypeError, match="non-Effect type"):

        @handler
        def bad_handler(eff: EffectA | NotAnEffect):  # type: ignore
            return "bad"


def test_handler_repr_with_union():
    """Test that handler repr correctly shows union types."""

    @handler
    def union_handler(eff: EffectA | EffectB) -> str:
        return "test"

    with union_handler:
        stack = get_stack()
        assert len(stack) == 1
        repr_str = repr(stack[0])
        # Should contain both effect names separated by |
        assert "EffectA" in repr_str
        assert "EffectB" in repr_str
        assert "|" in repr_str


def test_explicit_type_with_union_not_supported():
    """Test that explicit effect_type parameter doesn't support tuples/unions directly."""

    # This should still work with single type
    h = handler(lambda e: "test", EffectA)
    with h:
        assert send(EffectA("x")) == "test"

    # But passing a tuple directly isn't the intended API
    # (users should use type annotations for unions)


def test_union_handler_with_decorator():
    """Test union handler using decorator syntax."""

    @handler
    def decorated_union(eff: EffectA | EffectB) -> str:
        return f"decorated:{type(eff).__name__}"

    with decorated_union:
        assert send(EffectA("a")) == "decorated:EffectA"
        assert send(EffectB(1)) == "decorated:EffectB"


def test_union_handler_mixed_with_regular():
    """Test union handlers mixed with regular handlers."""

    @handler
    def handle_union(eff: EffectA | EffectB) -> str:
        return "union"

    @handler
    def handle_c(eff: EffectC) -> int:
        return 100

    with handle_union, handle_c:
        assert send(EffectA("x")) == "union"
        assert send(EffectB(1)) == "union"
        assert send(EffectC("y")) == 100
