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

ALL_GESTURES: list[str] = list(GESTURES.values())


def _finger_states(hand_landmarks) -> tuple[bool, ...]:
    lm = hand_landmarks.landmark
    tips = [4, 8, 12, 16, 20]
    pips = [3, 6, 10, 14, 18]

    states = []
    # Thumb: compare x-axis (works for right hand; mirrors for left)
    states.append(lm[tips[0]].x < lm[pips[0]].x)
    # Other fingers: tip y < pip y means extended (y increases downward)
    for tip, pip in zip(tips[1:], pips[1:]):
        states.append(lm[tip].y < lm[pip].y)
    return tuple(states)


class HandRecognizer:
    def __init__(self, config: dict | None = None):
        cfg = config or {}
        enabled = cfg.get("enabled_gestures", ALL_GESTURES)
        self._enabled: set[str] = set(enabled) if enabled else set(ALL_GESTURES)

        self._hands = mp.solutions.hands.Hands(
            static_image_mode=True,
            max_num_hands=int(cfg.get("mediapipe_max_num_hands", 2)),
            min_detection_confidence=float(cfg.get("mediapipe_min_detection_confidence", 0.5)),
            model_complexity=int(cfg.get("mediapipe_model_complexity", 1)),
        )
        logger.info(
            "MediaPipe Hands initialised — complexity=%s, min_confidence=%.2f, "
            "max_hands=%s, enabled_gestures=%s",
            cfg.get("mediapipe_model_complexity", 1),
            float(cfg.get("mediapipe_min_detection_confidence", 0.5)),
            cfg.get("mediapipe_max_num_hands", 2),
            sorted(self._enabled),
        )

    def recognize(self, image: np.ndarray) -> list[dict]:
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = self._hands.process(rgb)

        if not results.multi_hand_landmarks:
            return []

        detections = []
        for hand_landmarks, handedness in zip(
            results.multi_hand_landmarks, results.multi_handedness
        ):
            states  = _finger_states(hand_landmarks)
            gesture = GESTURES.get(states, "unknown")

            if gesture != "unknown" and gesture not in self._enabled:
                logger.debug(
                    "Gesture '%s' is disabled — skipping this detection", gesture
                )
                continue

            score      = handedness.classification[0].score
            hand_label = handedness.classification[0].label  # "Left" or "Right"
            detections.append({
                "gesture": gesture,
                "score":   round(score, 3),
                "hand":    hand_label,
            })
            logger.debug("Detected %s hand: %s (score=%.3f)", hand_label, gesture, score)

        return detections

    def close(self):
        self._hands.close()
