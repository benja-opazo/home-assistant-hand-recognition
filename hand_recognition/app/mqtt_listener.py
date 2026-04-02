import json
import logging
import paho.mqtt.client as mqtt
import yaml

from frigate_client import FrigateClient
from hand_recognizer import HandRecognizer
from mqtt_publisher import MQTTPublisher
from snapshot_store import SnapshotStore

logger = logging.getLogger(__name__)


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

    # ------------------------------------------------------------------ #
    #  MQTT callbacks                                                      #
    # ------------------------------------------------------------------ #

    def _setup_client(self) -> None:
        cfg = self._config
        if cfg.get("mqtt_username"):
            self._client.username_pw_set(cfg["mqtt_username"], cfg.get("mqtt_password"))
        self._client.on_connect    = self._on_connect
        self._client.on_message    = self._on_message
        self._client.on_disconnect = self._on_disconnect

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            topic = self._config.get("mqtt_topic", "frigate/events")
            logger.info("Connected to MQTT broker, subscribing to %s", topic)
            client.subscribe(topic)
        else:
            logger.error("MQTT connection failed with code %d", rc)

    def _on_disconnect(self, client, userdata, rc):
        if rc != 0:
            logger.warning("Unexpected MQTT disconnect (rc=%d), will auto-reconnect", rc)

    def _on_message(self, client, userdata, msg):
        try:
            raw = msg.payload.decode()
        except UnicodeDecodeError as e:
            logger.warning(
                "Could not decode MQTT message on topic '%s': %s | raw bytes: %s",
                msg.topic, e, msg.payload,
            )
            return

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            # Some Frigate topics (e.g. tracked_object_update) publish YAML instead of JSON
            try:
                payload = yaml.safe_load(raw)
                if not isinstance(payload, dict):
                    raise ValueError(f"Expected a mapping, got {type(payload).__name__}")
                logger.debug("Parsed message on topic '%s' as YAML", msg.topic)
            except Exception as e:
                logger.warning(
                    "Could not parse MQTT message on topic '%s' as JSON or YAML: %s\n"
                    "Raw payload: %s",
                    msg.topic, e, raw,
                )
                return

        # Apply every configured filter — all must pass
        for f in self._config.get("topic_filters", []):
            if not self._apply_filter(payload, f):
                logger.debug(
                    "Filter rejected message on topic '%s': %s %s %s",
                    msg.topic, f.get("property"), f.get("comparator"), f.get("value"),
                )
                return

        event_id, camera, score = self._extract_event_info(payload)
        mode = self._config.get("frigate_snapshot_mode", "event")

        if mode == "latest_frame":
            if not camera:
                logger.warning(
                    "latest_frame mode requires a camera name but none found in message "
                    "on topic '%s'.\nPayload: %s",
                    msg.topic, json.dumps(payload, indent=2),
                )
                return
        else:
            if not event_id:
                logger.warning(
                    "Could not extract event ID from message on topic '%s'.\n"
                    "Payload: %s",
                    msg.topic, json.dumps(payload, indent=2),
                )
                return

        logger.info(
            "Processing message on topic '%s' — camera='%s' event_id=%s (score=%.3f)",
            msg.topic, camera or "unknown", event_id or "N/A", score,
        )

        image = self._frigate.get_snapshot(event_id, camera=camera, mode=mode)
        if image is None:
            return

        detections = self._recognizer.recognize(image)

        if self._snapshot_store is not None:
            self._snapshot_store.add(image, camera or "unknown", event_id, score, detections)

        if not detections:
            logger.info("No hands detected in snapshot for event %s", event_id)
            return

        self._publisher.publish(camera or "unknown", detections)

    # ------------------------------------------------------------------ #
    #  Filter helpers                                                      #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _get_nested(obj: dict, path: str):
        """Resolve a dot-notation path against a nested dict."""
        for key in path.split("."):
            if not isinstance(obj, dict):
                return None
            obj = obj.get(key)
            if obj is None:
                return None
        return obj

    @staticmethod
    def _apply_filter(payload: dict, f: dict) -> bool:
        actual     = MQTTListener._get_nested(payload, f.get("property", ""))
        comparator = f.get("comparator", "==")
        raw        = f.get("value", "")

        if actual is None:
            return False

        if comparator in (">", "<", ">=", "<="):
            try:
                a, v = float(actual), float(raw)
                if comparator == ">":  return a > v
                if comparator == "<":  return a < v
                if comparator == ">=": return a >= v
                if comparator == "<=": return a <= v
            except (ValueError, TypeError):
                return False

        actual_str = str(actual)
        raw_str    = str(raw)

        if comparator == "==":          return actual_str == raw_str
        if comparator == "!=":          return actual_str != raw_str
        if comparator == "contains":    return raw_str.lower() in actual_str.lower()
        if comparator == "not contains":return raw_str.lower() not in actual_str.lower()

        return True

    @staticmethod
    def _extract_event_info(payload: dict) -> tuple[str | None, str | None, float]:
        """Extract (event_id, camera, score) from both frigate/events and flat payloads."""
        after = payload.get("after")
        if isinstance(after, dict):
            return (
                after.get("id"),
                after.get("camera"),
                float(after.get("top_score") or after.get("score") or 0),
            )
        return (
            payload.get("id"),
            payload.get("camera"),
            float(payload.get("score") or payload.get("top_score") or 0),
        )

    # ------------------------------------------------------------------ #

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
