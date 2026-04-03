import logging
import threading

from waitress import serve

from config import load_config
from event_processor import EventProcessor
from frigate_client import FrigateClient
from recognizer_factory import create_recognizer
from log_handler import InMemoryLogHandler
from mqtt_listener import MQTTListener
from mqtt_publisher import MQTTPublisher
from snapshot_store import SnapshotStore
from web.server import create_app

log_handler = InMemoryLogHandler()
log_handler.setLevel(logging.DEBUG)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger().addHandler(log_handler)

logger = logging.getLogger(__name__)


def main():
    config = load_config()

    snapshot_store = SnapshotStore(max_snapshots=config.get("max_snapshots", 10))
    frigate        = FrigateClient(config["frigate_url"])
    recognizer     = create_recognizer(config)

    # Listener is created first so its mqtt_client is available for the publisher.
    listener  = MQTTListener(config)
    publisher = MQTTPublisher(listener.mqtt_client, config["output_topic_template"])
    processor = EventProcessor(config, frigate, recognizer, publisher, snapshot_store)

    listener.on_event = processor.process

    threading.Thread(target=listener.start, daemon=True).start()

    flask_app = create_app(config, log_handler, snapshot_store, recognizer.available_gestures(), recognizer)

    logger.info("Web UI available on port %d", config["web_ui_port"])
    serve(flask_app, host="0.0.0.0", port=config["web_ui_port"], threads=8)
    listener.stop()
    recognizer.close()


if __name__ == "__main__":
    main()
