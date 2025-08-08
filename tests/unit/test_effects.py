"""Unit tests for the effects library core functionality."""

from effects.effects import Effect, handler, send


class Ping(Effect[str]):
    """A simple effect that expects a 'pong' string response."""


class Add(Effect[int]):
    """An effect that requests the sum of two integers."""

    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y


class Sub(Effect[int]):
    """An effect that requests the difference between two integers."""

    def __init__(self, a: int, b: int):
        self.a = a
        self.b = b


class ModifyValue(Effect[int]):
    """Effect to modify an integer value through multiple handlers."""

    def __init__(self, value: int):
        self.value = value


def test_nested_type_handlers():
    """Test that nested handlers for different effect types work correctly."""
    # nested handlers for different effect types
    with handler(lambda e: f"{e.x + e.y}", Add):
        with handler(lambda e: e.a - e.b, Sub):
            assert send(Add(2, 3)) == "5"
            assert send(Sub(5, 2)) == 3


def test_handler_precedence():
    """Test that the innermost handler for a given effect type takes precedence."""
    # inner handler takes precedence over outer
    with handler(lambda e: "first", Ping):
        with handler(lambda e: "second", Ping):
            assert send(Ping()) == "second"
        # after inner exits, outer still applies
        # after outer exits inner, outer handler still applies
        assert send(Ping()) == "first"


def test_interpret_final_forwarding():
    """
    Test that interpret_final=False allows forwarding an effect to the next handler.
    Uses a simple integer modification scenario.
    """

    def handle_add_ten(effect: ModifyValue) -> int:
        """Outermost handler: adds 10 to the value."""
        return effect.value + 10

    def handle_multiply_by_two(effect: ModifyValue) -> int:
        """Inner handler: multiplies value by 2 and forwards."""
        modified_value = effect.value * 2
        # Create a new effect instance with the modified value
        forwarded_effect = ModifyValue(modified_value)
        # Send it to the next handler up the stack
        return send(forwarded_effect, interpret_final=False)

    # Set up nested handlers
    with handler(handle_add_ten, ModifyValue):
        with handler(handle_multiply_by_two, ModifyValue):
            # Send the initial effect
            result = send(ModifyValue(5))

    # Expected: (5 * 2) + 10 = 20
    assert result == 20
