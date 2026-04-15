import asyncio
import json
import os

from orchestrator.langgraph_orchestrator import run_real_chain


async def _mock_adapter_server():
    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        req_line = await reader.readline()
        req = json.loads(req_line.decode("utf-8"))
        action = req["action"]
        data = {}
        status = "ok"
        error = None
        if action == "repo.map":
            data = {"files": 1}
        elif action in {"symbol.lookup", "symbol.lookup.static"}:
            data = {"symbol": "normalizeName", "line": 4}
        elif action == "patch.apply":
            data = {"replacements": 1, "backup_file": "x.patchlet.bak"}
        else:
            status = "error"
            error = {"code": "ADAPTER_ROUTE_FAILED"}

        resp = {
            "version": "v0",
            "request_id": req["request_id"],
            "trace_id": req["trace_id"],
            "status": status,
            "data": data if status == "ok" else None,
            "error": error,
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


def test_run_real_chain_uses_protocol_client_flow():
    async def run_case():
        server, port = await _mock_adapter_server()
        try:
            result = await run_real_chain(
                project_root=os.getcwd(),
                trace_id="tr_real_001",
                adapter_port=port,
                patch_target="dummy.txt",
                verify_command="python",
                verify_args=["-c", "print('ok')"],
            )
            assert result["status"] == "ok"
            assert result["states"] == ["Analyze", "Plan", "Execute", "Verify", "Done"]
            assert result["artifacts"]["patch"]["status"] == "ok"
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run_case())
