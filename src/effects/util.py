import sys


class stack:
    def __init__(self, *context_managers, return_value=None):
        self._context_managers = context_managers
        self._return_value = return_value

    def __enter__(self):
        for context_manager in self._context_managers:
            context_manager.__enter__()
        if self._return_value is not None:
            return self._return_value
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        suppressed = False
        for context_manager in reversed(self._context_managers):
            try:
                if context_manager.__exit__(exc_type, exc_val, exc_tb):
                    suppressed = True
                    # Clear exception details for subsequent handlers
                    exc_type, exc_val, exc_tb = None, None, None
            except Exception:
                # A new exception in __exit__ overrides the old one
                suppressed = False
                exc_type, exc_val, exc_tb = sys.exc_info()

        # Return False to propagate an unsuppressed exception, True otherwise.
        return suppressed

    def __repr__(self):
        context_managers_str = ", ".join(str(cm) for cm in self._context_managers)
        return (
            f"stack(context_managers=[{context_managers_str}], "
            f"return_value={self._return_value})"
        )
