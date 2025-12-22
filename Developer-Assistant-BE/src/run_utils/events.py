import asyncio
import json
import time
from typing import Any, Dict, List


class RunEventHub:
    def __init__(self):
        self.queues: Dict[str, List[asyncio.Queue[str]]] = {}
        self.history: Dict[str, List[str]] = {}
        self.HISTORY_LIMIT = 500

    def _ensure(self, run_id: str):
        self.queues.setdefault(run_id, [])
        self.history.setdefault(run_id, [])

    async def subscribe(self, run_id: str) -> asyncio.Queue[str]:
        self._ensure(run_id)
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=2048)
        self.queues[run_id].append(q)
        for line in self.history[run_id][-100:]:
            await q.put(line)
        return q

    def unsubscribe(self, run_id: str, q: asyncio.Queue[str]):
        arr = self.queues.get(run_id, [])
        if q in arr:
            arr.remove(q)
            
    def clear(self, run_id: str):
        if run_id in self.history:
            self.history[run_id] = []

    async def emit(self, run_id: str, event: Dict[str, Any]):
        self._ensure(run_id)
        payload = {
            "t": event.get("t", "log"),
            "ts": event.get("ts", int(time.time() * 1000)),
            **event,
        }
        line = f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        hist = self.history[run_id]
        hist.append(line)
        if len(hist) > self.HISTORY_LIMIT:
            del hist[: len(hist) - self.HISTORY_LIMIT]
        for q in list(self.queues[run_id]):
            try:
                q.put_nowait(line)
            except asyncio.QueueFull:
                self.unsubscribe(run_id, q)


hub = RunEventHub()
