"""Start/Stop interface for detection only; no mouse automation."""

import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

from detect_buttons import PROJECT, read_image
from live_detection import enable_display_coordinates, foreground_target, inspect_once


def validate_settings(process_name, interval_text):
    name = process_name.strip()
    if not name.casefold().endswith(".exe") or any(c in name for c in '/\\'):
        raise ValueError("Enter an executable filename, such as iVMS-4200.exe.")
    interval = float(interval_text)
    if not 0.2 <= interval <= 60:
        raise ValueError("Check interval must be between 0.2 and 60 seconds.")
    return name, interval


def observation_loop(inspect, interval, stop, messages):
    """Worker code communicates through a queue, never through Tk widgets."""
    while not stop.is_set():
        result = inspect()
        if stop.is_set():
            break
        messages.put(("result", result))
        if stop.wait(interval):
            break


def detection_worker(process_name, interval, stop, messages):
    try:
        import mss
        import psutil
        import win32gui

        template = read_image(PROJECT / "assets" / "play-button.png")
        get_target = lambda: foreground_target(win32gui, psutil, process_name)
        # Create and close the capture object on the same worker thread.
        with mss.mss() as capture:
            inspect = lambda: inspect_once(get_target, capture, template, 0.94)
            observation_loop(inspect, interval, stop, messages)
    except Exception as error:
        messages.put(("error", str(error)))


class ControlWindow:
    def __init__(self, root, startup_error=None):
        self.root = root
        self.startup_error = startup_error
        self.worker = None
        self.stop_event = threading.Event()
        self.messages = queue.Queue()
        self.closing = False
        self.stopping = False
        self.failed = False

        root.title("CCTV Helper — Detection Preview")
        root.geometry("620x520")
        root.minsize(560, 480)
        frame = ttk.Frame(root, padding=24)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text="CCTV Detection Preview", font=("Segoe UI", 20, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Label(frame, text="Find Play buttons in iVMS. This version does not click.").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(0, 24))

        self.process = tk.StringVar(value="iVMS-4200.exe")
        self.interval = tk.StringVar(value="2")
        self.status = tk.StringVar(value="Stopped")
        self.count = tk.StringVar(value="—")
        self.detail = tk.StringVar(value="Press Start, then switch to iVMS and keep the camera tiles visible.")
        self.last_result = tk.StringVar(value="Last observation: —")
        ttk.Label(frame, text="iVMS executable").grid(row=2, column=0, sticky="w", padx=(0, 16))
        self.process_entry = ttk.Entry(frame, textvariable=self.process)
        self.process_entry.grid(row=2, column=1, sticky="ew", pady=6)
        ttk.Label(frame, text="Check interval (seconds)").grid(row=3, column=0, sticky="w")
        self.interval_entry = ttk.Entry(frame, textvariable=self.interval)
        self.interval_entry.grid(row=3, column=1, sticky="ew", pady=6)

        controls = ttk.Frame(frame)
        controls.grid(row=4, column=0, columnspan=2, sticky="w", pady=18)
        self.start_button = ttk.Button(controls, text="Start detection", command=self.start)
        self.start_button.pack(side="left", padx=(0, 10))
        self.stop_button = ttk.Button(controls, text="Stop", command=self.stop, state="disabled")
        self.stop_button.pack(side="left")
        ttk.Separator(frame).grid(row=5, column=0, columnspan=2, sticky="ew", pady=8)
        ttk.Label(frame, textvariable=self.status, font=("Segoe UI", 16, "bold")).grid(
            row=6, column=0, columnspan=2, sticky="w", pady=8)
        ttk.Label(frame, text="Current button candidates").grid(row=7, column=0, sticky="w")
        ttk.Label(frame, textvariable=self.count, font=("Segoe UI", 22, "bold")).grid(
            row=7, column=1, sticky="w")
        ttk.Label(frame, textvariable=self.detail, wraplength=510).grid(
            row=8, column=0, columnspan=2, sticky="w", pady=12)
        ttk.Label(frame, textvariable=self.last_result, wraplength=510).grid(
            row=9, column=0, columnspan=2, sticky="w", pady=6)
        if startup_error:
            self.start_button.configure(state="disabled")
            self.status.set("Unavailable")
            self.detail.set(startup_error)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(100, self.poll)

    def start(self):
        if self.worker is not None or self.startup_error:
            return
        try:
            name, interval = validate_settings(self.process.get(), self.interval.get())
        except ValueError as error:
            messagebox.showerror("Check settings", str(error), parent=self.root)
            return
        self.messages = queue.Queue()
        self.stop_event = threading.Event()
        self.stopping = self.failed = False
        self.status.set("Starting")
        self.count.set("—")
        self.last_result.set("Last observation: —")
        self.detail.set("Switch to iVMS to begin observing.")
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        for entry in (self.process_entry, self.interval_entry):
            entry.configure(state="disabled")
        self.worker = threading.Thread(target=detection_worker,
            args=(name, interval, self.stop_event, self.messages), daemon=True)
        self.worker.start()

    def stop(self):
        if self.worker is not None:
            self.stopping = True
            self.stop_event.set()
            self.status.set("Stopping")
            self.count.set("—")
            self.stop_button.configure(state="disabled")
            self.detail.set("Finishing the current check…")

    def poll(self):
        # Only the main thread reads or modifies widgets.
        while True:
            try:
                kind, data = self.messages.get_nowait()
            except queue.Empty:
                break
            if self.stopping or self.closing:
                continue
            if kind == "error":
                self.failed = True
                self.status.set("Error")
                self.count.set("—")
                self.detail.set(data)
            else:
                active = data["status"] == "observing"
                self.status.set("Observing iVMS" if active else "Paused")
                self.count.set(str(data["count"]) if active else "—")
                self.detail.set("Detection only. No mouse actions." if active else data["reason"])
                if active:
                    self.last_result.set(f"Last observation: {time.strftime('%H:%M:%S')} — {data['count']} candidates")
        if self.worker is not None and not self.worker.is_alive() and self.messages.empty():
            self.worker.join()
            self.worker = None
            self.stop_button.configure(state="disabled")
            self.start_button.configure(state="normal")
            for entry in (self.process_entry, self.interval_entry):
                entry.configure(state="normal")
            if not self.failed or self.stopping:
                self.status.set("Stopped")
                self.count.set("—")
                self.detail.set("Detection stopped. You can change settings and start again.")
        if self.closing and self.worker is None:
            self.root.destroy()
            return
        self.root.after(100, self.poll)

    def close(self):
        self.closing = True
        self.stop()
        # Closing never blocks the Tk event loop waiting on a thread.
        # A daemon worker cannot keep the process alive if a capture hangs.
        self.root.after(2000, self.root.destroy)


def main():
    error = None
    if sys.platform != "win32":
        error = "Live detection requires Windows. The control window can be previewed here."
    else:
        try:
            enable_display_coordinates()
        except (AttributeError, OSError) as exc:
            error = f"Display-coordinate setup failed: {exc}"
    root = tk.Tk()
    ControlWindow(root, error)
    root.mainloop()


if __name__ == "__main__":
    main()
