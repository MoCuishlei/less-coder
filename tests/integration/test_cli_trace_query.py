import json
from pathlib import Path

from clients.cli.trace_query import query_trace


def test_query_trace_summary(tmp_path: Path):
    p = tmp_path / "trace_events.jsonl"
    events = [
        {"trace_id": "tr_001", "node": "Analyze", "duration_ms": 10},
        {"trace_id": "tr_001", "node": "Plan", "duration_ms": 20},
        {"trace_id": "tr_001", "node": "Execute", "duration_ms": 30, "error_code": "PATCHLET_CONFLICT"},
        {"trace_id": "tr_002", "node": "Analyze", "duration_ms": 5},
    ]
    p.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in events), encoding="utf-8")

    res = query_trace(str(p), "tr_001")
    assert res["found"] is True
    assert res["trace_id"] == "tr_001"
    assert res["total_duration_ms"] == 60
    assert res["error_codes"] == ["PATCHLET_CONFLICT"]
    nodes = {n["node"]: n["duration_ms"] for n in res["nodes"]}
    assert nodes["Analyze"] == 10
    assert nodes["Plan"] == 20
    assert nodes["Execute"] == 30
