import json
import os
from pathlib import Path
import urllib.error

from clients.cli import lesscoder
import clients.cli.task_cli as task_cli


def _repo_manifest_path() -> str:
    return str((Path(task_cli.__file__).resolve().parents[2] / "engine" / "rust" / "alsp_adapter" / "Cargo.toml"))


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


def test_lesscoder_server_invokes_adapter(monkeypatch, capsys):
    calls = []

    class FakeCompleted:
        returncode = 0

    def fake_run(cmd, env, check):
        calls.append({"cmd": cmd, "env": env, "check": check})
        return FakeCompleted()

    monkeypatch.setattr(task_cli.subprocess, "run", fake_run)
    code = lesscoder.main(
        ["server", "--host", "127.0.0.1", "--port", "8799", "--manifest-path", _repo_manifest_path()]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert '"mcpServers"' in out
    assert "/health" in out
    assert "/methods" in out
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
    code = task_cli.main(
        ["warmup", "--manifest-path", _repo_manifest_path(), "--skip-build"],
        prog="lesscoder",
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["status"] == "ok"
    assert payload["build"]["skipped"] is True


def test_lesscoder_server_supports_project_root_from_random_cwd(monkeypatch, tmp_path):
    calls = []

    class FakeCompleted:
        returncode = 0

    def fake_run(cmd, env, check):
        calls.append({"cmd": cmd, "env": env, "check": check})
        return FakeCompleted()

    monkeypatch.setattr(task_cli.subprocess, "run", fake_run)
    monkeypatch.chdir(tmp_path)
    repo_root = str(Path(task_cli.__file__).resolve().parents[2])
    code = lesscoder.main(["server", "--host", "127.0.0.1", "--port", "8801", "--project-root", repo_root])
    assert code == 0
    assert len(calls) == 2
    assert calls[1]["env"]["ALSP_ADAPTER_ADDR"] == "127.0.0.1:8801"


def test_warmup_error_contains_tried_paths_and_next_action(monkeypatch, capsys):
    monkeypatch.delenv("LESSCODER_HOME", raising=False)
    monkeypatch.setattr(task_cli, "_find_manifest_from", lambda _start: (None, ["C:/missing/a", "C:/missing/b"]))
    code = task_cli.main(["warmup", "--project-root", "C:/missing-root", "--skip-build"], prog="lesscoder")
    assert code == 2
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["status"] == "error"
    assert payload["error_code"] == "COMMON_PRECONDITION_REQUIRED"
    assert payload["checks"]["tried_paths"] == ["C:/missing/a", "C:/missing/b"]
    assert "next_action" in payload


def test_server_can_start_without_explicit_project_path(monkeypatch):
    calls = []

    class FakeCompleted:
        returncode = 0

    def fake_run(cmd, env, check):
        calls.append({"cmd": cmd, "env": env, "check": check})
        return FakeCompleted()

    monkeypatch.setattr(task_cli.subprocess, "run", fake_run)
    code = lesscoder.main(["server", "--host", "127.0.0.1", "--port", "8809"])
    assert code == 0
    assert len(calls) == 2
    assert calls[1]["env"]["ALSP_ADAPTER_ADDR"] == "127.0.0.1:8809"


def test_server_binary_mode_without_manifest(monkeypatch):
    calls = []

    class FakeCompleted:
        returncode = 0

    def fake_run(cmd, env, check):
        calls.append({"cmd": cmd, "env": env, "check": check})
        return FakeCompleted()

    monkeypatch.setattr(task_cli, "_resolve_manifest_path", lambda *_args, **_kwargs: (None, []))
    monkeypatch.setattr(
        task_cli,
        "_resolve_adapter_binary",
        lambda: ("C:/mock/bin/alsp_adapter.exe", {"source": "cache", "tried": ["C:/mock/bin/alsp_adapter.exe"]}),
    )
    monkeypatch.setattr(task_cli.subprocess, "run", fake_run)
    code = lesscoder.main(["server", "--host", "127.0.0.1", "--port", "8812"])
    assert code == 0
    assert len(calls) == 1
    assert calls[0]["cmd"] == ["C:/mock/bin/alsp_adapter.exe"]


def test_server_binary_mode_missing_adapter(monkeypatch, capsys):
    monkeypatch.setattr(task_cli, "_resolve_manifest_path", lambda *_args, **_kwargs: (None, []))
    monkeypatch.setattr(
        task_cli,
        "_resolve_adapter_binary",
        lambda: (None, {"source": "none", "tried": ["C:/missing/alsp_adapter.exe"]}),
    )
    code = lesscoder.main(["server", "--host", "127.0.0.1", "--port", "8813"])
    assert code == 2
    lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    payload = json.loads(lines[-1])
    assert payload["status"] == "error"
    assert payload["error_code"] == "COMMON_PRECONDITION_REQUIRED"
    assert payload["details"]["adapter_resolution"]["source"] == "none"


def test_warmup_requires_explicit_path_args(capsys):
    code = task_cli.main(["warmup", "--skip-build"], prog="lesscoder")
    assert code == 2
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["status"] == "error"
    assert payload["error_code"] == "COMMON_PRECONDITION_REQUIRED"


def test_server_port_in_use_returns_suggested_port(monkeypatch, capsys):
    monkeypatch.setattr(task_cli, "_is_port_available", lambda _host, _port: False)
    monkeypatch.setattr(task_cli, "_suggest_available_port", lambda _host, _port: 8811)
    code = lesscoder.main(
        ["server", "--host", "127.0.0.1", "--port", "8810", "--manifest-path", _repo_manifest_path()]
    )
    assert code == 2
    lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    payload = json.loads(lines[-1])
    assert payload["status"] == "error"
    assert payload["error_code"] == "COMMON_PORT_IN_USE"
    assert payload["details"]["suggested_port"] == 8811


def test_release_dry_run_success_with_skip_tests(monkeypatch, capsys):
    monkeypatch.setattr(
        task_cli,
        "_check_release_toolchain",
        lambda skip_tests: {
            "status": "ok",
            "required": {"python": "python", "cargo": "cargo", "npm": "npm", "build_module": "python -m build"},
            "missing": [],
        },
    )
    monkeypatch.setattr(
        task_cli,
        "_validate_release_versions",
        lambda _root, _tag: {"status": "ok", "versions": {"python": "0.1.0", "npm": "0.1.0", "tag": None}},
    )
    steps = []

    def fake_run_step(name, command, cwd):
        steps.append(name)
        return {"name": name, "status": "ok", "exit_code": 0, "command": command}

    monkeypatch.setattr(task_cli, "_run_step", fake_run_step)
    code = task_cli.main(
        ["release-dry-run", "--project-root", str(Path(task_cli.__file__).resolve().parents[2]), "--skip-tests"],
        prog="lesscoder",
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["status"] == "ok"
    assert steps == ["python_build", "npm_pack", "cargo_release_build"]


def test_release_dry_run_blocks_on_version_mismatch(monkeypatch, capsys):
    monkeypatch.setattr(
        task_cli,
        "_check_release_toolchain",
        lambda skip_tests: {
            "status": "ok",
            "required": {"python": "python", "cargo": "cargo", "npm": "npm", "build_module": "python -m build"},
            "missing": [],
        },
    )
    monkeypatch.setattr(
        task_cli,
        "_validate_release_versions",
        lambda _root, _tag: {
            "status": "error",
            "error_code": "RELEASE_VERSION_MISMATCH",
            "message": "python and npm versions are not aligned",
            "versions": {"python": "0.1.0", "npm": "0.2.0"},
        },
    )
    code = task_cli.main(
        ["release-dry-run", "--project-root", str(Path(task_cli.__file__).resolve().parents[2])],
        prog="lesscoder",
    )
    assert code == 2
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["status"] == "error"
    assert payload["error_code"] == "RELEASE_VERSION_MISMATCH"


def test_release_dry_run_blocks_on_missing_toolchain(monkeypatch, capsys):
    monkeypatch.setattr(
        task_cli,
        "_validate_release_versions",
        lambda _root, _tag: {"status": "ok", "versions": {"python": "0.1.0", "npm": "0.1.0", "tag": None}},
    )
    monkeypatch.setattr(
        task_cli,
        "_check_release_toolchain",
        lambda skip_tests: {
            "status": "error",
            "required": {"python": "python", "cargo": None, "npm": None, "build_module": "python -m build"},
            "missing": ["cargo", "npm"],
        },
    )
    code = task_cli.main(
        ["release-dry-run", "--project-root", str(Path(task_cli.__file__).resolve().parents[2]), "--skip-tests"],
        prog="lesscoder",
    )
    assert code == 2
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["status"] == "error"
    assert payload["error_code"] == "COMMON_PRECONDITION_REQUIRED"
    assert payload["toolchain"]["missing"] == ["cargo", "npm"]


def test_select_release_asset_windows_prefers_exe(monkeypatch):
    monkeypatch.setattr(task_cli, "_platform_tag", lambda: "windows")
    assets = [
        {"name": "alsp-adapter-linux", "browser_download_url": "https://example/linux"},
        {"name": "alsp_adapter.exe", "browser_download_url": "https://example/win"},
    ]
    selected = task_cli._select_release_asset(assets)
    assert selected is not None
    assert selected["name"] == "alsp_adapter.exe"


def test_select_release_asset_windows_rejects_non_exe(monkeypatch):
    monkeypatch.setattr(task_cli, "_platform_tag", lambda: "windows")
    assets = [
        {"name": "alsp-adapter-windows", "browser_download_url": "https://example/win-no-exe"},
        {"name": "alsp-adapter-linux", "browser_download_url": "https://example/linux"},
    ]
    selected = task_cli._select_release_asset(assets)
    assert selected is None


def test_lookup_asset_sha256_from_manifest():
    manifest = {
        "assets": [
            {"name": "alsp_adapter_windows_x86_64.exe", "sha256": "abc123"},
            {"name": "alsp_adapter_linux_x86_64", "sha256": "def456"},
        ]
    }
    assert (
        task_cli._lookup_asset_sha256(manifest, "alsp_adapter_windows_x86_64.exe")
        == "abc123"
    )
    assert task_cli._lookup_asset_sha256(manifest, "missing") is None


def test_normalize_release_repo_accepts_git_and_http_forms():
    assert (
        task_cli._normalize_release_repo("git@github.com:civilization-os/less-coder.git")
        == "civilization-os/less-coder"
    )
    assert (
        task_cli._normalize_release_repo("https://github.com/civilization-os/less-coder")
        == "civilization-os/less-coder"
    )


def test_download_adapter_falls_back_to_predictable_asset(monkeypatch, tmp_path):
    target = tmp_path / "alsp_adapter.exe"

    class _FakeResp:
        def __init__(self, payload: bytes):
            self._payload = payload

        def read(self):
            return self._payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    calls = {"api": 0, "asset": 0}

    def fake_urlopen(req, timeout=0):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if "api.github.com/repos/" in url:
            calls["api"] += 1
            raise urllib.error.HTTPError(url, 404, "Not Found", hdrs=None, fp=None)
        if "/releases/download/" in url:
            calls["asset"] += 1
            return _FakeResp(b"adapter-binary")
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(task_cli.importlib_metadata, "version", lambda _pkg: "0.1.5")
    monkeypatch.setattr(task_cli, "_platform_tag", lambda: "windows")
    monkeypatch.setattr(task_cli.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.delenv("LESSCODER_RELEASE_REPO", raising=False)

    downloaded, meta = task_cli._download_adapter_binary(target)
    assert downloaded == target
    assert target.exists()
    assert calls["api"] >= 1
    assert calls["asset"] >= 1
    assert meta["status"] == "ok"
    assert meta["stage"] == "asset_download_direct"
