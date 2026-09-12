"""Windows live Play-button preview. Prints candidates; never clicks or saves images."""

import argparse
import ctypes
import json
import sys
import time

import numpy as np

from detect_buttons import PROJECT, find_buttons, read_image


def foreground_target(gui, process_api, expected_name):
    """Accept only the foreground iVMS process, returning its client rectangle."""
    import win32process

    window = gui.GetForegroundWindow()
    if not window or gui.IsIconic(window):
        return None
    _, pid = win32process.GetWindowThreadProcessId(window)
    try:
        name = process_api.Process(pid).name()
    except process_api.Error:
        return None
    if name.casefold() != expected_name.casefold():
        return None
    left, top, right, bottom = gui.GetClientRect(window)
    left, top = gui.ClientToScreen(window, (left, top))
    right, bottom = gui.ClientToScreen(window, (right, bottom))
    if right <= left or bottom <= top:
        return None
    return window, pid, left, top, right, bottom


def inspect_once(get_target, capture, template, threshold):
    """Discard a capture if the foreground window or its geometry changes."""
    target = get_target()
    if target is None:
        return {"status": "paused", "reason": "iVMS is not the active target"}
    _, _, left, top, right, bottom = target
    image = np.asarray(capture.grab((left, top, right, bottom)))[:, :, :3].copy()
    if get_target() != target:
        return {"status": "paused", "reason": "Window changed during capture"}
    matches = find_buttons(image, template, threshold)
    if get_target() != target:
        return {"status": "paused", "reason": "Window changed during detection"}
    for match in matches:
        match["screen_x"] = left + match["center_x"]
        match["screen_y"] = top + match["center_y"]
    return {"status": "observing", "count": len(matches), "buttons": matches}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--process-name", default="iVMS-4200.exe",
                        help="Exact iVMS executable name from Task Manager Details")
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--threshold", type=float, default=0.94)
    args = parser.parse_args()
    if sys.platform != "win32":
        parser.exit(1, "Live detection requires Windows. Use detect_buttons.py on this computer.\n")
    if not 0.2 <= args.interval <= 60:
        parser.error("interval must be between 0.2 and 60 seconds")
    if not 0 < args.threshold <= 1:
        parser.error("threshold must be greater than 0 and at most 1")

    # Use physical pixels consistently on displays with Windows scaling enabled.
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        set_dpi = user32.SetProcessDpiAwarenessContext
        set_dpi.argtypes = [ctypes.c_void_p]
        set_dpi.restype = ctypes.c_bool
        if not set_dpi(ctypes.c_void_p(-4)):
            raise ctypes.WinError(ctypes.get_last_error())
    except (AttributeError, OSError) as error:
        parser.exit(1, f"Cannot establish physical-pixel display coordinates: {error}\n")

    try:
        import mss
        import psutil
        import win32gui
    except ImportError as error:
        parser.exit(1, f"Missing Windows dependency: {error}. Install requirements.txt first.\n")

    template = read_image(PROJECT / "assets" / "play-button.png")
    get_target = lambda: foreground_target(win32gui, psutil, args.process_name)
    print("Preview only. Switch to iVMS. Return here and press Ctrl+C to stop.", flush=True)
    print(f"Expected executable: {args.process_name}. Keep camera tiles unobscured.", flush=True)
    previous = None
    try:
        with mss.mss() as capture:
            while True:
                try:
                    result = inspect_once(get_target, capture, template, args.threshold)
                except Exception as error:
                    # A closed window or capture failure must not produce stale results.
                    result = {"status": "paused", "reason": f"Capture/detection error: {error}"}
                message = json.dumps(result)
                if message != previous:
                    print(time.strftime("%H:%M:%S"), message, flush=True)
                    previous = message
                time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopped.", flush=True)


if __name__ == "__main__":
    main()
