from dataclasses import dataclass


@dataclass(frozen=True)
class RouteDecision:
    next_node: str
    should_retry: bool
    terminal: bool
    reason: str


def decide_patchlet_route(error_code: str, retry_count: int, max_retries: int) -> RouteDecision:
    # L0-P0-06 policy:
    # - PATCHLET_APPLY_FAILED -> retry Execute (bounded)
    # - PATCHLET_CONFLICT / PATCHLET_SEARCH_MISS -> enter Repair terminal strategy
    if error_code == "PATCHLET_APPLY_FAILED":
        if retry_count < max_retries:
            return RouteDecision(
                next_node="Execute",
                should_retry=True,
                terminal=False,
                reason="transient apply failure, retry execute",
            )
        return RouteDecision(
            next_node="Repair",
            should_retry=False,
            terminal=True,
            reason="retry exhausted for apply failure",
        )

    if error_code in {"PATCHLET_CONFLICT", "PATCHLET_SEARCH_MISS"}:
        return RouteDecision(
            next_node="Repair",
            should_retry=False,
            terminal=True,
            reason="conflict/search miss requires repair terminal handling",
        )

    return RouteDecision(
        next_node="Repair",
        should_retry=False,
        terminal=False,
        reason="fallback routing for unknown patchlet error",
    )
