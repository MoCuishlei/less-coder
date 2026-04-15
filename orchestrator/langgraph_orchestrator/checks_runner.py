import asyncio
import os
import signal
from dataclasses import dataclass
from typing import Any


@dataclass
class ChecksRunRequest:
    cwd: str
    command: str
    args: list[str]
    timeout_ms: int
    env_allowlist: dict[str, str]
    max_output_kb: int


def _truncate_output(text: str, max_output_kb: int) -> str:
    max_bytes = max_output_kb * 1024
    data = text.encode("utf-8", errors="replace")
    if len(data) <= max_bytes:
        return text
    tail = data[-max_bytes:]
    return tail.decode("utf-8", errors="replace")


def _validate_request(req: ChecksRunRequest) -> None:
    if not req.cwd:
        raise ValueError("cwd is required")
    if not os.path.isabs(req.cwd):
        raise ValueError("cwd must be absolute path")
    if not req.command:
        raise ValueError("command is required")
    if req.timeout_ms <= 0:
        raise ValueError("timeout_ms must be > 0")
    if req.max_output_kb <= 0:
        raise ValueError("max_output_kb must be > 0")


async def _kill_process_tree(proc: asyncio.subprocess.Process) -> None:
    # Best-effort process-tree kill for timeout path.
    if os.name == "nt":
        killer = await asyncio.create_subprocess_exec(
            "taskkill",
            "/PID",
            str(proc.pid),
            "/T",
            "/F",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await killer.wait()
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except PermissionError:
            proc.kill()


async def run_checks(payload: dict[str, Any]) -> dict[str, Any]:
    req = ChecksRunRequest(
        cwd=payload["cwd"],
        command=payload["command"],
        args=list(payload.get("args", [])),
        timeout_ms=int(payload["timeout_ms"]),
        env_allowlist=dict(payload.get("env_allowlist", {})),
        max_output_kb=int(payload["max_output_kb"]),
    )
    _validate_request(req)

    proc = await asyncio.create_subprocess_exec(
        req.command,
        *req.args,
        cwd=req.cwd,
        env=req.env_allowlist,  # v0: do not inherit full env
        start_new_session=True,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    timed_out = False
    try:
        stdout_b, stderr_b = await asyncio.wait_for(
            proc.communicate(),
            timeout=req.timeout_ms / 1000.0,
        )
    except TimeoutError:
        timed_out = True
        await _kill_process_tree(proc)
        stdout_b, stderr_b = await proc.communicate()

    stdout = stdout_b.decode("utf-8", errors="replace")
    stderr = stderr_b.decode("utf-8", errors="replace")

    stdout_tail = _truncate_output(stdout, req.max_output_kb)
    stderr_tail = _truncate_output(stderr, req.max_output_kb)
    output_truncated = (len(stdout_tail) < len(stdout)) or (len(stderr_tail) < len(stderr))

    return {
        "exit_code": proc.returncode,
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
        "timed_out": timed_out,
        "output_truncated": output_truncated,
    }
