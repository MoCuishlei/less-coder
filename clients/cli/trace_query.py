import json
from pathlib import Path
from typing import Any


def query_trace(events_file: str, trace_id: str) -> dict[str, Any]:
    path = Path(events_file)
    if not path.exists():
        raise FileNotFoundError(f"events file not found: {events_file}")

    matched: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if obj.get("trace_id") == trace_id:
                matched.append(obj)

    if not matched:
        return {
            "trace_id": trace_id,
            "found": False,
            "nodes": [],
            "total_duration_ms": 0,
            "error_codes": [],
        }

    nodes: dict[str, int] = {}
    error_codes: list[str] = []
    total_duration_ms = 0
    for e in matched:
        node = str(e.get("node", "unknown"))
        duration = int(e.get("duration_ms", 0))
        nodes[node] = nodes.get(node, 0) + duration
        total_duration_ms += duration
        err = e.get("error_code")
        if err:
            error_codes.append(str(err))

    return {
        "trace_id": trace_id,
        "found": True,
        "nodes": [{"node": k, "duration_ms": v} for k, v in sorted(nodes.items())],
        "total_duration_ms": total_duration_ms,
        "error_codes": sorted(set(error_codes)),
    }
