import argparse
import hashlib
from importlib import metadata as importlib_metadata
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
import tomllib

from orchestrator.langgraph_orchestrator import run_real_chain
from clients.cli.trace_query import query_trace


def build_parser(prog: str = "task") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog)
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="run real chain task")
    run_parser.add_argument("--project-root", required=True, dest="project_root")
    run_parser.add_argument("--trace-id", dest="trace_id", default=None)
    run_parser.add_argument("--adapter-host", dest="adapter_host", default="127.0.0.1")
    run_parser.add_argument("--adapter-port", dest="adapter_port", default=8787, type=int)
    run_parser.add_argument(
        "--patch-target",
        dest="patch_target",
        default=None,
        help="target source file path for patch.apply",
    )
    run_parser.add_argument("--verify-command", dest="verify_command", default="mvn")
    run_parser.add_argument(
        "--verify-args",
        dest="verify_args",
        default="test",
        help="comma-separated args, e.g. test,-DskipTests=false",
    )

    trace_parser = sub.add_parser("trace", help="query trace by trace_id")
    trace_parser.add_argument("--trace-id", required=True, dest="trace_id")
    trace_parser.add_argument(
        "--events-file",
        default="logs/trace_events.jsonl",
        dest="events_file",
        help="jsonl trace events file path",
    )

    server_parser = sub.add_parser("server", help="start local adapter service (MCP-ready)")
    server_parser.add_argument("--host", default="127.0.0.1", dest="host")
    server_parser.add_argument("--port", default=8787, type=int, dest="port")
    server_parser.add_argument(
        "--manifest-path",
        default=None,
        dest="manifest_path",
    )
    server_parser.add_argument(
        "--project-root",
        default=None,
        dest="project_root",
        help="project root used to resolve engine/rust/alsp_adapter/Cargo.toml",
    )

    warmup_parser = sub.add_parser("warmup", help="preflight and warm build before server/MCP usage")
    warmup_parser.add_argument(
        "--manifest-path",
        default=None,
        dest="manifest_path",
    )
    warmup_parser.add_argument(
        "--project-root",
        default=None,
        dest="project_root",
        help="project root used to resolve engine/rust/alsp_adapter/Cargo.toml",
    )
    warmup_parser.add_argument(
        "--skip-build",
        action="store_true",
        dest="skip_build",
        help="only run environment checks without cargo build",
    )

    release_dry_run = sub.add_parser("release-dry-run", help="pre-release dry run (no publish)")
    release_dry_run.add_argument(
        "--project-root",
        required=True,
        dest="project_root",
        help="repository root path",
    )
    release_dry_run.add_argument(
        "--skip-tests",
        action="store_true",
        dest="skip_tests",
        help="skip pytest integration tests",
    )
    release_dry_run.add_argument(
        "--tag",
        default=None,
        dest="tag",
        help="optional release tag to verify (e.g. v0.1.0)",
    )
    return parser


