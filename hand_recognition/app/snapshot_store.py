import json
import logging
import os
import threading
import uuid
from collections import deque
from datetime import datetime

import cv2
import numpy as np

logger = logging.getLogger(__name__)

SNAPSHOTS_DIR = "/data/snapshots"
METADATA_FILE = os.path.join(SNAPSHOTS_DIR, "metadata.json")


class SnapshotStore:
    def __init__(self, max_snapshots: int = 10):
        self._max = max_snapshots
        self._snapshots: deque[dict] = deque()
        self._lock = threading.Lock()
        os.makedirs(SNAPSHOTS_DIR, exist_ok=True)
        self._load()

    # ------------------------------------------------------------------ #

    def add(
        self,
        image: np.ndarray,
        camera: str,
        event_id: str | None,
        frigate_score: float,
        detections: list[dict],
    ) -> dict:
        snapshot_id = str(uuid.uuid4())
        image_path = os.path.join(SNAPSHOTS_DIR, f"{snapshot_id}.jpg")
        cv2.imwrite(image_path, image)

        entry = {
            "id": snapshot_id,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "camera": camera,
            "event_id": event_id or "",
            "frigate_score": round(frigate_score, 3),
            "detections": detections,
            "image_path": image_path,
        }

        with self._lock:
            # Evict oldest entries until we're within the limit
            while len(self._snapshots) >= self._max:
                oldest = self._snapshots.popleft()
                self._remove_file(oldest["image_path"])
            self._snapshots.append(entry)
            self._persist()

        return entry

    def get_all(self) -> list[dict]:
        with self._lock:
            return [self._public(s) for s in reversed(list(self._snapshots))]

    def get_by_id(self, snapshot_id: str) -> dict | None:
        with self._lock:
            for s in self._snapshots:
                if s["id"] == snapshot_id:
                    return s
        return None

    def delete(self, snapshot_id: str) -> bool:
        with self._lock:
            for s in list(self._snapshots):
                if s["id"] == snapshot_id:
                    self._snapshots.remove(s)
                    self._remove_file(s["image_path"])
                    self._persist()
                    return True
        return False

    def clear(self) -> None:
        with self._lock:
            for s in list(self._snapshots):
                self._remove_file(s["image_path"])
            self._snapshots.clear()
            self._persist()

    def update_detections(self, snapshot_id: str, detections: list[dict]) -> bool:
        with self._lock:
            for s in self._snapshots:
                if s["id"] == snapshot_id:
                    s["detections"] = detections
                    self._persist()
                    return True
        return False

    def update_max(self, new_max: int) -> None:
        with self._lock:
            self._max = new_max
            while len(self._snapshots) > new_max:
                oldest = self._snapshots.popleft()
                self._remove_file(oldest["image_path"])
            self._persist()

    # ------------------------------------------------------------------ #

    def _persist(self) -> None:
        try:
            with open(METADATA_FILE, "w") as f:
                json.dump(list(self._snapshots), f)
        except OSError as e:
            logger.error("Failed to persist snapshot metadata: %s", e)

    def _load(self) -> None:
        if not os.path.exists(METADATA_FILE):
            return
        try:
            with open(METADATA_FILE) as f:
                entries = json.load(f)
            for entry in entries:
                if os.path.exists(entry.get("image_path", "")):
                    self._snapshots.append(entry)
            # Trim to current max in case max was reduced since last run
            while len(self._snapshots) > self._max:
                self._snapshots.popleft()
            logger.info("Loaded %d snapshots from disk", len(self._snapshots))
        except (OSError, json.JSONDecodeError) as e:
            logger.error("Failed to load snapshot metadata: %s", e)

    @staticmethod
    def _remove_file(path: str) -> None:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except OSError as e:
            logger.warning("Could not delete snapshot file %s: %s", path, e)

    @staticmethod
    def _public(s: dict) -> dict:
        """Strip internal fields before returning to API callers."""
        return {k: v for k, v in s.items() if k != "image_path"}
