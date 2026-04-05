import logging

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import GestureRecognizer as _MPGestureRecognizer
from mediapipe.tasks.python.vision import GestureRecognizerOptions

logger = logging.getLogger(__name__)

# MediaPipe Tasks gesture names → our normalized names
_GESTURE_MAP: dict[str, str] = {
    "Closed_Fist": "fist",
    "Open_Palm":   "open_palm",
    "Pointing_Up": "pointing",
    "Thumb_Down":  "thumbs_down",
    "Thumb_Up":    "thumbs_up",
    "Victory":     "peace",
    "ILoveYou":    "i_love_you",
}

_GESTURE_LABELS: dict[str, str] = {
    "fist":        "Fist",
    "open_palm":   "Open palm",
    "pointing":    "Pointing up",
    "thumbs_down": "Thumbs down",
    "thumbs_up":   "Thumbs up",
    "peace":       "Peace (V sign)",
    "i_love_you":  "I love you",
}

_ALL_GESTURES: list[str] = list(_GESTURE_MAP.values())


def _palm_facing(landmarks, hand_label: str) -> bool:
    """Return True if the palm faces the camera, False if the back of the hand does."""
    dx = landmarks[9].x - landmarks[0].x
    dy = landmarks[9].y - landmarks[0].y
    angle = np.arctan2(dy, dx) + np.pi / 2
    cos_a, sin_a = np.cos(-angle), np.sin(-angle)
    # Only need rotated x for landmarks 1 (thumb MCP) and 17 (pinky MCP)
    rx1  = landmarks[1].x  * cos_a - landmarks[1].y  * sin_a
    rx17 = landmarks[17].x * cos_a - landmarks[17].y * sin_a
    x_sign = -1.0 if hand_label == "Left" else 1.0
    return x_sign * (rx1 - rx17) > 0


class GestureRecognizer:
    def __init__(self, config: dict | None = None):
        cfg = config or {}
        model_path = cfg.get("gesture_recognizer_model_path", "/data/gesture_recognizer.task")
        enabled = cfg.get("enabled_gestures", _ALL_GESTURES)
        self._enabled: set[str] = set(enabled) if enabled else set(_ALL_GESTURES)

        options = GestureRecognizerOptions(
            base_options=BaseOptions(model_asset_path=model_path),
            num_hands=int(cfg.get("mediapipe_max_num_hands", 2)),
            min_hand_detection_confidence=float(cfg.get("mediapipe_min_detection_confidence", 0.5)),
        )
        self._recognizer = _MPGestureRecognizer.create_from_options(options)
        logger.info(
            "MediaPipe GestureRecognizer initialised — model=%s, min_confidence=%.2f, "
            "max_hands=%s, enabled_gestures=%s",
            model_path,
            float(cfg.get("mediapipe_min_detection_confidence", 0.5)),
            cfg.get("mediapipe_max_num_hands", 2),
            sorted(self._enabled),
        )

    def available_gestures(self) -> list[tuple[str, str]]:
        """Return [(value, label), ...] for all gestures this recognizer supports."""
        return [(g, _GESTURE_LABELS.get(g, g)) for g in _ALL_GESTURES]

    def recognize(self, image: np.ndarray) -> list[dict]:
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._recognizer.recognize(mp_image)

        if not result.gestures:
            return []

        detections = []
        for gestures, handedness, hand_lms in zip(result.gestures, result.handedness, result.hand_landmarks):
            raw_name = gestures[0].category_name
            if raw_name == "None":
                continue

            gesture    = _GESTURE_MAP.get(raw_name, "unknown")
            score      = round(gestures[0].score, 3)
            hand_label = handedness[0].category_name  # "Left" or "Right"

            if gesture != "unknown" and gesture not in self._enabled:
                logger.debug("Gesture '%s' is disabled — skipping this detection", gesture)
                continue

            try:
                facing = "camera" if _palm_facing(hand_lms, hand_label) else "away"
            except Exception:
                facing = "unknown"

            detections.append({
                "gesture": gesture,
                "score":   score,
                "hand":    hand_label,
                "facing":  facing,
            })
            logger.debug("Detected %s hand: %s (score=%.3f)", hand_label, gesture, score)

        return detections

    def close(self):
        self._recognizer.close()
