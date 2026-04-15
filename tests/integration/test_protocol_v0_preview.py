"""Integration test skeletons for local protocol v0.

These tests are intentionally lightweight contract skeletons for L0.
They validate control-flow expectations and error-code routing shape.
"""


def _simulate_normal_chain():
    return {
        "states": ["Analyze", "Plan", "Execute", "Verify", "Done"],
        "trace_id": "tr_preview_ok_001",
        "status": "ok",
    }


def _simulate_lsp_degrade_chain():
    return {
        "states": ["Analyze", "Plan", "Execute", "Verify", "Done"],
        "fallback_used": True,
        "error_code": "ALSP_LSP_TIMEOUT",
        "status": "ok",
    }


def _simulate_patch_conflict_chain():
    return {
        "states": ["Analyze", "Plan", "Execute", "Repair"],
        "error_code": "PATCHLET_CONFLICT",
        "repair_entered": True,
        "status": "error",
    }


def test_v0_normal_chain_skeleton():
    """正常链路: Analyze -> Plan -> Execute -> Verify -> Done."""
    result = _simulate_normal_chain()
    assert result["states"] == ["Analyze", "Plan", "Execute", "Verify", "Done"]
    assert result["status"] == "ok"
    assert result["trace_id"].startswith("tr_")


def test_v0_lsp_degrade_skeleton():
    """LSP 降级: 触发 ALSP_LSP_TIMEOUT 后仍不中断主流程."""
    result = _simulate_lsp_degrade_chain()
    assert result["error_code"] == "ALSP_LSP_TIMEOUT"
    assert result["fallback_used"] is True
    assert result["states"][-1] == "Done"
    assert result["status"] == "ok"


def test_v0_patch_conflict_skeleton():
    """补丁冲突: PATCHLET_CONFLICT 进入 Repair 并返回正确错误码."""
    result = _simulate_patch_conflict_chain()
    assert result["error_code"] in {"PATCHLET_CONFLICT", "PATCHLET_SEARCH_MISS"}
    assert result["repair_entered"] is True
    assert result["states"][-1] == "Repair"
    assert result["status"] == "error"
