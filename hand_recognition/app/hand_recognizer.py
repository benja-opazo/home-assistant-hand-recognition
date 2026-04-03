import logging
import mediapipe as mp
import numpy as np
import cv2

logger = logging.getLogger(__name__)

# Gesture classification based on finger states.
# Finger state: True = extended, False = curled.
# Order: [thumb, index, middle, ring, pinky]
GESTURES: dict[tuple[bool, ...], str] = {
    (False, False, False, False, False): "fist",
    (True,  False, False, False, False): "thumbs_up",
    (False, True,  False, False, False): "pointing",
    (False, True,  True,  False, False): "peace",
    (True,  True,  True,  True,  True ): "open_palm",
    (False, True,  True,  True,  True ): "four_fingers",
    (True,  True,  False, False, True ): "rock_on",
    (True,  False, False, False, True ): "call_me",
    (False, False, False, False, True ): "pinky",
    (True,  True,  True,  False, False): "three_fingers",
}

GESTURE_LABELS: dict[str, str] = {
    "fist":          "Fist",
    "thumbs_up":     "Thumbs up",
    "pointing":      "Pointing",
    "peace":         "Peace (V sign)",
    "open_palm":     "Open palm",
    "four_fingers":  "Four fingers",
    "rock_on":       "Rock on (horns)",
    "call_me":       "Call me",
    "pinky":         "Pinky",
    "three_fingers": "Three fingers",
}

ALL_GESTURES: list[str] = list(GESTURES.values())


# Defaults — overridden by config keys landmark_sigmoid_k / landmark_score_threshold / landmark_thumb_angle
_DEFAULT_SIGMOID_K       = 4.0
_DEFAULT_SCORE_THRESHOLD = 0.6
# Thumb opening angle in degrees from horizontal in the rotated frame.
# 0° = purely horizontal (x-axis). Positive = tilts toward palm-down direction.
# Try 30–45° if the thumb is consistently underscored.
_DEFAULT_THUMB_ANGLE     = 0.0


def _rotate_landmarks(lm, angle: float) -> list[tuple[float, float]]:
    """Rotate all landmarks by -angle so the palm axis aligns with the y-axis."""
    cos_a, sin_a = np.cos(-angle), np.sin(-angle)
    return [(lm[i].x * cos_a - lm[i].y * sin_a,
             lm[i].x * sin_a + lm[i].y * cos_a)
            for i in range(21)]


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + np.exp(-x))


_FINGER_NAMES = ("thumb", "index", "middle", "ring", "pinky")


def _finger_scores(hand_landmarks, sigmoid_k: float, thumb_angle_deg: float = 0.0) -> tuple[tuple[float, ...], float]:
    """Return (scores, angle_deg).

    scores: continuous extension score in [0, 1] for each finger, order = _FINGER_NAMES.
    angle_deg: palm rotation in degrees (0 = upright, positive = clockwise).
    thumb_angle_deg: direction of thumb extension in the rotated frame, measured from
        horizontal (0° = x-axis only, 45° = equal x+y component).
    """
    lm = hand_landmarks.landmark
    tips = [4, 8, 12, 16, 20]
    pips = [3, 6, 10, 14, 18]

    # Compute palm orientation: wrist (0) → middle MCP (9)
    dx = lm[9].x - lm[0].x
    dy = lm[9].y - lm[0].y
    angle     = np.arctan2(dy, dx) + np.pi / 2  # offset so "up" = 0 (y increases downward)
    palm_size = np.hypot(dx, dy) or 1e-6         # normalise by hand scale

    pts = _rotate_landmarks(lm, angle)

    scores = []
    # Thumb: project pip→tip displacement onto the configured opening direction
    thumb_rad  = np.radians(thumb_angle_deg)
    cos_t, sin_t = np.cos(thumb_rad), np.sin(thumb_rad)
    tdx = pts[pips[0]][0] - pts[tips[0]][0]
    tdy = pts[pips[0]][1] - pts[tips[0]][1]
    scores.append(_sigmoid(sigmoid_k * (tdx * cos_t + tdy * sin_t) / palm_size))
    # Other fingers: extension along y-axis (pip.y - tip.y > 0 means extended)
    for tip, pip in zip(tips[1:], pips[1:]):
        scores.append(_sigmoid(sigmoid_k * (pts[pip][1] - pts[tip][1]) / palm_size))

    angle_deg = float(np.degrees(angle))
    angle_deg = ((angle_deg + 180) % 360) - 180  # normalise to [-180, 180]
    return tuple(scores), round(angle_deg, 1)


def _match_gesture(scores: tuple[float, ...], score_threshold: float) -> tuple[str, float]:
    """Return (gesture_name, confidence) for the best-matching gesture.

    Confidence is the mean per-finger match score across all five fingers.
    """
    best_name  = "unknown"
    best_score = 0.0

    for pattern, name in GESTURES.items():
        score = sum(
            s if expected else (1.0 - s)
            for s, expected in zip(scores, pattern)
        ) / len(pattern)

        if score > best_score:
            best_score = score
            best_name  = name

    if best_score < score_threshold:
        return "unknown", round(best_score, 3)
    return best_name, round(best_score, 3)


