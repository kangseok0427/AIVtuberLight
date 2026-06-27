# AIVtuberLight/ipc/notifier.py
import json
import uuid
from pathlib import Path

NOTIFY_PATH = Path("/Users/lucas/AIVtuberLight/notify_queue.json")


def notify(event: str, **data):
    """가온이 → 컨트롤러 알림 전송"""
    queue = []
    if NOTIFY_PATH.exists():
        try:
            queue = json.loads(NOTIFY_PATH.read_text(encoding="utf-8"))
        except Exception:
            queue = []
    queue.append({"id": str(uuid.uuid4()), "event": event, **data})
    NOTIFY_PATH.write_text(json.dumps(queue, ensure_ascii=False), encoding="utf-8")
    print(f"[Notifier] 전송: {event} {data}")