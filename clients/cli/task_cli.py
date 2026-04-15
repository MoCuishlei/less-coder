import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

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

    warmup_parser = sub.add_parser("warmup", help="preflight and warm build before server/MCP usage")
    warmup_parser.add_argument(
        "--manifest-path",
        default=None,
        dest="manifest_path",
    )
    warmup_parser.add_argument(
        "--skip-build",
        action="store_true",
        dest="skip_build",
        help="only run environment checks without cargo build",
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
        manifest_path = _resolve_manifest_path(args.manifest_path)
        if manifest_path is None:
            print(
                json.dumps(
                    {
                        "status": "error",
                        "message": (
                            "alsp_adapter manifest not found. "
                            "Please run from repository root or pass --manifest-path <absolute-path>."
                        ),
                    },
                    ensure_ascii=False,
                )
            )
            return 2
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

    if args.command == "warmup":
        manifest_path = _resolve_manifest_path(args.manifest_path)
        result = _run_warmup(
            manifest_path=manifest_path,
            skip_build=bool(args.skip_build),
            env=os.environ.copy(),
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["status"] == "ok" else int(result.get("exit_code", 2))

    return 1


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)


def _resolve_manifest_path(user_manifest_path: str | None) -> Path | None:
    if user_manifest_path:
        p = Path(user_manifest_path).expanduser().resolve()
        return p if p.exists() else None

    cwd_candidate = _find_manifest_from(Path.cwd())
    if cwd_candidate:
        return cwd_candidate

    module_candidate = _find_manifest_from(Path(__file__).resolve().parents[2])
    if module_candidate:
        return module_candidate

    env_root = os.environ.get("LESSCODER_HOME")
    if env_root:
        env_candidate = _find_manifest_from(Path(env_root).expanduser().resolve())
        if env_candidate:
            return env_candidate

    return None


def _find_manifest_from(start: Path) -> Path | None:
    direct = (start / "engine" / "rust" / "alsp_adapter" / "Cargo.toml").resolve()
    if direct.exists():
        return direct

    for parent in [start, *start.parents]:
        candidate = (parent / "engine" / "rust" / "alsp_adapter" / "Cargo.toml").resolve()
        if candidate.exists():
            return candidate

    return None


def _collect_runtime_checks(manifest_path: Path | None) -> dict[str, str | None]:
    return {
        "python": shutil.which("python") or shutil.which("py"),
        "cargo": shutil.which("cargo"),
        "java": shutil.which("java"),
        "mvn": shutil.which("mvn"),
        "manifest_path": str(manifest_path) if manifest_path else None,
    }


def _run_warmup(
    manifest_path: Path | None, skip_build: bool, env: dict[str, str] | None = None
) -> dict[str, object]:
    checks = _collect_runtime_checks(manifest_path)
    warnings: list[str] = []
    if checks["java"] is None:
        warnings.append("java not found in PATH; verify step may fail for Java projects")
    if checks["mvn"] is None:
        warnings.append("mvn not found in PATH; verify step may fail for Java projects")

    if checks["cargo"] is None or manifest_path is None:
        return {
            "status": "error",
            "message": "warmup failed: cargo or alsp_adapter manifest not found",
            "checks": checks,
            "build": {"skipped": bool(skip_build), "exit_code": 2},
            "warnings": warnings,
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


if __name__ == "__main__":
    sys.exit(main())
