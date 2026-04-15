import asyncio
import json
from pathlib import Path

from orchestrator.langgraph_orchestrator import run_real_chain


async def _mock_adapter_server():
    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        req_line = await reader.readline()
        req = json.loads(req_line.decode("utf-8"))
        action = req["action"]

        if action == "repo.map":
            resp = {
                "version": "v0",
                "request_id": req["request_id"],
                "trace_id": req["trace_id"],
                "status": "ok",
                "data": {"files": 1},
                "error": None,
                "fallback_used": False,
                "cost": {"duration_ms": 1},
            }
        elif action in {"symbol.lookup", "symbol.lookup.static"}:
            resp = {
                "version": "v0",
                "request_id": req["request_id"],
                "trace_id": req["trace_id"],
                "status": "ok",
                "data": {"symbol": "normalizeName", "line": 4},
                "error": None,
                "fallback_used": False,
                "cost": {"duration_ms": 1},
            }
        elif action == "patch.apply":
            resp = {
                "version": "v0",
                "request_id": req["request_id"],
                "trace_id": req["trace_id"],
                "status": "ok",
                "data": {"replacements": 1, "backup_file": "dummy.bak"},
                "error": None,
                "fallback_used": False,
                "cost": {"duration_ms": 1},
            }
        else:
            resp = {
                "version": "v0",
                "request_id": req["request_id"],
                "trace_id": req["trace_id"],
                "status": "error",
                "data": None,
                "error": {"code": "ADAPTER_ROUTE_FAILED"},
                "fallback_used": False,
                "cost": {"duration_ms": 1},
            }

        writer.write((json.dumps(resp) + "\n").encode("utf-8"))
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    return server, port


def test_run_real_chain_writes_structured_trace_events(tmp_path: Path):
    async def run_case():
        server, port = await _mock_adapter_server()
        events_file = tmp_path / "trace_events.jsonl"
        try:
            result = await run_real_chain(
                project_root=str(tmp_path),
                trace_id="tr_trace_001",
                adapter_host="127.0.0.1",
                adapter_port=port,
                patch_target=str(tmp_path / "dummy.java"),
                verify_command="python",
                verify_args=["-c", "print('ok')"],
                trace_events_file=str(events_file),
            )
            assert result["status"] == "ok"
        finally:
            server.close()
            await server.wait_closed()

        assert events_file.exists()
        events = [json.loads(line) for line in events_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        nodes = [e["node"] for e in events]
        assert nodes == ["Analyze", "Plan", "Execute", "Verify", "Done"]
        for e in events:
            assert e["trace_id"] == "tr_trace_001"
            assert isinstance(e["duration_ms"], int)
            assert "status" in e
            assert "error_code" in e

    asyncio.run(run_case())
