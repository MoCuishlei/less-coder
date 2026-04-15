import asyncio
import os

from orchestrator.langgraph_orchestrator import run_checks


def test_checks_runner_success_fields():
    async def run_case():
        payload = {
            "cwd": os.getcwd(),
            "command": "python",
            "args": ["-c", "print('ok')"],
            "timeout_ms": 3000,
            "env_allowlist": {},
            "max_output_kb": 32,
        }
        result = await run_checks(payload)
        assert "exit_code" in result
        assert "stdout_tail" in result
        assert "stderr_tail" in result
        assert "timed_out" in result
        assert "output_truncated" in result
        assert result["timed_out"] is False
        assert "ok" in result["stdout_tail"]

    asyncio.run(run_case())


def test_checks_runner_timeout():
    async def run_case():
        payload = {
            "cwd": os.getcwd(),
            "command": "python",
            "args": ["-c", "import time; time.sleep(1.5)"],
            "timeout_ms": 100,
            "env_allowlist": {},
            "max_output_kb": 32,
        }
        result = await run_checks(payload)
        assert result["timed_out"] is True

    asyncio.run(run_case())


def test_checks_runner_env_allowlist_only():
    async def run_case():
        payload = {
            "cwd": os.getcwd(),
            "command": "python",
            "args": ["-c", "import os; print(os.getenv('KEEP_ME','')); print(os.getenv('SHOULD_NOT_EXIST',''))"],
            "timeout_ms": 3000,
            "env_allowlist": {"KEEP_ME": "yes"},
            "max_output_kb": 32,
        }
        result = await run_checks(payload)
        assert result["timed_out"] is False
        assert "yes" in result["stdout_tail"]
        assert "SHOULD_NOT_EXIST" not in result["stdout_tail"]

    asyncio.run(run_case())


def test_checks_runner_output_truncation():
    async def run_case():
        payload = {
            "cwd": os.getcwd(),
            "command": "python",
            "args": ["-c", "print('X'*6000)"],
            "timeout_ms": 3000,
            "env_allowlist": {},
            "max_output_kb": 1,
        }
        result = await run_checks(payload)
        assert result["output_truncated"] is True
        assert len(result["stdout_tail"].encode("utf-8")) <= 1024

    asyncio.run(run_case())
