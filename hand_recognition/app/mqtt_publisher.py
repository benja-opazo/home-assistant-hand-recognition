import json
import logging
import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


class MQTTPublisher:
    def __init__(self, client: mqtt.Client, topic_template: str):
        self._client = client
        self._topic_template = topic_template

    def publish(self, camera: str, detections: list[dict]) -> None:
        topic   = self._topic_template.format(camera=camera)
        by_hand = {d["hand"].lower(): {"gesture": d["gesture"], "score": d["score"]} for d in detections}
        empty   = {"gesture": "unknown", "score": 0}
        payload = json.dumps({
            "camera": camera,
            "left":   by_hand.get("left",  empty),
            "right":  by_hand.get("right", empty),
        })
        result = self._client.publish(topic, payload, qos=1)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            logger.error("Failed to publish to %s: rc=%d", topic, result.rc)
        else:
            logger.info("Published to %s: %s", topic, payload)
