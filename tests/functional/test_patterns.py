"""Functional tests for common effect usage patterns."""

from typing import Any

from effects.effects import Effect, bind, handler, send


class Log(Effect[None]):
    """Effect for logging messages."""

    def __init__(self, message: str):
        self.message = message


class GetConfig(Effect[dict[str, Any]]):
    """Effect for retrieving configuration."""


class SaveData(Effect[bool]):
    """Effect for saving data."""

    def __init__(self, key: str, value: Any):
        self.key = key
        self.value = value


def test_layered_application():
    """Test a typical layered application pattern with effects."""
    # Simulate a simple application with logging, config, and data layers
    logs: list[str] = []
    config = {"debug": True, "max_retries": 3}
    storage: dict[str, Any] = {}

    def log_handler(effect: Log) -> None:
        logs.append(effect.message)

    def config_handler(effect: GetConfig) -> dict[str, Any]:
        return config

    def storage_handler(effect: SaveData) -> bool:
        storage[effect.key] = effect.value
        return True

    def business_logic(data: str) -> bool:
        """Core business logic using effects."""
        send(Log(f"Processing: {data}"))

        cfg = send(GetConfig())
        if cfg["debug"]:
            send(Log("Debug mode enabled"))

        # Process and save
        processed = data.upper()
        success = send(SaveData("result", processed))

        if success:
            send(Log("Data saved successfully"))

        return success

    # Set up the application with all handlers
    with handler(log_handler, Log):
        with handler(config_handler, GetConfig):
            with handler(storage_handler, SaveData):
                # Run the business logic
                result = business_logic("hello world")

    # Verify the effects were handled correctly
    assert result is True
    assert storage["result"] == "HELLO WORLD"
    assert "Processing: hello world" in logs
    assert "Debug mode enabled" in logs
    assert "Data saved successfully" in logs


def test_testing_with_mocked_effects():
    """Test that effects make testing easier by allowing handler substitution."""

    class Database(Effect[str]):
        """Effect for database queries."""

        def __init__(self, query: str):
            self.query = query

    def application_code() -> str:
        """Some application code that uses database."""
        result = send(Database("SELECT * FROM users"))
        return f"Users: {result}"

    # Test with mocked database
    def mock_db_handler(effect: Database) -> str:
        if "users" in effect.query:
            return "Alice, Bob"
        return "no data"

    with handler(mock_db_handler, Database):
        result = application_code()
        assert result == "Users: Alice, Bob"

    # Test with different mock
    def empty_db_handler(effect: Database) -> str:
        return "empty"

    with handler(empty_db_handler, Database):
        result = application_code()
        assert result == "Users: empty"


def test_composable_handlers():
    """Test that handlers can be composed and reused."""

    class Counter(Effect[int]):
        """Effect to get current count."""

    class Increment(Effect[None]):
        """Effect to increment counter."""

    def create_counter_handlers(initial: int = 0):
        """Factory for creating counter handlers."""
        count = [initial]  # Mutable container for state

        def get_count(effect: Counter) -> int:
            return count[0]

        def increment(effect: Increment) -> None:
            count[0] += 1

        return [
            handler(get_count, Counter),
            handler(increment, Increment),
        ]

    def counter_app() -> list[int]:
        """Application using counter effects."""
        results = []
        results.append(send(Counter()))
        send(Increment())
        results.append(send(Counter()))
        send(Increment())
        results.append(send(Counter()))
        return results

    # Test with counter starting at 0
    handlers = create_counter_handlers(0)
    bound_app = bind(counter_app, *handlers)
    assert bound_app() == [0, 1, 2]

    # Test with counter starting at 10
    handlers = create_counter_handlers(10)
    bound_app = bind(counter_app, *handlers)
    assert bound_app() == [10, 11, 12]


def test_generator_with_effects():
    """Test that generators work properly with effects."""

    class Yield(Effect[None]):
        """Effect to yield a value."""

        def __init__(self, value: Any):
            self.value = value

    def generator_with_effects():
        """A generator that uses effects."""
        for i in range(3):
            send(Log(f"Yielding {i}"))
            yield i
            send(Yield(i))

    logs: list[str] = []
    yielded: list[int] = []

    def log_handler(effect: Log) -> None:
        logs.append(effect.message)

    def yield_handler(effect: Yield) -> None:
        yielded.append(effect.value)

    # Bind the generator with handlers
    bound_gen = bind(
        generator_with_effects,
        handler(log_handler, Log),
        handler(yield_handler, Yield),
    )

    # Consume the generator
    result = list(bound_gen())

    assert result == [0, 1, 2]
    assert logs == ["Yielding 0", "Yielding 1", "Yielding 2"]
    assert yielded == [0, 1, 2]
