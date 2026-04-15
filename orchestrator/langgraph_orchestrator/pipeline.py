from dataclasses import dataclass, field
import os
import time
from typing import Any, Awaitable, Callable

from .error_routing import decide_patchlet_route
from .checks_runner import run_checks
from .protocol_client import LocalProtocolClient, ProtocolClientError
from .trace_logger import append_trace_event


AdapterCall = Callable[[str, dict[str, Any], str], Awaitable[dict[str, Any]]]
PatchCall = Callable[[dict[str, Any], str], Awaitable[dict[str, Any]]]
ChecksCall = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass
class RunContext:
    trace_id: str
    task: str
    states: list[str] = field(default_factory=list)
    artifacts: dict[str, Any] = field(default_factory=dict)


async def run_normal_chain(
    task: str,
    trace_id: str,
    adapter_call: AdapterCall,
    patch_call: PatchCall,
    checks_call: ChecksCall,
) -> dict[str, Any]:
    ctx = RunContext(trace_id=trace_id, task=task)

    ctx.states.append("Analyze")
    repo_map = await adapter_call("repo.map", {"task": task}, trace_id)
    symbol = await adapter_call("symbol.lookup", {"task": task}, trace_id)
    ctx.artifacts["repo_map"] = repo_map
    ctx.artifacts["symbol"] = symbol

    ctx.states.append("Plan")
    plan = {
        "target": "src/main/java/com/acme/A.java",
        "search_replace_blocks": [{"search": "old", "replace": "new"}],
        "check_profile": {"command": "mvn", "args": ["test"]},
    }
    ctx.artifacts["plan"] = plan

    ctx.states.append("Execute")
    patch_result = await patch_call(
        {
            "target": plan["target"],
            "search_replace_blocks": plan["search_replace_blocks"],
        },
        trace_id,
    )
    ctx.artifacts["patch"] = patch_result

    ctx.states.append("Verify")
    checks_result = await checks_call(
        {
            "cwd": ".",
            "command": plan["check_profile"]["command"],
            "args": plan["check_profile"]["args"],
            "timeout_ms": 120000,
            "env_allowlist": {},
            "max_output_kb": 512,
        }
    )
    ctx.artifacts["checks"] = checks_result

    if checks_result.get("exit_code") == 0 and checks_result.get("timed_out") is False:
        ctx.states.append("Done")
        return {
            "status": "ok",
            "trace_id": trace_id,
            "states": ctx.states,
            "artifacts": ctx.artifacts,
        }

    return {
        "status": "error",
        "trace_id": trace_id,
        "states": ctx.states,
        "error_code": "ORCH_NODE_FAILED",
        "artifacts": ctx.artifacts,
    }


async def run_chain_with_lsp_fallback(
    task: str,
    trace_id: str,
    adapter_call: AdapterCall,
    patch_call: PatchCall,
    checks_call: ChecksCall,
) -> dict[str, Any]:
    ctx = RunContext(trace_id=trace_id, task=task)

    ctx.states.append("Analyze")
    repo_map = await adapter_call("repo.map", {"task": task}, trace_id)
    symbol = await adapter_call("symbol.lookup", {"task": task}, trace_id)

    fallback_used = False
    if symbol.get("status") == "error" and symbol.get("error", {}).get("code") == "ALSP_LSP_TIMEOUT":
        symbol = await adapter_call("symbol.lookup.static", {"task": task}, trace_id)
        fallback_used = True

    ctx.artifacts["repo_map"] = repo_map
    ctx.artifacts["symbol"] = symbol
    ctx.artifacts["fallback_used"] = fallback_used

    ctx.states.append("Plan")
    plan = {
        "target": "src/main/java/com/acme/A.java",
        "search_replace_blocks": [{"search": "old", "replace": "new"}],
        "check_profile": {"command": "mvn", "args": ["test"]},
    }
    ctx.artifacts["plan"] = plan

    ctx.states.append("Execute")
    patch_result = await patch_call(
        {
            "target": plan["target"],
            "search_replace_blocks": plan["search_replace_blocks"],
        },
        trace_id,
    )
    ctx.artifacts["patch"] = patch_result

    ctx.states.append("Verify")
    checks_result = await checks_call(
        {
            "cwd": ".",
            "command": plan["check_profile"]["command"],
            "args": plan["check_profile"]["args"],
            "timeout_ms": 120000,
            "env_allowlist": {},
            "max_output_kb": 512,
        }
    )
    ctx.artifacts["checks"] = checks_result

    if checks_result.get("exit_code") == 0 and checks_result.get("timed_out") is False:
        ctx.states.append("Done")
        return {
            "status": "ok",
            "trace_id": trace_id,
            "states": ctx.states,
            "fallback_used": fallback_used,
            "artifacts": ctx.artifacts,
        }

    return {
        "status": "error",
        "trace_id": trace_id,
        "states": ctx.states,
        "fallback_used": fallback_used,
        "error_code": "ORCH_NODE_FAILED",
        "artifacts": ctx.artifacts,
    }


