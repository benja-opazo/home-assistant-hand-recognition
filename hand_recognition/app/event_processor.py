import logging
import threading
import time

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
        self._continuous_lock = threading.Lock()
        self._continuous_running = False

    def reload_config(self, config: dict) -> None:
        self._config = config

    def process(self, event_id: str | None, camera: str | None, score: float) -> None:
        snapshot_mode = self._config.get("snapshot_mode", "normal")

        if snapshot_mode == "continuous":
            with self._continuous_lock:
                if self._continuous_running:
                    logger.info(
                        "Continuous snapshot burst already in progress — ignoring new event (camera=%s, event_id=%s)",
                        camera or "unknown", event_id or "N/A",
                    )
                    return
                self._continuous_running = True
            threading.Thread(
                target=self._run_continuous,
                args=(event_id, camera, score),
                daemon=True,
            ).start()
        else:
            self._process_single(event_id, camera, score)

    def _process_single(self, event_id: str | None, camera: str | None, score: float) -> None:
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

        self._publisher.publish(camera or "unknown", detections)

    def _run_continuous(self, event_id: str | None, camera: str | None, score: float) -> None:
        count    = int(self._config.get("continuous_snapshot_count", 5))
        interval = float(self._config.get("continuous_snapshot_interval", 5))
        logger.info(
            "Starting continuous snapshot burst: %d snapshots every %.1f s (camera=%s, event_id=%s)",
            count, interval, camera or "unknown", event_id or "N/A",
        )
        try:
            for i in range(count):
                if i > 0:
                    time.sleep(interval)
                logger.debug("Continuous burst snapshot %d/%d", i + 1, count)
                self._process_single(event_id, camera, score)
        finally:
            with self._continuous_lock:
                self._continuous_running = False
            logger.info(
                "Continuous snapshot burst finished (camera=%s, event_id=%s)",
                camera or "unknown", event_id or "N/A",
            )
