"""CLI for experiment version control: ``python -m aceneurotools.evc``.

Thin argparse shell over ExperimentVersionControl — the same shared-backend
porcelain the future GUI will call (Comenius parity rule, ADR 0001).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from aceneurotools.evc.errors import EVCError
from aceneurotools.evc.porcelain import ExperimentVersionControl
from aceneurotools.evc.remote import LocalDirectoryRemote


def _fmt_time(ts: int) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(ts)) + " UTC"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m aceneurotools.evc",
        description="Git-like version control for experiment parameters and results.",
    )
    parser.add_argument("--dir", default=".", help="experiment directory (default: cwd)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="start tracking this experiment directory")
    p_record = sub.add_parser("record", help="record the current state as a revision")
    p_record.add_argument("-m", "--message", required=True)
    p_record.add_argument("--author", default=None, help="'Name <email>'")
    sub.add_parser("status", help="show whether the working state differs from HEAD")
    p_log = sub.add_parser("log", help="list revisions, newest first")
    p_log.add_argument("-n", "--limit", type=int, default=None)
    p_show = sub.add_parser("show", help="show one revision")
    p_show.add_argument("rev", nargs="?", default="HEAD")
    p_diff = sub.add_parser("diff", help="compare two revisions")
    p_diff.add_argument("rev_a")
    p_diff.add_argument("rev_b", nargs="?", default="HEAD")
    p_restore = sub.add_parser("restore", help="set working state to a revision (never destroys)")
    p_restore.add_argument("rev")
    p_comment = sub.add_parser("comment", help="annotate a revision without changing it")
    p_comment.add_argument("rev")
    p_comment.add_argument("-m", "--message", required=True)
    p_comments = sub.add_parser("comments", help="show a revision's comments")
    p_comments.add_argument("rev", nargs="?", default="HEAD")
    sub.add_parser("recover", help="list journaled states, incl. safety snapshots")
    p_push = sub.add_parser("push", help="publish history to a shared directory remote")
    p_push.add_argument("remote_path", help="path to the shared (bare) store")

    args = parser.parse_args(argv)
    directory = Path(args.dir)
    try:
        if args.command == "init":
            ExperimentVersionControl.init(directory)
            print(f"initialised empty experiment repository in {directory / '.evc'}")
            return 0
        evc = ExperimentVersionControl.open(directory)
        if args.command == "record":
            oid = evc.record(args.message, author=args.author)
            print(f"recorded {oid[:12]}")
        elif args.command == "status":
            report = evc.status()
            head = report.head[:12] if report.head else "(unborn)"
            state = "clean" if report.clean else f"{len(report.changes)} change(s)"
            print(f"branch {report.branch} @ {head}: {state}")
            for change in report.changes:
                print(f"  {change.status:9s} {change.path}")
        elif args.command == "log":
            for rev in evc.history(limit=args.limit):
                first_line = rev.message.splitlines()[0]
                print(f"{rev.oid[:12]}  {_fmt_time(rev.author_time)}  {rev.author}  {first_line}")
        elif args.command == "show":
            rev = evc.show(args.rev)
            print(f"revision {rev.oid}")
            print(f"author   {rev.author}  {_fmt_time(rev.author_time)}")
            print(f"parents  {', '.join(p[:12] for p in rev.parents) or '(none)'}")
            print(f"message  {rev.message}")
            for path in rev.files:
                print(f"  {path}")
        elif args.command == "diff":
            for change in evc.diff(args.rev_a, args.rev_b):
                print(f"{change.status:9s} {change.path}")
                for param in change.param_changes:
                    print(f"    {param.key}: {param.old!r} -> {param.new!r}")
        elif args.command == "restore":
            result = evc.restore(args.rev)
            print(f"working state set to {result.restored[:12]}")
            if result.safety_snapshot:
                print(f"previous state preserved as {result.safety_snapshot[:12]} "
                      "(see: recover)")
        elif args.command == "comment":
            evc.comment(args.rev, args.message)
            print("comment recorded")
        elif args.command == "comments":
            text = evc.comments(args.rev)
            print(text if text is not None else "(no comments)")
        elif args.command == "recover":
            for entry in evc.recover():
                print(f"{_fmt_time(entry.timestamp)}  {entry.op:16s} "
                      f"{entry.new[:12]}  {entry.ref}  {entry.message}")
        elif args.command == "push":
            remote = LocalDirectoryRemote.create(Path(args.remote_path))
            for result in evc.push(remote):
                state = "up to date" if result.up_to_date else f"{result.objects_sent} object(s)"
                print(f"{result.ref}: {state} -> {result.new_oid[:12]}")
    except EVCError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
