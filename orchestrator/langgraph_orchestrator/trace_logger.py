import json
import os
import time
from pathlib import Path
from typing import Any


def append_trace_event(
    trace_id: str,
    node: str,
    status: str,
    duration_ms: int,
    error_code: str | None = None,
    extra: dict[str, Any] | None = None,
    events_file: str = "logs/trace_events.jsonl",
) -> None:
    event = {
        "ts_unix_ms": int(time.time() * 1000),
        "trace_id": trace_id,
        "node": node,
        "status": status,
        "duration_ms": int(duration_ms),
        "error_code": error_code,
    }
    if extra:
        event.update(extra)

    p = Path(events_file)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + os.linesep)
