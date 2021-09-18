# Effects: Algebraic Effects for Python

A lightweight algebraic effects library for Python.
Effect systems provide a powerful way to structure applications by separating a behavior's intent (an effect) from its implementation (a handler), enabling runtime behaviors to be composed and modified across different abstraction levels.

## Installation

Install directly from GitHub:

```bash
pip install git+https://github.com/ludvb/effects.git
```

## Usage

The following example demonstrates a simple logging system.
It shows how to define effects, create handlers that can modify and forward effects, and compose them.

```python
import effects as fx
import sys
from datetime import datetime

# 1. Define a logging effect that expects a formatted string back.
class Log(fx.Effect[str]):
    def __init__(self, message: str):
        self.message = message

# 2. The final handler formats the message and returns it.
def log_writer(effect: Log) -> str:
    formatted_message = f"LOG: {effect.message}"
    print(formatted_message, file=sys.stdout)
    return formatted_message

# 3. A handler that adds a timestamp and forwards the effect.
def add_timestamp(effect: Log) -> str:
    new_message = f"[{datetime.now().isoformat()}] {effect.message}"
    # Forward the modified effect to the next handler and return its result.
    return fx.send(Log(new_message), interpret_final=False)

# --- Core Application Logic ---
def main_app_logic():
    print("Application is running...")
    # The application sends the effect and receives the final, formatted string.
    final_log = fx.send(Log("Something important happened!"))
    print(f"Final log message was: '{final_log}'")
    print("Application finished.")

# --- Composition Root ---
# Here, we compose the application with different logging behaviors.

print("--- Running with a simple logger ---")
with fx.handler(log_writer, Log):
    main_app_logic()
# Expected Output:
# Application is running...
# LOG: Something important happened!
# Final log message was: 'LOG: Something important happened!'
# Application finished.

print("\n--- Running with a timestamp logger ---")
# Handlers are stacked. `add_timestamp` is called first, which then
# forwards the modified effect to `log_writer`.
with fx.handler(log_writer, Log):
    with fx.handler(add_timestamp, Log):
        main_app_logic()
# Expected Output:
# Application is running...
# LOG: [YYYY-MM-DDTHH:MM:SS.ffffff] Something important happened!
# Final log message was: 'LOG: [YYYY-MM-DDTHH:MM:SS.ffffff] Something important happened!'
# Application finished.
```

## See also

- [effects-logging](https://github.com/ludvb/effects-logging): A logging framework built on top of the effects library.

## Contributing

Contributions are welcome! Please feel free to open an issue to report bugs or suggest features, or submit a pull request with improvements.

## License

This project is licensed under the MIT License.