def _all_gesture_scores(finger_scores: tuple[float, ...]) -> list[dict]:
    """Return all gestures with their match scores, sorted descending."""
    results = []
    for pattern, name in GESTURES.items():
        score = sum(
            s if expected else (1.0 - s)
            for s, expected in zip(finger_scores, pattern)
        ) / len(pattern)
        results.append({"gesture": name, "score": round(score, 3)})
    results.sort(key=lambda x: x["score"], reverse=True)
    return results


class HandRecognizer:
    def __init__(self, config: dict | None = None):
        cfg = config or {}
        enabled = cfg.get("enabled_gestures", ALL_GESTURES)
        self._enabled: set[str]      = set(enabled) if enabled else set(ALL_GESTURES)
        self._sigmoid_k: float       = float(cfg.get("landmark_sigmoid_k",       _DEFAULT_SIGMOID_K))
        self._score_threshold: float = float(cfg.get("landmark_score_threshold", _DEFAULT_SCORE_THRESHOLD))
        self._thumb_angle: float     = float(cfg.get("landmark_thumb_angle",     _DEFAULT_THUMB_ANGLE))

        self._hands = mp.solutions.hands.Hands(
            static_image_mode=True,
            max_num_hands=int(cfg.get("mediapipe_max_num_hands", 2)),
            min_detection_confidence=float(cfg.get("mediapipe_min_detection_confidence", 0.5)),
            model_complexity=int(cfg.get("mediapipe_model_complexity", 1)),
        )
        logger.info(
            "MediaPipe Hands initialised — complexity=%s, min_confidence=%.2f, "
            "max_hands=%s, sigmoid_k=%.1f, score_threshold=%.2f, thumb_angle=%.1f°, enabled_gestures=%s",
            cfg.get("mediapipe_model_complexity", 1),
            float(cfg.get("mediapipe_min_detection_confidence", 0.5)),
            cfg.get("mediapipe_max_num_hands", 2),
            self._sigmoid_k,
            self._score_threshold,
            self._thumb_angle,
            sorted(self._enabled),
        )

    def reload_config(self, config: dict) -> None:
        """Hot-reload scoring parameters without recreating the MediaPipe model.

        Parameters that require a restart (max_num_hands, min_detection_confidence,
        model_complexity, recognizer_backend) are intentionally ignored here.
        """
        cfg = config or {}
        enabled = cfg.get("enabled_gestures", ALL_GESTURES)
        self._enabled         = set(enabled) if enabled else set(ALL_GESTURES)
        self._sigmoid_k       = float(cfg.get("landmark_sigmoid_k",       _DEFAULT_SIGMOID_K))
        self._score_threshold = float(cfg.get("landmark_score_threshold", _DEFAULT_SCORE_THRESHOLD))
        self._thumb_angle     = float(cfg.get("landmark_thumb_angle",     _DEFAULT_THUMB_ANGLE))
        logger.info(
            "Detection parameters reloaded — sigmoid_k=%.1f, score_threshold=%.2f, "
            "thumb_angle=%.1f°, enabled_gestures=%s",
            self._sigmoid_k, self._score_threshold, self._thumb_angle, sorted(self._enabled),
        )

    def recognize_debug(self, image: np.ndarray) -> list[dict]:
        """Like recognize(), but each detection includes all_scores: sorted list of every gesture with its score."""
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = self._hands.process(rgb)

        if not results.multi_hand_landmarks:
            return []

        detections = []
        for hand_landmarks, handedness in zip(
            results.multi_hand_landmarks, results.multi_handedness
        ):
            scores, angle_deg   = _finger_scores(hand_landmarks, self._sigmoid_k, self._thumb_angle)
            gesture, confidence = _match_gesture(scores, self._score_threshold)
            hand_label          = handedness.classification[0].label
            detections.append({
                "gesture":       gesture,
                "score":         confidence,
                "hand":          hand_label,
                "rotation_deg":  angle_deg,
                "finger_scores": {name: round(s, 3) for name, s in zip(_FINGER_NAMES, scores)},
                "all_scores":    _all_gesture_scores(scores),
            })
        return detections

    def available_gestures(self) -> list[tuple[str, str]]:
        """Return [(value, label), ...] for all gestures this recognizer supports."""
        return [(g, GESTURE_LABELS.get(g, g)) for g in ALL_GESTURES]

    def recognize(self, image: np.ndarray) -> list[dict]:
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = self._hands.process(rgb)

        if not results.multi_hand_landmarks:
            return []

        detections = []
        for hand_landmarks, handedness in zip(
            results.multi_hand_landmarks, results.multi_handedness
        ):
            scores, _           = _finger_scores(hand_landmarks, self._sigmoid_k, self._thumb_angle)
            gesture, confidence = _match_gesture(scores, self._score_threshold)

            if gesture != "unknown" and gesture not in self._enabled:
                logger.debug(
                    "Gesture '%s' is disabled — skipping this detection", gesture
                )
                continue

            hand_label = handedness.classification[0].label  # "Left" or "Right"
            detections.append({
                "gesture": gesture,
                "score":   confidence,
                "hand":    hand_label,
            })
            logger.debug("Detected %s hand: %s (score=%.3f)", hand_label, gesture, confidence)

        return detections

    def close(self):
        self._hands.close()
