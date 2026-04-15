import asyncio

from orchestrator.langgraph_orchestrator import run_normal_chain


def test_normal_chain_end_to_end():
    async def adapter_call(action: str, payload: dict, trace_id: str):
        return {
            "status": "ok",
            "trace_id": trace_id,
            "data": {"action": action, "payload": payload},
        }

    async def patch_call(payload: dict, trace_id: str):
        return {
            "status": "ok",
            "trace_id": trace_id,
            "data": {"patched": True, "target": payload["target"]},
        }

    async def checks_call(payload: dict):
        return {
            "exit_code": 0,
            "stdout_tail": "BUILD SUCCESS",
            "stderr_tail": "",
            "timed_out": False,
            "output_truncated": False,
            "echo": payload["command"],
        }

    async def run_case():
        result = await run_normal_chain(
            task="fix npe",
            trace_id="tr_chain_001",
            adapter_call=adapter_call,
            patch_call=patch_call,
            checks_call=checks_call,
        )
        assert result["status"] == "ok"
        assert result["trace_id"] == "tr_chain_001"
        assert result["states"] == ["Analyze", "Plan", "Execute", "Verify", "Done"]
        assert result["artifacts"]["checks"]["exit_code"] == 0

    asyncio.run(run_case())
