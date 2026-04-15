import json

from clients.cli import lesscoder
import clients.cli.task_cli as task_cli


def test_lesscoder_help_contains_server(capsys):
    try:
        lesscoder.main(["--help"])
    except SystemExit as exc:
        code = int(exc.code)
    else:
        code = 0
    assert code == 0
    captured = capsys.readouterr()
    assert "usage: lesscoder" in captured.out
    assert "warmup" in captured.out


def test_lesscoder_server_invokes_adapter(monkeypatch):
    calls = []

    class FakeCompleted:
        returncode = 0

    def fake_run(cmd, env, check):
        calls.append({"cmd": cmd, "env": env, "check": check})
        return FakeCompleted()

    monkeypatch.setattr(task_cli.subprocess, "run", fake_run)
    code = lesscoder.main(["server", "--host", "127.0.0.1", "--port", "8799"])
    assert code == 0
    assert len(calls) == 2
    build_call = calls[0]
    run_call = calls[1]
    assert build_call["cmd"][:3] == ["cargo", "build", "--manifest-path"]
    assert build_call["cmd"][3].endswith("engine\\rust\\alsp_adapter\\Cargo.toml") or build_call["cmd"][3].endswith(
        "engine/rust/alsp_adapter/Cargo.toml"
    )
    assert build_call["cmd"][-2:] == ["--bin", "alsp_adapter"]
    assert build_call["check"] is False
    assert run_call["cmd"][:3] == ["cargo", "run", "--manifest-path"]
    assert run_call["cmd"][-2:] == ["--bin", "alsp_adapter"]
    assert run_call["check"] is False
    assert run_call["env"]["ALSP_ADAPTER_ADDR"] == "127.0.0.1:8799"


def test_lesscoder_trace_command(monkeypatch, tmp_path, capsys):
    events_file = tmp_path / "trace_events.jsonl"
    events_file.write_text(
        json.dumps({"trace_id": "tr_test_1", "node": "Analyze", "duration_ms": 3}),
        encoding="utf-8",
    )
    code = task_cli.main(
        ["trace", "--trace-id", "tr_test_1", "--events-file", str(events_file)],
        prog="lesscoder",
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["status"] == "ok"
    assert payload["data"]["trace_id"] == "tr_test_1"


def test_lesscoder_warmup_skip_build(monkeypatch, capsys):
    code = task_cli.main(["warmup", "--skip-build"], prog="lesscoder")
    assert code == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["status"] == "ok"
    assert payload["build"]["skipped"] is True
