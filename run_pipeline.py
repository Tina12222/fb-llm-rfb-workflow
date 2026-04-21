from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run_cmd(args: list[str]) -> int:
    proc = subprocess.run(args, cwd=ROOT)
    return proc.returncode


def cmd_check(dry_run: bool) -> int:
    print(f"project_root={ROOT}")
    if dry_run:
        return 0
    return run_cmd([sys.executable, "-m", "compileall", str(ROOT)])


def cmd_rag(dry_run: bool) -> int:
    cmd = [sys.executable, "-m", "RAG.rag_core.main"]
    if dry_run:
        cmd.append("--dry-run")
    return run_cmd(cmd)


def cmd_reference(dry_run: bool) -> int:
    cmd = [sys.executable, "-m", "Reference.scripts.ref_main"]
    if dry_run:
        cmd.append("--dry-run")
    return run_cmd(cmd)


def cmd_idea(dry_run: bool) -> int:
    cmd = [sys.executable, "-m", "Reaearch_Idea.code.background"]
    if dry_run:
        cmd.append("--dry-run")
    return run_cmd(cmd)


def main() -> int:
    parser = argparse.ArgumentParser(description="Unified project entrypoint from repository root.")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("check", "rag", "reference", "idea"):
        p = sub.add_parser(name)
        p.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    if args.command == "check":
        return cmd_check(args.dry_run)
    if args.command == "rag":
        return cmd_rag(args.dry_run)
    if args.command == "reference":
        return cmd_reference(args.dry_run)
    if args.command == "idea":
        return cmd_idea(args.dry_run)

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
