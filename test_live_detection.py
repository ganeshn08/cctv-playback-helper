"""Tests for live-preview decisions without accessing the desktop."""

import unittest
from unittest.mock import Mock, patch

import numpy as np

from detect_buttons import PROJECT, read_image
from live_detection import foreground_target, inspect_once


class PreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = read_image(PROJECT / "assets/play-button.png")
        # Synthetic fixture: no private shop screenshots are needed to run tests.
        cls.stopped = np.full((1080, 1920, 3), 95, dtype=np.uint8)
        height, width = cls.template.shape[:2]
        for x, y in [(673, 265), (1485, 265), (673, 709), (1485, 709)]:
            cls.stopped[y:y + height, x:x + width] = cls.template

    def test_other_app_is_not_captured(self):
        capture = Mock()
        result = inspect_once(lambda: None, capture, self.template, 0.94)
        self.assertEqual(result["status"], "paused")
        capture.grab.assert_not_called()

    def test_changed_foreground_discards_capture(self):
        capture = Mock()
        capture.grab.return_value = self.stopped
        target = (123, 456, 10, 20, 1930, 1100)
        result = inspect_once(Mock(side_effect=[target, None]), capture, self.template, 0.94)
        self.assertEqual(result["status"], "paused")
        self.assertNotIn("buttons", result)

    def test_change_during_detection_discards_results(self):
        capture = Mock()
        capture.grab.return_value = self.stopped
        target = (123, 456, 10, 20, 1930, 1100)
        result = inspect_once(Mock(side_effect=[target, target, None]), capture, self.template, 0.94)
        self.assertEqual(result["status"], "paused")

    def test_screen_coordinates_include_window_offset(self):
        capture = Mock()
        capture.grab.return_value = np.dstack((self.stopped, np.full(self.stopped.shape[:2], 255, dtype=np.uint8)))
        target = (123, 456, -100, 20, 1820, 1100)
        result = inspect_once(lambda: target, capture, self.template, 0.94)
        self.assertEqual(result["count"], 4)
        self.assertEqual(result["buttons"][0]["screen_x"], 599)
        self.assertEqual(result["buttons"][0]["screen_y"], 311)
        capture.grab.assert_called_once_with((-100, 20, 1820, 1100))

    def test_wrong_process_rejected_even_with_ivms_window_title(self):
        gui, processes, winprocess = Mock(), Mock(), Mock()
        gui.GetForegroundWindow.return_value = 123
        gui.IsIconic.return_value = False
        gui.GetWindowText.return_value = "iVMS-4200"
        winprocess.GetWindowThreadProcessId.return_value = (1, 456)
        processes.Process.return_value.name.return_value = "chrome.exe"
        processes.Error = RuntimeError
        with patch.dict("sys.modules", {"win32process": winprocess}):
            self.assertIsNone(foreground_target(gui, processes, "iVMS-4200.exe"))
        gui.GetClientRect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
