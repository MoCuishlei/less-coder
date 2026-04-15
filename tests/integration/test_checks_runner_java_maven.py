import asyncio
import os
import shutil
import tempfile
from pathlib import Path

from orchestrator.langgraph_orchestrator import run_checks


def _minimal_windows_maven_env_allowlist() -> dict[str, str]:
    keys = ["PATH", "SystemRoot", "ComSpec", "PATHEXT", "TEMP", "TMP", "JAVA_HOME", "MAVEN_HOME"]
    out: dict[str, str] = {}
    for k in keys:
        v = os.environ.get(k)
        if v:
            out[k] = v
    return out


def test_checks_runner_executes_real_maven_on_java_fixture():
    async def run_case():
        root = Path(__file__).resolve().parents[2]
        fixture_src = root / "fixtures" / "java-sample"
        fixture_dir = Path(tempfile.mkdtemp(prefix="java_fixture_fail_"))
        shutil.copytree(fixture_src, fixture_dir, dirs_exist_ok=True)

        # Force buggy baseline in isolated copy.
        target = fixture_dir / "src" / "main" / "java" / "com" / "acme" / "NameService.java"
        original = target.read_text(encoding="utf-8")
        buggy = original.replace(
            "if (input == null || input.trim().isEmpty()) {",
            "if (input == null) {",
        )
        target.write_text(buggy, encoding="utf-8")
        mvn_cmd = "mvn.cmd" if os.name == "nt" else "mvn"

        try:
            result = await run_checks(
                {
                    "cwd": str(fixture_dir),
                    "command": mvn_cmd,
                    "args": ["test"],
                    "timeout_ms": 180000,
                    "env_allowlist": _minimal_windows_maven_env_allowlist(),
                    "max_output_kb": 1024,
                }
            )

            # Current fixture baseline intentionally has 1 failing test.
            assert result["timed_out"] is False
            assert result["exit_code"] != 0
            combined = (result["stdout_tail"] + "\n" + result["stderr_tail"]).lower()
            assert "failures" in combined or "build failure" in combined
        finally:
            if fixture_dir.exists():
                shutil.rmtree(fixture_dir, ignore_errors=True)

    asyncio.run(run_case())
