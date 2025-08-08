"""Unit tests for the util module."""

from collections.abc import Generator
from contextlib import contextmanager

from effects.util import stack


@contextmanager
def counter(counts: list[int]) -> Generator[None, None, None]:
    """A simple context manager that increments a counter on enter and exit."""
    counts.append(1)  # Enter
    try:
        yield
    finally:
        counts.append(2)  # Exit


def test_stack_multiple_context_managers():
    """Test that stack properly manages multiple context managers."""
    counts: list[int] = []

    with stack(counter(counts), counter(counts)):
        assert counts == [1, 1]  # Both entered

    assert counts == [1, 1, 2, 2]  # Both exited in reverse order


def test_stack_with_return_value():
    """Test that stack can return a value when specified."""
    return_value = "test_value"
    counts: list[int] = []

    with stack(counter(counts), return_value=return_value) as result:
        assert result == return_value
        assert counts == [1]  # Context manager entered

    assert counts == [1, 2]  # Context manager exited


def test_stack_without_return_value():
    """Test that stack returns itself when no return value is specified."""
    counts: list[int] = []

    with stack(counter(counts)) as result:
        assert result is not None
        assert counts == [1]  # Context manager entered

    assert counts == [1, 2]  # Context manager exited


def test_stack_empty():
    """Test that stack works with no context managers."""
    with stack() as result:
        assert result is not None  # Should return self


def test_stack_exception_propagation():
    """Test that stack doesn't suppress exceptions."""
    counts: list[int] = []

    try:
        with stack(counter(counts)):
            assert counts == [1]  # Context manager entered
            raise ValueError("test error")
    except ValueError as e:
        assert str(e) == "test error"
        assert counts == [1, 2]  # Exit was still called
    else:
        assert False, "Exception should have been raised"
