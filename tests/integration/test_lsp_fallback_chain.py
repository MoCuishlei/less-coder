import asyncio

from orchestrator.langgraph_orchestrator import run_chain_with_lsp_fallback


def test_lsp_timeout_fallback_to_static_and_done():
    calls: list[str] = []

    async def adapter_call(action: str, payload: dict, trace_id: str):
        calls.append(action)
        if action == "repo.map":
            return {"status": "ok", "trace_id": trace_id, "data": {"files": 10}}
        if action == "symbol.lookup":
            return {
                "status": "error",
                "trace_id": trace_id,
                "error": {"code": "ALSP_LSP_TIMEOUT"},
            }
        if action == "symbol.lookup.static":
            return {"status": "ok", "trace_id": trace_id, "data": {"symbol": "A#foo"}}
        return {"status": "ok", "trace_id": trace_id, "data": {}}

    async def patch_call(payload: dict, trace_id: str):
        return {"status": "ok", "trace_id": trace_id, "data": {"patched": True}}

    async def checks_call(payload: dict):
        return {
            "exit_code": 0,
            "stdout_tail": "BUILD SUCCESS",
            "stderr_tail": "",
            "timed_out": False,
            "output_truncated": False,
        }

    async def run_case():
        result = await run_chain_with_lsp_fallback(
            task="fix symbol call",
            trace_id="tr_fallback_001",
            adapter_call=adapter_call,
            patch_call=patch_call,
            checks_call=checks_call,
        )
        assert result["status"] == "ok"
        assert result["fallback_used"] is True
        assert result["states"] == ["Analyze", "Plan", "Execute", "Verify", "Done"]
        assert "symbol.lookup.static" in calls

    asyncio.run(run_case())
