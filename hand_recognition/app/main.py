import logging
import threading

from gunicorn.app.base import BaseApplication

from config import load_config
from frigate_client import FrigateClient
from hand_recognizer import HandRecognizer
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
    frigate = FrigateClient(config["frigate_url"])
    recognizer = HandRecognizer(config)
    listener = MQTTListener(config, frigate, recognizer, None, snapshot_store)

    publisher = MQTTPublisher(listener.mqtt_client, config["output_topic_template"])
    listener._publisher = publisher

    threading.Thread(target=listener.start, daemon=True).start()

    flask_app = create_app(config, log_handler, snapshot_store)

    class _GunicornApp(BaseApplication):
        def load_config(self):
            self.cfg.set("bind",         f"0.0.0.0:{config['web_ui_port']}")
            self.cfg.set("worker_class", "gthread")
            self.cfg.set("workers",      1)
            self.cfg.set("threads",      8)
            self.cfg.set("timeout",      0)   # disable worker timeout (SSE streams are long-lived)
            self.cfg.set("loglevel",     "warning")

        def load(self):
            return flask_app

    logger.info("Web UI available on port %d", config["web_ui_port"])
    # Run gunicorn on the main thread so it can register its own signal handlers
    _GunicornApp().run()
    listener.stop()
    recognizer.close()


if __name__ == "__main__":
    main()
