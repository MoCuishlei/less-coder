from orchestrator.langgraph_orchestrator import decide_patchlet_route


def test_apply_failed_routes_to_retry_execute():
    decision = decide_patchlet_route(
        error_code="PATCHLET_APPLY_FAILED",
        retry_count=0,
        max_retries=2,
    )
    assert decision.next_node == "Execute"
    assert decision.should_retry is True
    assert decision.terminal is False


def test_apply_failed_exhausted_routes_terminal_repair():
    decision = decide_patchlet_route(
        error_code="PATCHLET_APPLY_FAILED",
        retry_count=2,
        max_retries=2,
    )
    assert decision.next_node == "Repair"
    assert decision.should_retry is False
    assert decision.terminal is True


def test_conflict_routes_terminal_repair():
    decision = decide_patchlet_route(
        error_code="PATCHLET_CONFLICT",
        retry_count=0,
        max_retries=2,
    )
    assert decision.next_node == "Repair"
    assert decision.should_retry is False
    assert decision.terminal is True