async def run_chain_with_patch_conflict(
    task: str,
    trace_id: str,
    adapter_call: AdapterCall,
    patch_call: PatchCall,
    max_retries: int = 2,
) -> dict[str, Any]:
    ctx = RunContext(trace_id=trace_id, task=task)

    ctx.states.append("Analyze")
    repo_map = await adapter_call("repo.map", {"task": task}, trace_id)
    symbol = await adapter_call("symbol.lookup", {"task": task}, trace_id)
    ctx.artifacts["repo_map"] = repo_map
    ctx.artifacts["symbol"] = symbol

    ctx.states.append("Plan")
    plan = {
        "target": "src/main/java/com/acme/A.java",
        "search_replace_blocks": [{"search": "old", "replace": "new"}],
    }
    ctx.artifacts["plan"] = plan

    retry_count = 0
    while True:
        ctx.states.append("Execute")
        patch_result = await patch_call(
            {"target": plan["target"], "search_replace_blocks": plan["search_replace_blocks"]},
            trace_id,
        )
        ctx.artifacts["patch"] = patch_result

        if patch_result.get("status") == "ok":
            ctx.states.append("Done")
            return {
                "status": "ok",
                "trace_id": trace_id,
                "states": ctx.states,
                "artifacts": ctx.artifacts,
            }

        error_code = patch_result.get("error", {}).get("code", "PATCHLET_UNKNOWN")
        decision = decide_patchlet_route(error_code, retry_count=retry_count, max_retries=max_retries)
        ctx.artifacts["route_decision"] = {
            "next_node": decision.next_node,
            "should_retry": decision.should_retry,
            "terminal": decision.terminal,
            "reason": decision.reason,
        }

        if decision.next_node == "Execute" and decision.should_retry:
            retry_count += 1
            continue

        ctx.states.append("Repair")
        return {
            "status": "error",
            "trace_id": trace_id,
            "states": ctx.states,
            "error_code": error_code,
            "artifacts": ctx.artifacts,
        }


