import json
import sys

import clients.cli.task_cli as task_cli


def test_task_run_command_outputs_structured_result(monkeypatch, capsys):
    async def fake_run_real_chain(**kwargs):
        return {
            "status": "ok",
            "trace_id": kwargs["trace_id"],
            "states": ["Analyze", "Plan", "Execute", "Verify", "Done"],
            "artifacts": {},
        }

    monkeypatch.setattr(task_cli, "run_real_chain", fake_run_real_chain)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "task",
            "run",
            "--project-root",
            "fixtures/java-sample",
            "--trace-id",
            "tr_cli_001",
            "--verify-command",
            "python",
            "--verify-args=-c,print('ok')",
            "--patch-target",
            "fixtures/java-sample/src/main/java/com/acme/NameService.java",
        ],
    )

    code = task_cli.main()
    assert code == 0

    out = capsys.readouterr().out.strip()
    payload = json.loads(out)
    assert payload["status"] == "ok"
    assert payload["data"]["status"] == "ok"
    assert payload["data"]["trace_id"] == "tr_cli_001"
