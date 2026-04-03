import logging

logger = logging.getLogger(__name__)

_BACKENDS = ("landmarks", "gesture_recognizer")


def create_recognizer(config: dict):
    """Instantiate the correct recognizer backend based on config."""
    backend = config.get("recognizer_backend", "landmarks")

    if backend == "gesture_recognizer":
        from hand_recognizer_gr import GestureRecognizer
        return GestureRecognizer(config)

    if backend != "landmarks":
        logger.warning(
            "Unknown recognizer_backend '%s', falling back to 'landmarks'", backend
        )

    from hand_recognizer import HandRecognizer
    return HandRecognizer(config)
