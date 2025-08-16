# Effects: Algebraic Effects for Python

A lightweight algebraic effects library for Python.
Effect systems provide a powerful way to structure applications by separating a behavior's intent (an effect) from its implementation (a handler), enabling runtime behaviors to be composed and modified across different abstraction levels.

## Installation

Install directly from GitHub:

```bash
pip install git+https://github.com/ludvb/effects.git
```

## Usage

```python
import effects as fx
from datetime import datetime

# Define an effect
class Log(fx.Effect[int]):
    def __init__(self, message: str):
        self.message = message

# Define effect handlers
@fx.handler
def log_writer(effect: Log):
    formatted = f"LOG: {effect.message}"
    print(formatted)
    return len(formatted)

@fx.handler
def add_timestamp(effect: Log):
    timestamped = f"[{datetime.now().isoformat()}] {effect.message}"
    return fx.send(Log(timestamped), interpret_final=False)

# Define an effectful computation
def log_event(message: str):
    return fx.send(Log(message))

# Application code
def app():
    result = log_event("Something happened")
    print(f"Characters written: {result}")

# Use the decorated handler
with log_writer:
    app()
# Output: LOG: Something happened
#         Characters written: 23

# Stack multiple handlers - timestamp runs first, then forwards to log_writer
with log_writer, add_timestamp:
    app()
# Output: LOG: [2024-...] Something happened
#         Characters written: 52

# Effect types are inferred from the signature of the handler.
# It's also possible to specify the effect type explicitly when using an untyped handler:
with fx.handler(lambda e: 0, Log):
    app()
# Output: Characters written: 0
```

## Advanced Usage

### Inspecting the Handler Stack

You can inspect the current handler stack for debugging or advanced control flow:

```python
import effects as fx

@fx.handler
def my_handler(effect: Log) -> int:
    # Inside a handler, you can inspect the full stack
    stack = fx.get_stack()
    print(f"Current stack depth: {len(stack)}")
    for handler in stack:
        print(f"  {handler}")  # Uses __repr__ for debugging
    return 0

with my_handler:
    fx.send(Log("test"))
    # Output: Current stack depth: 1
    #         _EffectHandler(my_handler, Log)
```

### Custom Handler Ordering with `bind`

The `bind` function combined with `get_stack()` enables advanced handler composition:

```python
import effects as fx

@fx.handler
def production_handler(e: Log) -> int:
    print("Production handler")
    return 1

@fx.handler
def debug_handler(e: Log) -> int:
    print("Debug handler")
    return 2

@fx.handler
def fallback_handler(e: Log) -> int:
    print("Fallback handler - using default")
    return 0

def my_computation():
    return fx.send(Log("test"))

# Normal stacking - innermost (debug) wins
with production_handler, debug_handler:
    result = my_computation()  # Prints: "Debug handler", returns 2

    # Get current handlers to reorder them
    current = fx.get_stack()

    # Reverse the order - now production wins!
    bound_reversed = fx.bind(my_computation, *reversed(current))
    result = bound_reversed()  # Prints: "Production handler", returns 1

    # Insert fallback at the BOTTOM - only used if no other handler matches
    # This is useful for providing defaults while respecting user handlers
    bound_with_fallback = fx.bind(my_computation, fallback_handler, *current)
    result = bound_with_fallback()  # Prints: "Debug handler", returns 2

    # But fallback activates if we use a different effect type
    def other_computation():
        return fx.send(OtherEffect())  # No handler for this!

    bound_other = fx.bind(other_computation, fallback_handler, *current)
    # Would use fallback since current handlers don't handle OtherEffect
```

## See also

- [effects-logging](https://github.com/ludvb/effects-logging): A logging framework built on top of the effects library.

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Type checking
pyright

# Linting and formatting
ruff check src/ tests/
ruff format src/ tests/
```

## Contributing

Contributions are welcome! Please feel free to open an issue to report bugs or suggest features, or submit a pull request with improvements.

## License

This project is licensed under the MIT License.
