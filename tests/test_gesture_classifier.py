"""
Gesture classifier test script.

Usage:
    # Test with a local image file:
    python tests/test_gesture_classifier.py path/to/hand.jpg

    # Test with a URL:
    python tests/test_gesture_classifier.py https://example.com/hand.jpg

    # Test with multiple images:
    python tests/test_gesture_classifier.py img1.jpg img2.jpg img3.jpg

    # Run built-in sanity check using a synthetic blank image (no hands expected):
    python tests/test_gesture_classifier.py --sanity
"""

import argparse
import sys
import os

# Allow importing from app/ without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import cv2
import numpy as np
import requests

from hand_recognizer import HandRecognizer


def load_image_from_path(path: str) -> np.ndarray:
    img = cv2.imread(path)
    if img is None:
        raise ValueError(f"Could not read image: {path}")
    return img


def load_image_from_url(url: str) -> np.ndarray:
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    arr = np.frombuffer(response.content, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Could not decode image from URL: {url}")
    return img


def load_image(source: str) -> np.ndarray:
    if source.startswith("http://") or source.startswith("https://"):
        return load_image_from_url(source)
    return load_image_from_path(source)


def run_test(recognizer: HandRecognizer, source: str) -> None:
    print(f"\n{'─' * 50}")
    print(f"  Source : {source}")
    print(f"{'─' * 50}")

    try:
        image = load_image(source)
        h, w = image.shape[:2]
        print(f"  Size   : {w}×{h} px")
    except Exception as e:
        print(f"  ERROR  : {e}")
        return

    detections = recognizer.recognize(image)

    if not detections:
        print("  Result : No hands detected")
        return

    for i, d in enumerate(detections, 1):
        print(f"  Hand {i}  : {d['hand']}")
        print(f"  Gesture: {d['gesture']}")
        print(f"  Score  : {d['score']:.3f}")


def sanity_check(recognizer: HandRecognizer) -> None:
    print("\nRunning sanity check with a blank image (expecting no detections)...")
    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    detections = recognizer.recognize(blank)
    if not detections:
        print("  PASS — no hands detected in blank image.")
    else:
        print(f"  FAIL — unexpectedly detected {len(detections)} hand(s) in blank image.")
        for d in detections:
            print(f"         {d}")


def main():
    parser = argparse.ArgumentParser(description="Test the hand gesture classifier.")
    parser.add_argument(
        "sources",
        nargs="*",
        metavar="IMAGE",
        help="Image file paths or URLs to classify.",
    )
    parser.add_argument(
        "--sanity",
        action="store_true",
        help="Run a quick sanity check with a synthetic blank image.",
    )
    args = parser.parse_args()

    if not args.sources and not args.sanity:
        parser.print_help()
        sys.exit(1)

    print("Loading MediaPipe HandRecognizer...")
    recognizer = HandRecognizer()

    if args.sanity:
        sanity_check(recognizer)

    for source in args.sources:
        run_test(recognizer, source)

    recognizer.close()
    print(f"\n{'─' * 50}")
    print("Done.")


if __name__ == "__main__":
    main()
