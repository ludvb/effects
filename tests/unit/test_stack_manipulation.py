"""Unit tests for effect handler stack manipulation."""

import effects as fx


class Query(fx.Effect[str]):
    """An effect that queries for information."""

    def __init__(self, key: str):
        self.key = key


class Command(fx.Effect[None]):
    """An effect that represents a command."""

    def __init__(self, action: str):
        self.action = action


def test_get_stack_empty():
    """Test that get_stack returns empty list when no handlers."""
    stack = fx.get_stack()
    assert stack == []


def test_get_stack_with_handlers():
    """Test that get_stack returns current handlers."""

    @fx.handler
    def handle_query(e: Query) -> str:
        return f"query_{e.key}"

    @fx.handler
    def handle_command(e: Command) -> None:
        pass

    # No handlers initially
    assert fx.get_stack() == []

    # One handler
    with handle_query:
        stack = fx.get_stack()
        assert len(stack) == 1
        assert repr(stack[0]) == "_EffectHandler(handle_query, Query)"

        # Two handlers
        with handle_command:
            stack = fx.get_stack()
            assert len(stack) == 2
            assert repr(stack[0]) == "_EffectHandler(handle_query, Query)"
            assert repr(stack[1]) == "_EffectHandler(handle_command, Command)"

    # Back to no handlers
    assert fx.get_stack() == []


def test_handler_repr():
    """Test that handler __repr__ provides useful debugging info."""

    @fx.handler
    def named_handler(e: Query) -> str:
        return "result"

    with named_handler:
        stack = fx.get_stack()
        handler_repr = repr(stack[0])
        assert "named_handler" in handler_repr
        assert "Query" in handler_repr


def test_lambda_handler_repr():
    """Test that lambda handlers have reasonable repr."""

    lambda_handler = fx.handler(lambda e: f"result_{e.key}", Query)

    with lambda_handler:
        stack = fx.get_stack()
        handler_repr = repr(stack[0])
        assert "<lambda>" in handler_repr
        assert "Query" in handler_repr


def test_stack_manipulation_with_bind():
    """Test manual stack manipulation using bind and get_stack."""

    @fx.handler
    def outer_handler(e: Query) -> str:
        return f"outer_{e.key}"

    @fx.handler
    def inner_handler(e: Query) -> str:
        return f"inner_{e.key}"

    def computation():
        return fx.send(Query("test"))

    # Set up outer context
    with outer_handler:
        # Original context uses outer handler
        assert fx.send(Query("test")) == "outer_test"

        # Create a bound computation with only inner handler
        # (not including current context)
        custom_bound = fx.bind(computation, inner_handler)

        # The bound computation uses only inner handler
        result = custom_bound()
        assert result == "inner_test"

        # Original stack unchanged
        assert fx.send(Query("test")) == "outer_test"


def test_handler_reordering_with_get_stack():
    """Test that handlers from get_stack() can be reordered with bind."""

    @fx.handler
    def first_handler(e: Query) -> str:
        return "first"

    @fx.handler
    def second_handler(e: Query) -> str:
        return "second"

    @fx.handler
    def third_handler(e: Query) -> str:
        return "third"

    def computation():
        return fx.send(Query("test"))

    # Normal stacking - last (innermost) wins
    with first_handler, second_handler:
        assert computation() == "second"

        # Get current stack
        current = fx.get_stack()
        assert len(current) == 2

        # Reverse the order - now first wins!
        bound_reversed = fx.bind(computation, *reversed(current))
        assert bound_reversed() == "first"

        # Add a new handler on top (last position) - it wins
        bound_with_third = fx.bind(computation, *current, third_handler)
        assert bound_with_third() == "third"

        # Original context unchanged
        assert computation() == "second"


def test_fallback_handler_pattern():
    """Test using bind to insert a fallback handler at the bottom of the stack."""

    @fx.handler
    def user_handler(e: Query) -> str:
        return "user"

    @fx.handler
    def fallback_handler(e: Query) -> str:
        return "fallback"

    @fx.handler
    def fallback_command(e: Command) -> None:
        # Fallback for a different effect type
        pass

    def query_computation():
        return fx.send(Query("test"))

    def command_computation():
        fx.send(Command("test"))
        return "done"

    # User provides a Query handler but not a Command handler
    with user_handler:
        # Query uses user's handler
        assert query_computation() == "user"

        # Get current stack
        current = fx.get_stack()

        # Add fallback at the BOTTOM for Query - user handler still wins
        bound_with_query_fallback = fx.bind(query_computation, fallback_handler, *current)
        assert bound_with_query_fallback() == "user"  # User handler takes precedence

        # Add fallback for Command (which user didn't handle)
        bound_with_command_fallback = fx.bind(command_computation, fallback_command, *current)
        assert bound_with_command_fallback() == "done"  # Fallback handles the Command

        # Without fallback, Command would raise NoHandlerError
        try:
            fx.bind(command_computation, *current)()
            assert False, "Should have raised NoHandlerError"
        except fx.NoHandlerError:
            pass  # Expected


def test_stack_isolation_with_bind():
    """Test that bind creates isolated handler stacks."""

    @fx.handler
    def handler1(e: Query) -> str:
        return "handler1"

    @fx.handler
    def handler2(e: Query) -> str:
        return "handler2"

    def check_stack_length():
        return len(fx.get_stack())

    with handler1:
        # Current context has one handler
        assert check_stack_length() == 1

        # Bound function with different handlers
        bound_check = fx.bind(check_stack_length, handler2)

        # Bound function sees only its own handler
        assert bound_check() == 1

        # Original context unchanged
        assert check_stack_length() == 1


def test_bind_with_current_context():
    """Test bind with bind_current_context=True includes existing handlers."""

    @fx.handler
    def base_handler(e: Query) -> str:
        return f"base_{e.key}"

    @fx.handler
    def additional_handler(e: Command) -> None:
        pass

    def computation():
        stack = fx.get_stack()
        # Should see both handlers
        return len(stack)

    with base_handler:
        # Bind with current context
        bound = fx.bind(computation, additional_handler, bind_current_context=True)

        # Should see both handlers (base from context + additional)
        count = bound()
        assert count == 2


def test_recreating_handlers_from_stack():
    """Test recreating handlers from stack information."""

    @fx.handler
    def handler1(e: Query) -> str:
        return "first"

    @fx.handler
    def handler2(e: Command) -> None:
        pass

    def computation():
        # Check we can send both effect types
        query_result = fx.send(Query("test"))
        fx.send(Command("action"))
        return query_result

    # Set up handlers
    with handler1, handler2:
        # Original context works
        assert computation() == "first"

        # Get stack to inspect handlers
        current_handlers = fx.get_stack()
        assert len(current_handlers) == 2

        # For this example, we just create fresh handlers
        # In practice, you might want to expose handler properties
        # or provide a method to clone handlers
        new_h1 = fx.handler(lambda e: "first", Query)
        new_h2 = fx.handler(lambda e: None, Command)

        # Bind with recreated handlers
        bound = fx.bind(computation, new_h1, new_h2)

        # Should work the same way
        assert bound() == "first"


def test_stack_inspection_for_debugging():
    """Test that get_stack helps with debugging handler configuration."""

    @fx.handler
    def production_handler(e: Query) -> str:
        return "production"

    @fx.handler
    def debug_handler(e: Query) -> str:
        # Can inspect what handlers are above us
        stack = fx.get_stack()
        # Return debug info
        return f"handlers: {len(stack)}"

    with production_handler, debug_handler:
        result = fx.send(Query("test"))
        assert result == "handlers: 2"