def main(argv: list[str] | None = None, prog: str = "task") -> int:
    parser = build_parser(prog=prog)
    args = parser.parse_args(argv)

    if args.command == "run":
        trace_id = args.trace_id or f"tr_{uuid.uuid4().hex[:12]}"
        verify_args = [x for x in args.verify_args.split(",") if x]
        patch_target = args.patch_target
        if patch_target is None:
            patch_target = f"{args.project_root}/src/main/java/com/acme/NameService.java"
        result = asyncio_run(
            run_real_chain(
                project_root=args.project_root,
                trace_id=trace_id,
                adapter_host=args.adapter_host,
                adapter_port=args.adapter_port,
                patch_target=patch_target,
                verify_command=args.verify_command,
                verify_args=verify_args,
            )
        )
        print(json.dumps({"status": "ok", "data": result}, ensure_ascii=False))
        return 0

    if args.command == "trace":
        try:
            result = query_trace(args.events_file, args.trace_id)
        except FileNotFoundError as exc:
            print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
            return 2

        print(json.dumps({"status": "ok", "data": result}, ensure_ascii=False))
        return 0

    if args.command == "server":
        addr = f"{args.host}:{args.port}"
        env = os.environ.copy()
        env["ALSP_ADAPTER_ADDR"] = addr
        _print_mcp_config_hint(args.host, int(args.port), args.project_root, args.manifest_path)
        if not _is_port_available(args.host, int(args.port)):
            suggested = _suggest_available_port(args.host, int(args.port))
            print(
                json.dumps(
                    {
                        "status": "error",
                        "error_code": "COMMON_PORT_IN_USE",
                        "message": f"port already in use: {args.host}:{args.port}",
                        "details": {
                            "host": args.host,
                            "port": int(args.port),
                            "suggested_port": suggested,
                            "next_action": "retry lesscoder server with --port <suggested_port>",
                        },
                    },
                    ensure_ascii=False,
                )
            )
            return 2
        manifest_path, tried_paths = _resolve_manifest_path(
            args.manifest_path,
            args.project_root,
            allow_implicit=True,
        )
        if manifest_path is not None:
            warmup_result = _run_warmup(manifest_path=manifest_path, skip_build=False, env=env)
            if warmup_result["status"] != "ok":
                print(json.dumps(warmup_result, ensure_ascii=False))
                return int(warmup_result.get("exit_code", 2))
            cmd = [
                "cargo",
                "run",
                "--manifest-path",
                str(manifest_path),
                "--bin",
                "alsp_adapter",
            ]
            try:
                completed = subprocess.run(cmd, env=env, check=False)
                return int(completed.returncode)
            except FileNotFoundError:
                print(
                    json.dumps(
                        {
                            "status": "error",
                            "message": "cargo not found, please install Rust toolchain",
                        },
                        ensure_ascii=False,
                    )
                )
                return 127

        adapter_bin, adapter_meta = _resolve_adapter_binary()
        if adapter_bin is None:
            print(
                json.dumps(
                    {
                        "status": "error",
                        "error_code": "COMMON_PRECONDITION_REQUIRED",
                        "message": "alsp_adapter binary not available",
                        "details": {
                            "tried_paths": tried_paths,
                            "adapter_resolution": adapter_meta,
                            "next_action": "set LESSCODER_ADAPTER_BIN or install release assets",
                        },
                    },
                    ensure_ascii=False,
                )
            )
            return 2
        try:
            completed = subprocess.run([adapter_bin], env=env, check=False)
            return int(completed.returncode)
        except FileNotFoundError:
            print(
                json.dumps(
                    {
                        "status": "error",
                        "error_code": "COMMON_PRECONDITION_REQUIRED",
                        "message": f"adapter binary not executable: {adapter_bin}",
                    },
                    ensure_ascii=False,
                )
            )
            return 127
        except OSError as exc:
            print(
                json.dumps(
                    {
                        "status": "error",
                        "error_code": "COMMON_BINARY_INCOMPATIBLE",
                        "message": f"adapter binary failed to start: {exc}",
                        "details": {
                            "adapter_bin": adapter_bin,
                            "next_action": [
                                "set LESSCODER_ADAPTER_BIN to a valid local alsp_adapter binary",
                                "remove incompatible cached binary under ~/.lesscoder/adapter and retry",
                            ],
                        },
                    },
                    ensure_ascii=False,
                )
            )
            return 126

    if args.command == "warmup":
        if not args.manifest_path and not args.project_root:
            print(
                json.dumps(
                    {
                        "status": "error",
                        "error_code": "COMMON_PRECONDITION_REQUIRED",
                        "message": "warmup requires explicit --project-root or --manifest-path",
                        "details": {
                            "required": ["--project-root|--manifest-path"],
                            "next_action": "rerun lesscoder warmup with explicit path arguments",
                        },
                    },
                    ensure_ascii=False,
                )
            )
            return 2
        manifest_path, tried_paths = _resolve_manifest_path(args.manifest_path, args.project_root)
        result = _run_warmup(
            manifest_path=manifest_path,
            skip_build=bool(args.skip_build),
            env=os.environ.copy(),
            tried_paths=tried_paths,
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["status"] == "ok" else int(result.get("exit_code", 2))

    if args.command == "release-dry-run":
        result = _run_release_dry_run(
            project_root=Path(args.project_root).expanduser().resolve(),
            skip_tests=bool(args.skip_tests),
            tag=args.tag,
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["status"] == "ok" else int(result.get("exit_code", 2))

    return 1


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)


def _resolve_manifest_path(
    user_manifest_path: str | None,
    project_root: str | None,
    allow_implicit: bool = False,
) -> tuple[Path | None, list[str]]:
    tried_paths: list[str] = []

    if not user_manifest_path and not project_root and not allow_implicit:
        return None, tried_paths

    if user_manifest_path:
        p = Path(user_manifest_path).expanduser().resolve()
        tried_paths.append(str(p))
        return (p, tried_paths) if p.exists() else (None, tried_paths)

    if project_root:
        root = Path(project_root).expanduser().resolve()
        project_candidate, project_tried = _find_manifest_from(root)
        tried_paths.extend(project_tried)
        if project_candidate:
            return project_candidate, tried_paths

    if allow_implicit:
        cwd_candidate, cwd_tried = _find_manifest_from(Path.cwd())
        tried_paths.extend(cwd_tried)
        if cwd_candidate:
            return cwd_candidate, tried_paths

        module_candidate, module_tried = _find_manifest_from(Path(__file__).resolve().parents[2])
        tried_paths.extend(module_tried)
        if module_candidate:
            return module_candidate, tried_paths

        env_root = os.environ.get("LESSCODER_HOME")
        if env_root:
            env_candidate, env_tried = _find_manifest_from(Path(env_root).expanduser().resolve())
            tried_paths.extend(env_tried)
            if env_candidate:
                return env_candidate, tried_paths

    dedup_tried = list(dict.fromkeys(tried_paths))
    return None, dedup_tried


def _find_manifest_from(start: Path) -> tuple[Path | None, list[str]]:
    tried_paths: list[str] = []
    direct = (start / "engine" / "rust" / "alsp_adapter" / "Cargo.toml").resolve()
    tried_paths.append(str(direct))
    if direct.exists():
        return direct, tried_paths

    for parent in [start, *start.parents]:
        candidate = (parent / "engine" / "rust" / "alsp_adapter" / "Cargo.toml").resolve()
        tried_paths.append(str(candidate))
        if candidate.exists():
            return candidate, tried_paths

    return None, tried_paths


def _collect_runtime_checks(manifest_path: Path | None) -> dict[str, str | None]:
    return {
        "python": shutil.which("python") or shutil.which("py"),
        "cargo": shutil.which("cargo"),
        "java": shutil.which("java"),
        "mvn": shutil.which("mvn"),
        "manifest_path": str(manifest_path) if manifest_path else None,
    }


def _run_warmup(
    manifest_path: Path | None,
    skip_build: bool,
    env: dict[str, str] | None = None,
    tried_paths: list[str] | None = None,
) -> dict[str, object]:
    checks = _collect_runtime_checks(manifest_path)
    checks["tried_paths"] = tried_paths or []
    warnings: list[str] = []
    if checks["java"] is None:
        warnings.append("java not found in PATH; verify step may fail for Java projects")
    if checks["mvn"] is None:
        warnings.append("mvn not found in PATH; verify step may fail for Java projects")

    if checks["cargo"] is None or manifest_path is None:
        return {
            "status": "error",
            "message": "warmup failed: cargo or alsp_adapter manifest not found",
            "error_code": "COMMON_PRECONDITION_REQUIRED",
            "checks": checks,
            "build": {"skipped": bool(skip_build), "exit_code": 2},
            "warnings": warnings,
            "next_action": "run system.warmup with project_root or provide --manifest-path",
            "exit_code": 2,
        }

    build = {"skipped": bool(skip_build), "exit_code": 0}
    if not skip_build:
        cmd = [
            "cargo",
            "build",
            "--manifest-path",
            str(manifest_path),
            "--bin",
            "alsp_adapter",
        ]
        completed = subprocess.run(cmd, env=env, check=False)
        build["exit_code"] = int(completed.returncode)
        if completed.returncode != 0:
            return {
                "status": "error",
                "message": "warmup build failed",
                "checks": checks,
                "build": build,
                "warnings": warnings,
                "exit_code": int(completed.returncode),
            }

    return {
        "status": "ok",
        "message": "warmup completed",
        "checks": checks,
        "build": build,
        "warnings": warnings,
        "exit_code": 0,
    }


def _is_port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def _suggest_available_port(host: str, preferred: int, max_probe: int = 20) -> int | None:
    for offset in range(1, max_probe + 1):
        candidate = preferred + offset
        if _is_port_available(host, candidate):
            return candidate
    return None


def _run_release_dry_run(project_root: Path, skip_tests: bool, tag: str | None) -> dict[str, object]:
    if not project_root.exists():
        return {
            "status": "error",
            "error_code": "COMMON_BAD_REQUEST",
            "message": f"project root not found: {project_root}",
            "exit_code": 2,
        }

    version_check = _validate_release_versions(project_root, tag)
    if version_check["status"] != "ok":
        version_check["exit_code"] = 2
        return version_check

    steps: list[dict[str, object]] = []
    tool_check = _check_release_toolchain(skip_tests=skip_tests)
    if tool_check["status"] != "ok":
        return {
            "status": "error",
            "error_code": "COMMON_PRECONDITION_REQUIRED",
            "message": "release dry run toolchain check failed",
            "versions": version_check["versions"],
            "toolchain": tool_check,
            "exit_code": 2,
        }
    npm_exe = str(tool_check["required"]["npm"])
    cargo_exe = str(tool_check["required"]["cargo"])

    if not skip_tests:
        test_step = _run_step(
            name="pytest_integration",
            command=["pytest", "-q", "tests/integration"],
            cwd=project_root,
        )
        steps.append(test_step)
        if test_step["status"] != "ok":
            return {
                "status": "error",
                "error_code": "RELEASE_DRY_RUN_FAILED",
                "message": "integration tests failed",
                "versions": version_check["versions"],
                "steps": steps,
                "exit_code": int(test_step.get("exit_code", 1)),
            }
    else:
        steps.append({"name": "pytest_integration", "status": "skipped", "reason": "skip_tests=true"})

    py_step = _run_step(
        name="python_build",
        command=[sys.executable, "-m", "build"],
        cwd=project_root,
    )
    steps.append(py_step)
    if py_step["status"] != "ok":
        return {
            "status": "error",
            "error_code": "RELEASE_DRY_RUN_FAILED",
            "message": "python build failed",
            "versions": version_check["versions"],
            "steps": steps,
            "exit_code": int(py_step.get("exit_code", 1)),
        }

    npm_step = _run_step(
        name="npm_pack",
        command=[npm_exe, "pack"],
        cwd=project_root,
    )
    steps.append(npm_step)
    if npm_step["status"] != "ok":
        return {
            "status": "error",
            "error_code": "RELEASE_DRY_RUN_FAILED",
            "message": "npm pack failed",
            "versions": version_check["versions"],
            "steps": steps,
            "exit_code": int(npm_step.get("exit_code", 1)),
        }

    rust_step = _run_step(
        name="cargo_release_build",
        command=[
            cargo_exe,
            "build",
            "--release",
            "--manifest-path",
            str(project_root / "engine" / "rust" / "alsp_adapter" / "Cargo.toml"),
            "--bin",
            "alsp_adapter",
        ],
        cwd=project_root,
    )
    steps.append(rust_step)
    if rust_step["status"] != "ok":
        return {
            "status": "error",
            "error_code": "RELEASE_DRY_RUN_FAILED",
            "message": "rust release build failed",
            "versions": version_check["versions"],
            "steps": steps,
            "exit_code": int(rust_step.get("exit_code", 1)),
        }

    return {
        "status": "ok",
        "message": "release dry run passed",
        "versions": version_check["versions"],
        "toolchain": tool_check,
        "steps": steps,
        "exit_code": 0,
    }


def _validate_release_versions(project_root: Path, tag: str | None) -> dict[str, object]:
    pyproject_path = project_root / "pyproject.toml"
    package_json_path = project_root / "package.json"

    if not pyproject_path.exists() or not package_json_path.exists():
        return {
            "status": "error",
            "error_code": "COMMON_PRECONDITION_REQUIRED",
            "message": "pyproject.toml or package.json not found in project root",
        }

    with pyproject_path.open("rb") as f:
        pyproject = tomllib.load(f)
    with package_json_path.open("r", encoding="utf-8") as f:
        package_json = json.load(f)

    py_ver = str(pyproject.get("project", {}).get("version", "")).strip()
    npm_ver = str(package_json.get("version", "")).strip()
    if not py_ver or not npm_ver:
        return {
            "status": "error",
            "error_code": "COMMON_BAD_REQUEST",
            "message": "missing version in pyproject.toml or package.json",
        }

    if py_ver != npm_ver:
        return {
            "status": "error",
            "error_code": "RELEASE_VERSION_MISMATCH",
            "message": "python and npm versions are not aligned",
            "versions": {"python": py_ver, "npm": npm_ver},
        }

    if tag:
        normalized = tag.strip()
        if not re.fullmatch(r"v\d+\.\d+\.\d+", normalized):
            return {
                "status": "error",
                "error_code": "COMMON_BAD_REQUEST",
                "message": "tag format must be vMAJOR.MINOR.PATCH",
                "versions": {"python": py_ver, "npm": npm_ver, "tag": normalized},
            }
        if normalized[1:] != py_ver:
            return {
                "status": "error",
                "error_code": "RELEASE_VERSION_MISMATCH",
                "message": "tag version does not match project version",
                "versions": {"python": py_ver, "npm": npm_ver, "tag": normalized},
            }

    return {
        "status": "ok",
        "versions": {"python": py_ver, "npm": npm_ver, "tag": tag.strip() if tag else None},
    }


def _run_step(name: str, command: list[str], cwd: Path) -> dict[str, object]:
    try:
        completed = subprocess.run(command, cwd=str(cwd), check=False)
    except FileNotFoundError:
        return {
            "name": name,
            "status": "error",
            "error_code": "COMMON_PRECONDITION_REQUIRED",
            "message": f"command not found: {command[0]}",
            "exit_code": 127,
        }
    return {
        "name": name,
        "status": "ok" if completed.returncode == 0 else "error",
        "exit_code": int(completed.returncode),
        "command": command,
    }


def _print_mcp_config_hint(host: str, port: int, project_root: str | None, manifest_path: str | None) -> None:
    args = ["server", "--host", host, "--port", str(port)]
    if project_root:
        args.extend(["--project-root", project_root])
    if manifest_path:
        args.extend(["--manifest-path", manifest_path])
    config = {
        "mcpServers": {
            "lesscoder": {
                "command": "lesscoder",
                "args": args,
            }
        }
    }
    print(
        json.dumps(
            {
                "status": "info",
                "message": "mcp config hint",
                "mcp_config": config,
                "http_endpoints": {
                    "health": f"http://{host}:{port}/health",
                    "methods": f"http://{host}:{port}/methods",
                },
            },
            ensure_ascii=False,
        )
    )


def _check_release_toolchain(skip_tests: bool) -> dict[str, object]:
    required = {
        "python": sys.executable,
        "cargo": shutil.which("cargo"),
        "npm": shutil.which("npm") or shutil.which("npm.cmd"),
        "build_module": "python -m build",
    }
    if not skip_tests:
        required["pytest"] = shutil.which("pytest")

    missing: list[str] = []
    if not required["cargo"]:
        missing.append("cargo")
    if not required["npm"]:
        missing.append("npm")
    if not skip_tests and not required.get("pytest"):
        missing.append("pytest")

    return {
        "status": "ok" if not missing else "error",
        "required": required,
        "missing": missing,
    }


def _resolve_adapter_binary() -> tuple[str | None, dict[str, object]]:
    tried: list[str] = []
    env_bin = os.environ.get("LESSCODER_ADAPTER_BIN")
    if env_bin:
        p = Path(env_bin).expanduser().resolve()
        tried.append(str(p))
        if p.exists():
            return str(p), {"source": "env", "tried": tried}

    bundled = _bundled_adapter_path()
    if bundled:
        tried.append(str(bundled))
        if bundled.exists():
            return str(bundled), {"source": "bundled", "tried": tried}

    cached = _cached_adapter_path()
    tried.append(str(cached))
    if cached.exists():
        return str(cached), {"source": "cache", "tried": tried}

    if os.environ.get("LESSCODER_NO_DOWNLOAD", "").strip() == "1":
        return None, {"source": "none", "tried": tried, "download_skipped": True}

    downloaded, download_meta = _download_adapter_binary(cached)
    if downloaded:
        return str(downloaded), {"source": "download", "tried": tried, "download": download_meta}
    return None, {"source": "none", "tried": tried, "download": download_meta}


def _bundled_adapter_path() -> Path | None:
    root = Path(__file__).resolve().parents[1]
    suffix = ".exe" if os.name == "nt" else ""
    candidates = [
        root / "bin" / _platform_tag() / f"alsp_adapter{suffix}",
        root / "bin" / f"alsp_adapter{suffix}",
    ]
    for p in candidates:
        if p.exists():
            return p
    return candidates[0]


def _cached_adapter_path() -> Path:
    ver = _installed_version()
    base = Path.home() / ".lesscoder" / "adapter" / ver / _platform_tag()
    suffix = ".exe" if os.name == "nt" else ""
    return base / f"alsp_adapter{suffix}"


def _installed_version() -> str:
    try:
        return importlib_metadata.version("lesscoder")
    except importlib_metadata.PackageNotFoundError:
        return "0.1.0"


def _platform_tag() -> str:
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def _download_adapter_binary(target: Path) -> tuple[Path | None, dict[str, object]]:
    repo = os.environ.get("LESSCODER_RELEASE_REPO", "MoCuishlei/less-coder")
    version = _installed_version()
    tag = f"v{version}"
    api = f"https://api.github.com/repos/{repo}/releases/tags/{tag}"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "lesscoder-cli"}
    req = urllib.request.Request(api, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            release = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        return None, {"status": "error", "stage": "release_lookup", "message": str(exc)}
    except json.JSONDecodeError as exc:
        return None, {"status": "error", "stage": "release_parse", "message": str(exc)}

    assets = release.get("assets", [])
    asset = _select_release_asset(assets)
    if asset is None:
        return None, {"status": "error", "stage": "asset_select", "message": "matching adapter asset not found"}
    url = asset.get("browser_download_url")
    if not isinstance(url, str) or not url:
        return None, {"status": "error", "stage": "asset_url", "message": "browser_download_url missing"}

    manifest = _download_release_manifest(assets)
    expected_sha = None
    if manifest:
        expected_sha = _lookup_asset_sha256(manifest, str(asset.get("name", "")))

    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=60) as src, target.open("wb") as dst:
            dst.write(src.read())
    except urllib.error.URLError as exc:
        return None, {"status": "error", "stage": "asset_download", "message": str(exc)}

    actual_sha = _sha256_file(target)
    if expected_sha and actual_sha.lower() != expected_sha.lower():
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass
        return None, {
            "status": "error",
            "stage": "checksum_verify",
            "message": "downloaded adapter checksum mismatch",
            "asset": asset.get("name"),
            "expected_sha256": expected_sha,
            "actual_sha256": actual_sha,
        }

    if os.name != "nt":
        target.chmod(0o755)
    return target, {
        "status": "ok",
        "repo": repo,
        "tag": tag,
        "asset": asset.get("name"),
        "sha256": actual_sha,
        "manifest_verified": bool(expected_sha),
    }


