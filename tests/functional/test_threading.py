"""Functional tests for threading and concurrency with effects."""

import queue
from threading import Thread

from effects.effects import Effect, handler, send


class Ping(Effect[str]):
    """A simple effect that expects a string response."""


def test_thread_safety():
    """Test that effect handlers are context-local and thread-safe."""
    results: queue.Queue[str] = queue.Queue()

    def worker(thread_id: int) -> None:
        """Worker function that uses thread-specific handlers."""
        # Each thread uses its own handler
        with handler(lambda e: f"pong-{thread_id}", Ping):
            # Send multiple effects to verify isolation
            for _ in range(5):
                results.put(send(Ping()))

    # Create and start multiple threads
    threads = [Thread(target=worker, args=(i,)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Collect and verify results
    collected: list[str] = []
    while not results.empty():
        collected.append(results.get())

    # Each thread should have produced exactly 5 results with its ID
    for i in range(3):
        expected = f"pong-{i}"
        assert collected.count(expected) == 5, (
            f"Thread {i} produced {collected.count(expected)} results, expected 5"
        )

    # Total should be 15 results (3 threads × 5 calls each)
    assert len(collected) == 15, f"Expected 15 total results, got {len(collected)}"
