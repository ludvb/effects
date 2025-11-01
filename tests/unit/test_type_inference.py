"""Unit tests for effect type inference from handler signatures."""

import pytest

from effects.effects import Effect, handler, send


class Query(Effect[str]):
    """An effect that queries for a value."""

    def __init__(self, key: str):
        self.key = key


class Command(Effect[None]):
    """An effect that represents a command."""

    def __init__(self, action: str):
        self.action = action


def test_inference_from_typed_function():
    """Test that effect type can be inferred from a typed function."""

    def handle_query(e: Query) -> str:
        return f"result_{e.key}"

    # Type is inferred from the annotation
    with handler(handle_query):
        result = send(Query("test"))
        assert result == "result_test"


def test_inference_from_method():
    """Test that effect type can be inferred from a method."""

    class Handler:
        def handle_query(self, e: Query) -> str:
            return f"handled_{e.key}"

    h = Handler()
    with handler(h.handle_query):
        result = send(Query("test"))
        assert result == "handled_test"


def test_explicit_type_overrides_inference():
    """Test that explicitly providing the type works and takes precedence."""

    # Even with a typed function, explicit type should work
    def handle_query(e: Query) -> str:
        return f"result_{e.key}"

    with handler(handle_query, Query):
        result = send(Query("test"))
        assert result == "result_test"


def test_backward_compatibility_with_lambdas():
    """Test that the old style with lambdas and explicit types still works."""

    with handler(lambda e: f"value_{e.key}", Query):
        result = send(Query("test"))
        assert result == "value_test"


def test_nested_handlers_with_inference():
    """Test nested handlers with type inference."""

    def handle_query(e: Query) -> str:
        return f"query_{e.key}"

    def handle_command(e: Command) -> None:
        # Commands don't return anything
        pass

    with handler(handle_query):
        with handler(handle_command):
            assert send(Query("test")) == "query_test"
            send(Command("action"))  # Should not raise


def test_error_no_parameters():
    """Test error when handler function has no parameters."""

    def no_params() -> str:
        return "test"

    with pytest.raises(TypeError, match="handler_func has no parameters"):
        handler(no_params)  # type: ignore[arg-type]


def test_error_no_type_annotation():
    """Test error when parameter has no type annotation."""

    def no_annotation(e):
        return "test"

    with pytest.raises(TypeError, match="no type annotation"):
        handler(no_annotation)


def test_error_wrong_type_annotation():
    """Test error when parameter annotation is not an Effect subclass."""

    def wrong_type(x: int) -> str:
        return str(x)

    with pytest.raises(TypeError, match="not a subclass of Effect"):
        handler(wrong_type)  # type: ignore[arg-type]


def test_error_non_effect_class():
    """Test error when annotation is a class but not an Effect subclass."""

    class NotAnEffect:
        pass

    def handle_not_effect(e: NotAnEffect) -> str:
        return "test"

    with pytest.raises(TypeError, match="not a subclass of Effect"):
        handler(handle_not_effect)  # type: ignore[arg-type]


def test_inference_with_generic_annotation():
    """Test that generic annotations are handled correctly."""

    # Using the full generic form should also work
    def handle_with_generic(e: Effect[str]) -> str:
        if isinstance(e, Query):
            return f"generic_{e.key}"
        return "unknown"

    # This should infer Effect as the type (the base class)
    with handler(handle_with_generic):
        # This will work because Query is a subclass of Effect
        result = send(Query("test"))
        assert result == "generic_test"


def test_decorator_syntax():
    """Test that handler can be used as a decorator."""

    @handler
    def handle_query(e: Query) -> str:
        return f"decorated_{e.key}"

    @handler
    def handle_command(e: Command) -> None:
        pass  # Commands don't return anything

    # Use the decorated handlers as context managers
    with handle_query:
        result = send(Query("test"))
        assert result == "decorated_test"

    # Stack decorated handlers
    with handle_query, handle_command:
        assert send(Query("test")) == "decorated_test"
        send(Command("action"))  # Should not raise


def test_callable_type_inference():
    """Test that Callable type parameters are correctly inferred from function annotations."""
    import dataclasses as dc
    from typing import Any, Callable

    @dc.dataclass
    class CallableEffect[T](Effect[int]):
        fn: Callable[[T], int]

    @handler
    def handle_int_callable(e: CallableEffect[int]) -> int:
        return e.fn(42)

    @handler
    def handle_str_callable(e: CallableEffect[str]) -> int:
        return e.fn("hello")

    @handler
    def handle_any_callable(e: CallableEffect[Any]) -> int:
        return 999

    def int_func(x: int) -> int:
        return x * 2

    def str_func(x: str) -> int:
        return len(x)

    def float_func(x: float) -> int:
        return int(x * 10)

    # Test with handler stack
    with handle_any_callable, handle_str_callable, handle_int_callable:
        # Should match handle_int_callable
        result1 = send(CallableEffect(fn=int_func))
        assert result1 == 84  # int_func(42) = 42 * 2 = 84

        # Should match handle_str_callable
        result2 = send(CallableEffect(fn=str_func))
        assert result2 == 5  # str_func("hello") = len("hello") = 5

        # Should match handle_any_callable (no specific float handler)
        result3 = send(CallableEffect(fn=float_func))
        assert result3 == 999  # Handled by Any handler
