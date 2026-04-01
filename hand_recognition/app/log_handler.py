import logging
import queue
import threading
from collections import deque
from datetime import datetime


class InMemoryLogHandler(logging.Handler):
    def __init__(self, maxlen: int = 2000):
        super().__init__()
        self._records: deque[dict] = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self._counter = 0
        self._listeners: list[queue.Queue] = []

    def emit(self, record: logging.LogRecord) -> None:
        entry = {
            "id": self._counter,
            "timestamp": datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S"),
            "level": record.levelname,
            "source": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            entry["message"] += "\n" + self.formatException(record.exc_info)

        with self._lock:
            self._counter += 1
            self._records.append(entry)
            for q in self._listeners:
                try:
                    q.put_nowait(entry)
                except queue.Full:
                    pass

    def get_records(self) -> list[dict]:
        with self._lock:
            return list(self._records)

    def clear(self) -> None:
        with self._lock:
            self._records.clear()

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=500)
        with self._lock:
            self._listeners.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            try:
                self._listeners.remove(q)
            except ValueError:
                pass