def _select_release_asset(assets: list[dict[str, object]]) -> dict[str, object] | None:
    platform = _platform_tag()
    windows_exact = {"alsp_adapter_windows_x86_64.exe", "alsp_adapter.exe", "alsp-adapter-windows.exe"}
    linux_exact = {"alsp_adapter_linux_x86_64", "alsp_adapter", "alsp-adapter-linux"}
    macos_exact = {"alsp_adapter_macos_x86_64", "alsp_adapter", "alsp-adapter-macos"}
    exact = {
        "windows": windows_exact,
        "linux": linux_exact,
        "macos": macos_exact,
    }.get(platform, {"alsp_adapter"})

    # pass 1: exact filename match
    for asset in assets:
        name = str(asset.get("name", ""))
        if name in exact:
            return asset

    # pass 2: strict platform match
    for asset in assets:
        name = str(asset.get("name", ""))
        lower = name.lower()
        if platform == "windows":
            if ("windows" in lower or "win" in lower) and lower.endswith(".exe"):
                return asset
            if "alsp_adapter.exe" in lower:
                return asset
        elif platform == "linux":
            if "linux" in lower and not lower.endswith(".exe"):
                return asset
        elif platform == "macos":
            if ("macos" in lower or "darwin" in lower) and not lower.endswith(".exe"):
                return asset
    return None


def _download_release_manifest(assets: list[dict[str, object]]) -> dict[str, object] | None:
    manifest_asset = None
    for asset in assets:
        name = str(asset.get("name", ""))
        if name in {"lesscoder_adapter_manifest.json", "adapter_manifest.json"}:
            manifest_asset = asset
            break
    if manifest_asset is None:
        return None
    url = manifest_asset.get("browser_download_url")
    if not isinstance(url, str) or not url:
        return None
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError):
        return None


def _lookup_asset_sha256(manifest: dict[str, object], asset_name: str) -> str | None:
    assets = manifest.get("assets")
    if not isinstance(assets, list):
        return None
    for item in assets:
        if not isinstance(item, dict):
            continue
        if str(item.get("name", "")) == asset_name:
            sha = item.get("sha256")
            return str(sha) if isinstance(sha, str) and sha else None
    return None


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


if __name__ == "__main__":
    sys.exit(main())
