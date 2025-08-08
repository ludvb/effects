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
class Log(fx.Effect[str]):
    def __init__(self, message: str):
        self.message = message

# Basic handler
def log_writer(effect: Log) -> str:
    formatted = f"LOG: {effect.message}"
    print(formatted)
    return formatted

# Handler that modifies and forwards
def add_timestamp(effect: Log) -> str:
    timestamped = f"[{datetime.now().isoformat()}] {effect.message}"
    return fx.send(Log(timestamped), interpret_final=False)

# Application code
def app():
    result = fx.send(Log("Something happened"))
    print(f"Got: {result}")

# Simple handler
with fx.handler(log_writer, Log):
    app()
# Output: LOG: Something happened
#         Got: LOG: Something happened

# Stacked handlers - timestamp runs first, then forwards to log_writer
with fx.handler(log_writer, Log), fx.handler(add_timestamp, Log):
    app()
# Output: LOG: [2024-...] Something happened
#         Got: LOG: [2024-...] Something happened
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