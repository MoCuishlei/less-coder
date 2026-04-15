import asyncio

from orchestrator.langgraph_orchestrator import run_chain_with_patch_conflict


def test_patch_conflict_enters_repair_with_error_code():
    async def adapter_call(action: str, payload: dict, trace_id: str):
        return {"status": "ok", "trace_id": trace_id, "data": {"action": action}}

    async def patch_call(payload: dict, trace_id: str):
        return {
            "status": "error",
            "trace_id": trace_id,
            "error": {"code": "PATCHLET_CONFLICT"},
        }

    async def run_case():
        result = await run_chain_with_patch_conflict(
            task="fix patch conflict",
            trace_id="tr_conflict_001",
            adapter_call=adapter_call,
            patch_call=patch_call,
        )
        assert result["status"] == "error"
        assert result["error_code"] == "PATCHLET_CONFLICT"
        assert result["states"][-1] == "Repair"

    asyncio.run(run_case())


def test_patch_search_miss_enters_repair_with_error_code():
    async def adapter_call(action: str, payload: dict, trace_id: str):
        return {"status": "ok", "trace_id": trace_id, "data": {"action": action}}

    async def patch_call(payload: dict, trace_id: str):
        return {
            "status": "error",
            "trace_id": trace_id,
            "error": {"code": "PATCHLET_SEARCH_MISS"},
        }

    async def run_case():
        result = await run_chain_with_patch_conflict(
            task="fix search miss",
            trace_id="tr_search_miss_001",
            adapter_call=adapter_call,
            patch_call=patch_call,
        )
        assert result["status"] == "error"
        assert result["error_code"] == "PATCHLET_SEARCH_MISS"
        assert result["states"][-1] == "Repair"

    asyncio.run(run_case())
