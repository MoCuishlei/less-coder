import sys

from clients.cli import task_cli


def main(argv: list[str] | None = None) -> int:
    return task_cli.main(argv=argv, prog="lesscoder")


if __name__ == "__main__":
    sys.exit(main())
