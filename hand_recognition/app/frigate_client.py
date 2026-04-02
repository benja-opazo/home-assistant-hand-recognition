import logging
import requests
import numpy as np
import cv2

logger = logging.getLogger(__name__)


class FrigateClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def get_snapshot(
        self,
        event_id: str,
        camera: str | None = None,
        mode: str = "event",
    ) -> np.ndarray | None:
        if mode == "latest_frame" and camera:
            url = f"{self.base_url}/api/{camera}/latest.jpg"
        else:
            url = f"{self.base_url}/api/events/{event_id}/snapshot.jpg"

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            image_array = np.frombuffer(response.content, dtype=np.uint8)
            image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            return image
        except requests.RequestException as e:
            logger.error("Failed to download snapshot (mode=%s, url=%s): %s", mode, url, e)
            return None
