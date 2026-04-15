import asyncio
import json
import os
from pathlib import Path

from orchestrator.langgraph_orchestrator import run_checks


def _minimal_env_allowlist() -> dict[str, str]:
    keys = ["PATH", "SystemRoot", "ComSpec", "PATHEXT", "TEMP", "TMP", "JAVA_HOME", "MAVEN_HOME"]
    out: dict[str, str] = {}
    for k in keys:
        v = os.environ.get(k)
        if v:
            out[k] = v
    return out


def test_java_benchmark_set_has_three_runnable_failing_tasks():
    async def run_case():
        root = Path(__file__).resolve().parents[2]
        manifest = json.loads((root / "benchmarks" / "java_benchmark_set.json").read_text(encoding="utf-8"))
        assert manifest["language"] == "java"
        assert len(manifest["tasks"]) == 3

        mvn_cmd = "mvn.cmd" if os.name == "nt" else "mvn"
        for task in manifest["tasks"]:
            project_root = root / task["project_root"]
            result = await run_checks(
                {
                    "cwd": str(project_root),
                    "command": mvn_cmd,
                    "args": ["test"],
                    "timeout_ms": 180000,
                    "env_allowlist": _minimal_env_allowlist(),
                    "max_output_kb": 1024,
                }
            )
            assert result["timed_out"] is False
            assert result["exit_code"] != 0
            combined = (result["stdout_tail"] + "\n" + result["stderr_tail"]).lower()
            assert "failures: 1" in combined or "failures: 1," in combined or "failures" in combined

    asyncio.run(run_case())
