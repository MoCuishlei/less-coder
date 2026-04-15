import argparse
import json
import os
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
        default="engine/rust/alsp_adapter/Cargo.toml",
        dest="manifest_path",
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
        cmd = [
            "cargo",
            "run",
            "--manifest-path",
            args.manifest_path,
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

    return 1


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)


if __name__ == "__main__":
    sys.exit(main())