async def run_real_chain(
    project_root: str,
    trace_id: str,
    task: str = "fix java bug",
    adapter_host: str = "127.0.0.1",
    adapter_port: int = 8787,
    patch_target: str = "fixtures/java-sample/src/main/java/com/acme/NameService.java",
    search: str = "if (input == null) {",
    replace: str = "if (input == null || input.trim().isEmpty()) {",
    verify_command: str = "mvn",
    verify_args: list[str] | None = None,
    force_lsp_timeout: bool = False,
    force_patch_conflict: bool = False,
    trace_events_file: str = "logs/trace_events.jsonl",
) -> dict[str, Any]:
    client = LocalProtocolClient(host=adapter_host, port=adapter_port)
    ctx = RunContext(trace_id=trace_id, task=task)

    try:
        t0 = time.perf_counter()
        ctx.states.append("Analyze")
        repo_map = await client.request("repo.map", {"path": project_root}, trace_id)
        symbol = await client.request(
            "symbol.lookup",
            {
                "path": project_root,
                "symbol": "normalizeName",
                "force_lsp_timeout": force_lsp_timeout,
            },
            trace_id,
        )
        fallback_used = False
        if symbol.get("status") == "error" and symbol.get("error", {}).get("code") == "ALSP_LSP_TIMEOUT":
            symbol = await client.request(
                "symbol.lookup.static",
                {"path": project_root, "symbol": "normalizeName"},
                trace_id,
            )
            fallback_used = True
        ctx.artifacts["repo_map"] = repo_map
        ctx.artifacts["symbol"] = symbol
        ctx.artifacts["fallback_used"] = fallback_used
        append_trace_event(
            trace_id=trace_id,
            node="Analyze",
            status="ok",
            duration_ms=int((time.perf_counter() - t0) * 1000),
            extra={"fallback_used": fallback_used},
            events_file=trace_events_file,
        )

        t1 = time.perf_counter()
        ctx.states.append("Plan")
        if verify_args is None:
            verify_args = ["test"]
        ctx.artifacts["plan"] = {"target": patch_target, "search": search, "replace": replace}
        append_trace_event(
            trace_id=trace_id,
            node="Plan",
            status="ok",
            duration_ms=int((time.perf_counter() - t1) * 1000),
            events_file=trace_events_file,
        )

        t2 = time.perf_counter()
        ctx.states.append("Execute")
        patch_resp = await client.request(
            "patch.apply",
            {
                "target": patch_target,
                "search_replace_blocks": [{"search": search, "replace": replace}],
                "force_patch_conflict": force_patch_conflict,
            },
            trace_id,
        )
        ctx.artifacts["patch"] = patch_resp
        if patch_resp.get("status") != "ok":
            code = patch_resp.get("error", {}).get("code", "ORCH_NODE_FAILED")
            append_trace_event(
                trace_id=trace_id,
                node="Execute",
                status="error",
                duration_ms=int((time.perf_counter() - t2) * 1000),
                error_code=code,
                events_file=trace_events_file,
            )
            ctx.states.append("Repair")
            append_trace_event(
                trace_id=trace_id,
                node="Repair",
                status="error",
                duration_ms=0,
                error_code=code,
                events_file=trace_events_file,
            )
            return {
                "status": "error",
                "trace_id": trace_id,
                "states": ctx.states,
                "error_code": code,
                "artifacts": ctx.artifacts,
            }
        append_trace_event(
            trace_id=trace_id,
            node="Execute",
            status="ok",
            duration_ms=int((time.perf_counter() - t2) * 1000),
            events_file=trace_events_file,
        )

        t3 = time.perf_counter()
        ctx.states.append("Verify")
        env_allowlist = _default_shell_env_allowlist()
        checks = await run_checks(
            {
                "cwd": project_root,
                "command": verify_command,
                "args": verify_args,
                "timeout_ms": 120000,
                "env_allowlist": env_allowlist,
                "max_output_kb": 512,
            }
        )
        ctx.artifacts["checks"] = checks
        verify_status = "ok" if checks.get("exit_code") == 0 and checks.get("timed_out") is False else "error"
        append_trace_event(
            trace_id=trace_id,
            node="Verify",
            status=verify_status,
            duration_ms=int((time.perf_counter() - t3) * 1000),
            error_code=None if verify_status == "ok" else "ORCH_NODE_FAILED",
            events_file=trace_events_file,
        )

        if checks.get("exit_code") == 0 and checks.get("timed_out") is False:
            ctx.states.append("Done")
            append_trace_event(
                trace_id=trace_id,
                node="Done",
                status="ok",
                duration_ms=0,
                events_file=trace_events_file,
            )
            return {
                "status": "ok",
                "trace_id": trace_id,
                "states": ctx.states,
                "fallback_used": fallback_used,
                "artifacts": ctx.artifacts,
            }

        ctx.states.append("Repair")
        append_trace_event(
            trace_id=trace_id,
            node="Repair",
            status="error",
            duration_ms=0,
            error_code="ORCH_NODE_FAILED",
            events_file=trace_events_file,
        )
        return {
            "status": "error",
            "trace_id": trace_id,
            "states": ctx.states,
            "fallback_used": fallback_used,
            "error_code": "ORCH_NODE_FAILED",
            "artifacts": ctx.artifacts,
        }
    except ProtocolClientError as exc:
        append_trace_event(
            trace_id=trace_id,
            node="Analyze",
            status="error",
            duration_ms=0,
            error_code="COMMON_TIMEOUT",
            extra={"message": str(exc)},
            events_file=trace_events_file,
        )
        return {
            "status": "error",
            "trace_id": trace_id,
            "states": ctx.states if ctx.states else ["Analyze"],
            "error_code": "COMMON_TIMEOUT",
            "artifacts": {"message": str(exc)},
        }


def _default_shell_env_allowlist() -> dict[str, str]:
    keys = [
        "PATH",
        "SystemRoot",
        "ComSpec",
        "PATHEXT",
        "TEMP",
        "TMP",
        "JAVA_HOME",
        "MAVEN_HOME",
    ]
    out: dict[str, str] = {}
    for k in keys:
        v = os.environ.get(k)
        if v:
            out[k] = v
    return out
