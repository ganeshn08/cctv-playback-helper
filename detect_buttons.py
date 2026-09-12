"""Lesson 1: find Play icons in a saved image. Never capture or click a screen."""

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


PROJECT = Path(__file__).resolve().parent


def read_image(path):
    """Read pixels from disk, including Windows paths with non-English names."""
    pixels = np.frombuffer(Path(path).read_bytes(), dtype=np.uint8)
    image = cv2.imdecode(pixels, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Cannot decode image: {path}")
    return image


def find_buttons(image, template, threshold=0.94):
    """Return distinct template matches, sorted top-to-bottom, left-to-right.

    Scores express visual similarity, not a probability that clicking is safe.
    This prototype expects the same icon size as the supplied screenshots.
    """
    height, width = template.shape[:2]
    if image.shape[0] < height or image.shape[1] < width:
        raise ValueError("The screenshot is smaller than the Play icon template.")
    if not 0 < threshold <= 1:
        raise ValueError("Threshold must be greater than 0 and at most 1.")
    scores = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
    matches = []

    while True:
        _, score, _, location = cv2.minMaxLoc(scores)
        if score < threshold:
            break
        x, y = location
        matches.append({
            "center_x": x + width // 2,
            "center_y": y + height // 2,
            "score": round(score, 4),
        })
        # Nearby matching positions usually describe the same icon.
        # Exclude them so one button is counted only once.
        scores[max(0, y - height + 1):y + height,
               max(0, x - width + 1):x + width] = -1

    return sorted(matches, key=lambda item: (item["center_y"], item["center_x"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="Saved screenshot to inspect")
    parser.add_argument("--template", type=Path,
                        default=PROJECT / "assets" / "play-button.png")
    parser.add_argument("--threshold", type=float, default=0.94)
    args = parser.parse_args()
    try:
        matches = find_buttons(read_image(args.image), read_image(args.template),
                               args.threshold)
    except (OSError, ValueError, cv2.error) as error:
        parser.exit(1, f"Error: {error}\n")
    print(json.dumps({"image": args.image.name, "count": len(matches),
                      "buttons": matches}, indent=2))


if __name__ == "__main__":
    main()
