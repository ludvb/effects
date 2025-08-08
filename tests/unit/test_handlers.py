"""Unit tests for effect handlers and advanced features."""

from effects.effects import Effect, NoHandlerError, barrier, bind, handler, safe_send, send


class Query(Effect[str]):
    """An effect that queries for information."""

    def __init__(self, key: str):
        self.key = key


class Command(Effect[None]):
    """An effect that represents a command with no return value."""

    def __init__(self, action: str):
        self.action = action


def test_no_handler_error():
    """Test that NoHandlerError is raised when no handler is found."""
    query = Query("test")
    try:
        send(query)
        assert False, "Should have raised NoHandlerError"
    except NoHandlerError as e:
        assert "No handler for effect" in str(e)
        assert e.effect == query


def test_safe_send_with_default():
    """Test safe_send returns default value when no handler exists."""
    result = safe_send(Query("test"), default_value="default")
    assert result == "default"


def test_safe_send_without_default():
    """Test safe_send returns None when no handler exists and no default given."""
    result = safe_send(Query("test"))
    assert result is None


def test_safe_send_with_handler():
    """Test safe_send returns handler result when handler exists."""
    with handler(lambda e: f"value_{e.key}", Query):
        result = safe_send(Query("test"))
        assert result == "value_test"


def test_barrier():
    """Test that barrier prevents effect handling."""
    with handler(lambda e: "outer", Query):
        with barrier(Query):
            try:
                send(Query("test"))
                assert False, "Should have raised NoHandlerError"
            except NoHandlerError:
                pass  # Expected

        # After barrier, outer handler should work again
        assert send(Query("test")) == "outer"


def test_bind_function():
    """Test bind creates a pure function with bound handlers."""

    def computation(x: int) -> str:
        result = send(Query(str(x)))
        return f"computed_{result}"

    # Bind the computation with a handler
    bound_fn = bind(computation, handler(lambda e: f"handled_{e.key}", Query))

    # The bound function should work without context
    result = bound_fn(42)
    assert result == "computed_handled_42"

    # Original function without handler should fail
    try:
        computation(42)
        assert False, "Should have raised NoHandlerError"
    except NoHandlerError:
        pass  # Expected


def test_bind_with_current_context():
    """Test bind can include current context."""

    def inner_computation() -> str:
        return send(Query("inner"))

    # Set up outer context
    with handler(lambda e: "outer_value", Query):
        # Bind with current context
        bound_fn = bind(inner_computation, bind_current_context=True)

        # Should use the outer handler
        result = bound_fn()
        assert result == "outer_value"


def test_handler_on_enter_exit():
    """Test handler's on_enter and on_exit callbacks."""
    events: list[str] = []

    def on_enter() -> None:
        events.append("enter")

    def on_exit(exc_type, exc_val, exc_tb) -> None:
        events.append("exit")

    with handler(lambda e: "result", Query, on_enter=on_enter, on_exit=on_exit):
        assert events == ["enter"]
        send(Query("test"))

    assert events == ["enter", "exit"]


def test_multiple_effect_types():
    """Test handling multiple different effect types."""
    with handler(lambda e: f"query_{e.key}", Query):
        with handler(lambda e: None, Command):
            # Both effect types should work
            assert send(Query("test")) == "query_test"
            assert send(Command("action")) is None

            # Can handle multiple sends
            assert send(Query("other")) == "query_other"
            send(Command("another"))


def test_effect_inheritance():
    """Test that effect subclasses work correctly."""

    class SpecialQuery(Query):
        """A specialized query effect."""

    with handler(lambda e: f"handled_{e.key}", Query):
        # Subclass should be handled by parent class handler
        result = send(SpecialQuery("special"))
        assert result == "handled_special"
