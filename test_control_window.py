"""Worker lifecycle tests; no desktop or camera access."""
import queue
import threading
import unittest
from unittest.mock import Mock

from control_window import observation_loop, validate_settings


class WorkerTests(unittest.TestCase):
    def test_invalid_settings(self):
        for value in ("nan", "inf", "0", "61", "hello"):
            with self.assertRaises(ValueError):
                validate_settings("iVMS-4200.exe", value)
        with self.assertRaises(ValueError):
            validate_settings("C:\\other.exe", "2")

    def test_stop_interrupts_long_wait(self):
        stop, messages = threading.Event(), queue.Queue()
        worker = threading.Thread(target=observation_loop,
            args=(lambda: {"count": 4}, 60, stop, messages), daemon=True)
        worker.start()
        self.assertEqual(messages.get(timeout=2), ("result", {"count": 4}))
        stop.set()
        worker.join(timeout=1)
        self.assertFalse(worker.is_alive())

    def test_no_results_after_stop_during_capture(self):
        stop, messages = threading.Event(), queue.Queue()
        def inspect():
            stop.set()
            return {"count": 4}
        observation_loop(inspect, 2, stop, messages)
        self.assertTrue(messages.empty())

    def test_already_stopped_does_not_capture(self):
        stop, inspect = threading.Event(), Mock()
        stop.set()
        observation_loop(inspect, 2, stop, queue.Queue())
        inspect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
