from typing import Any, overload, Literal
from types import TracebackType


class stack[T]:
    def __init__(self, *context_managers: Any, return_value: T | None = None) -> None:
        self._context_managers = context_managers
        self._return_value = return_value

    @overload
    def __enter__(self: "stack[None]") -> "stack[None]": ...
    
    @overload
    def __enter__(self: "stack[T]") -> T: ...
    
    def __enter__(self: "stack[None] | stack[T]"):
        for context_manager in self._context_managers:
            context_manager.__enter__()
        if self._return_value is not None:
            return self._return_value
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None
    ) -> Literal[False]:
        # Call __exit__ on all context managers in reverse order
        # If any raise an exception, that exception will propagate
        for context_manager in reversed(self._context_managers):
            context_manager.__exit__(exc_type, exc_val, exc_tb)
        return False

    def __repr__(self) -> str:
        context_managers_str = ", ".join(str(cm) for cm in self._context_managers)
        return (
            f"stack(context_managers=[{context_managers_str}], "
            f"return_value={self._return_value})"
        )
