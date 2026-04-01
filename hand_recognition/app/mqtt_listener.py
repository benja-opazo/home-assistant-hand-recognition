import json
import logging
import paho.mqtt.client as mqtt

from frigate_client import FrigateClient
from hand_recognizer import HandRecognizer
from mqtt_publisher import MQTTPublisher
from snapshot_store import SnapshotStore

logger = logging.getLogger(__name__)

FRIGATE_EVENTS_TOPIC = "frigate/events"


class MQTTListener:
    def __init__(
        self,
        config: dict,
        frigate_client: FrigateClient,
        hand_recognizer: HandRecognizer,
        publisher: MQTTPublisher,
        snapshot_store: SnapshotStore | None = None,
    ):
        self._config = config
        self._frigate = frigate_client
        self._recognizer = hand_recognizer
        self._publisher = publisher
        self._snapshot_store = snapshot_store
        self._client = mqtt.Client()
        self._setup_client()

    def _setup_client(self) -> None:
        cfg = self._config
        if cfg.get("mqtt_username"):
            self._client.username_pw_set(cfg["mqtt_username"], cfg.get("mqtt_password"))

        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("Connected to MQTT broker, subscribing to %s", FRIGATE_EVENTS_TOPIC)
            client.subscribe(FRIGATE_EVENTS_TOPIC)
        else:
            logger.error("MQTT connection failed with code %d", rc)

    def _on_disconnect(self, client, userdata, rc):
        if rc != 0:
            logger.warning("Unexpected MQTT disconnect (rc=%d), will auto-reconnect", rc)

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning("Could not parse MQTT message: %s", e)
            return

        event_type = payload.get("type")
        after = payload.get("after", {})

        if event_type not in ("new", "update"):
            return

        label = after.get("label")
        score = after.get("top_score") or after.get("score", 0)
        event_id = after.get("id")
        camera = after.get("camera", "unknown")

        if label != "person":
            return

        threshold = self._config.get("score_threshold", 0.7)
        if score < threshold:
            logger.debug(
                "Skipping event %s: score %.3f below threshold %.3f",
                event_id, score, threshold,
            )
            return

        logger.info(
            "Processing event %s on camera '%s' (score=%.3f)",
            event_id, camera, score,
        )

        image = self._frigate.get_snapshot(event_id)
        if image is None:
            return

        detections = self._recognizer.recognize(image)

        if self._snapshot_store is not None:
            self._snapshot_store.add(image, camera, event_id, score, detections)

        if not detections:
            logger.info("No hands detected in snapshot for event %s", event_id)
            return

        self._publisher.publish(camera, detections)

    def start(self) -> None:
        cfg = self._config
        logger.info("Connecting to MQTT broker %s:%d", cfg["mqtt_host"], cfg["mqtt_port"])
        self._client.connect(cfg["mqtt_host"], cfg["mqtt_port"], keepalive=60)
        self._client.loop_start()

    def stop(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()

    @property
    def mqtt_client(self) -> mqtt.Client:
        return self._client
