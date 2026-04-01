import logging
import signal
import sys
import threading

from config import load_config
from frigate_client import FrigateClient
from hand_recognizer import HandRecognizer
from mqtt_listener import MQTTListener
from mqtt_publisher import MQTTPublisher
from web.server import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    config = load_config()

    frigate = FrigateClient(config["frigate_url"])
    recognizer = HandRecognizer()
    listener = MQTTListener(config, frigate, recognizer, None)  # publisher set below

    publisher = MQTTPublisher(listener.mqtt_client, config["output_topic_template"])
    listener._publisher = publisher

    listener.start()

    flask_app = create_app(config)
    web_thread = threading.Thread(
        target=lambda: flask_app.run(
            host="0.0.0.0",
            port=config["web_ui_port"],
            use_reloader=False,
        ),
        daemon=True,
    )
    web_thread.start()
    logger.info("Web UI available on port %d", config["web_ui_port"])

    def _shutdown(sig, frame):
        logger.info("Shutting down...")
        listener.stop()
        recognizer.close()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)
    signal.pause()


if __name__ == "__main__":
    main()
