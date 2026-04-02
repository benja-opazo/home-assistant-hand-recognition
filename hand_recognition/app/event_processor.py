import logging

from frigate_client import FrigateClient
from hand_recognizer import HandRecognizer
from mqtt_publisher import MQTTPublisher
from snapshot_store import SnapshotStore

logger = logging.getLogger(__name__)


class EventProcessor:
    """Orchestrates the pipeline for a single Frigate event:
    fetch snapshot → run hand recognition → store → publish results.
    """

    def __init__(
        self,
        config: dict,
        frigate: FrigateClient,
        recognizer: HandRecognizer,
        publisher: MQTTPublisher,
        snapshot_store: SnapshotStore | None = None,
    ):
        self._config = config
        self._frigate = frigate
        self._recognizer = recognizer
        self._publisher = publisher
        self._snapshot_store = snapshot_store

    def process(self, event_id: str | None, camera: str | None, score: float) -> None:
        mode = self._config.get("frigate_snapshot_mode", "event")

        if mode == "latest_frame":
            if not camera:
                logger.warning(
                    "latest_frame mode requires a camera name but none was provided"
                )
                return
        else:
            if not event_id:
                logger.warning(
                    "Event mode requires an event ID but none was found in the message"
                )
                return

        image = self._frigate.get_snapshot(
            event_id,
            camera=camera,
            mode=mode,
            quality=self._config.get("frigate_snapshot_quality") or None,
            height=self._config.get("frigate_snapshot_height") or None,
            crop=bool(self._config.get("frigate_snapshot_crop", False)),
        )
        if image is None:
            return

        detections = self._recognizer.recognize(image)

        if self._snapshot_store is not None:
            self._snapshot_store.add(image, camera or "unknown", event_id, score, detections)

        if not detections:
            logger.info("No hands detected in snapshot for event %s", event_id)
            return

        self._publisher.publish(camera or "unknown", detections)
