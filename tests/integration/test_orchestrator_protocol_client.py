import asyncio
import json

import pytest

from orchestrator.langgraph_orchestrator import LocalProtocolClient, ProtocolClientError


async def _run_mock_server():
    seen_actions: list[str] = []

    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        req_line = await reader.readline()
        req = json.loads(req_line.decode("utf-8"))
        seen_actions.append(req["action"])
        resp = {
            "version": "v0",
            "request_id": req["request_id"],
            "trace_id": req["trace_id"],
            "status": "ok",
            "data": {"accepted": True, "action": req["action"]},
            "error": None,
            "fallback_used": False,
            "cost": {"duration_ms": 1},
        }
        writer.write((json.dumps(resp) + "\n").encode("utf-8"))
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    return server, port, seen_actions


def test_protocol_client_request_response():
    async def run_case():
        server, port, seen_actions = await _run_mock_server()
        client = LocalProtocolClient(port=port)
        try:
            resp = await client.request(
                action="symbol.lookup",
                payload={"symbol": "A#foo", "path": "."},
                trace_id="tr_test_001",
                timeout_ms=3000,
            )
            assert resp["status"] == "ok"
            assert resp["trace_id"] == "tr_test_001"
            assert resp["data"]["action"] == "symbol.lookup"
            assert seen_actions == ["system.warmup", "symbol.lookup"]
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run_case())


def test_protocol_client_requires_explicit_warmup_path():
    async def run_case():
        server, port, _ = await _run_mock_server()
        client = LocalProtocolClient(port=port)
        try:
            with pytest.raises(ProtocolClientError) as exc:
                await client.request(
                    action="symbol.lookup",
                    payload={"symbol": "A#foo"},
                    trace_id="tr_test_002",
                    timeout_ms=3000,
                )
            assert "explicit project_root/path" in str(exc.value)
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run_case())
