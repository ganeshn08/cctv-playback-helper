# CCTV Playback Helper

A Python tool that detects Play-button icons in iVMS-4200 camera views.

- Detect buttons in a saved screenshot and print their locations.
- Preview detections in the active iVMS window on Windows.
- Pause live detection when another application is active.

The current version only reports detections. It does not click buttons or save live captures. Live Windows capture is awaiting testing; saved-image detection has been tested on Windows with Python 3.14.7. The reference icon uses a fixed size, so display scaling or a different interface may require adjustment.

## Requirements

Python 3.10 or newer. Windows is required for live detection.

Dependencies: OpenCV, NumPy, and, on Windows, MSS, psutil, and pywin32. Install them from `requirements.txt`.

## Install on Windows

Open Command Prompt in the project folder:

```bat
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

## Run

Detect buttons in your own saved screenshot:

```bat
.venv\Scripts\python detect_buttons.py "path\to\screenshot.png"
```

Start live detection, then switch to iVMS and keep its camera tiles unobscured:

```bat
.venv\Scripts\python live_detection.py
```

Return to the terminal and press **Ctrl+C** to stop. Results are printed when they change. Live capture searches the window's visible content area; overlapping windows or notifications can affect results.

Optional settings:

```bat
.venv\Scripts\python live_detection.py --interval 2 --threshold 0.94 --process-name "iVMS-4200.exe"
```

If detection stays paused, confirm the exact iVMS executable name in Task Manager's Details tab. Similarity scores are not probabilities that a click is safe.

## Tests

```bat
.venv\Scripts\python -m unittest test_live_detection.py
```

Tests use synthetic images and mocked Windows calls. Two example shop screenshots are included: `for mac2.png` shows stopped cameras with four Play buttons; `for mac.png` shows active cameras with no central Play buttons.
