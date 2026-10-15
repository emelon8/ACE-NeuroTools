"""CLI for experiment version control: ``python -m aceneurotools.evc``.

Thin argparse shell over ExperimentVersionControl — the same shared-backend
porcelain the future GUI will call (Comenius parity rule, ADR 0001).

Every command accepts ``--json``: machine-readable output on stdout for
scripts and AI agents (the "invisible CLI" — D05/ADR 0002). Payloads are the
frozen ``evc.api`` dataclasses rendered via ``dataclasses.asdict``, so the
JSON shape is the documented API contract. Errors go to stderr with a
non-zero exit either way; ``verify`` emits its report (data, not an error)
on stdout even when verification fails.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from pathlib import Path

from aceneurotools.evc.errors import EVCError
from aceneurotools.evc.pointers import verify_manifest
from aceneurotools.evc.porcelain import ExperimentVersionControl
from aceneurotools.evc.remote import LocalDirectoryRemote
from aceneurotools.evc.workspace import ExperimentWorkspace


def _fmt_time(ts: int) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(ts)) + " UTC"


def _emit(payload: dict) -> None:
    print(json.dumps(payload, default=str))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m aceneurotools.evc",
        description="Git-like version control for experiment parameters and results.",
    )
    parser.add_argument("--dir", default=".", help="experiment directory (default: cwd)")
    machine = argparse.ArgumentParser(add_help=False)
    machine.add_argument(
        "--json",
        action="store_true",
        help="emit machine-readable JSON on stdout (for scripts and agents)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", parents=[machine], help="start tracking this experiment directory")
    p_init.add_argument(
        "--workspace",
        action="store_true",
        help="also scaffold the standard experiment layout (parameters/, results/, artifacts/)",
    )
    p_record = sub.add_parser("record", parents=[machine], help="record the current state as a revision")
    p_record.add_argument("-m", "--message", required=True)
    p_record.add_argument("--author", default=None, help="'Name <email>'")
    sub.add_parser(
        "status",
        parents=[machine],
        help="show whether the working state differs from HEAD",
    )
    p_log = sub.add_parser("log", parents=[machine], help="list revisions, newest first")
    p_log.add_argument("-n", "--limit", type=int, default=None)
    p_show = sub.add_parser("show", parents=[machine], help="show one revision")
    p_show.add_argument("rev", nargs="?", default="HEAD")
    p_diff = sub.add_parser("diff", parents=[machine], help="compare two revisions")
    p_diff.add_argument("rev_a")
    p_diff.add_argument("rev_b", nargs="?", default="HEAD")
    p_restore = sub.add_parser(
        "restore",
        parents=[machine],
        help="set working state to a revision (never destroys)",
    )
    p_restore.add_argument("rev")
    p_comment = sub.add_parser("comment", parents=[machine], help="annotate a revision without changing it")
    p_comment.add_argument("rev")
    p_comment.add_argument("-m", "--message", required=True)
    p_comments = sub.add_parser("comments", parents=[machine], help="show a revision's comments")
    p_comments.add_argument("rev", nargs="?", default="HEAD")
    sub.add_parser(
        "recover",
        parents=[machine],
        help="list journaled states, incl. safety snapshots",
    )
    p_push = sub.add_parser("push", parents=[machine], help="publish history to a shared directory remote")
    p_push.add_argument("remote_path", help="path to the shared (bare) store")
    p_verify = sub.add_parser(
        "verify",
        parents=[machine],
        help="re-hash a run's artifacts against its recorded manifest",
    )
    p_verify.add_argument("run_id", help="run id under results/ in this experiment")

    args = parser.parse_args(argv)
    directory = Path(args.dir)
    try:
        if args.command == "init":
            evc = ExperimentVersionControl.init(directory, workspace=args.workspace)
            if args.json:
                _emit({"initialized": str(evc.repo.evc_dir), "workspace": args.workspace})
            else:
                print(f"initialised empty experiment repository in {directory / '.evc'}")
            return 0
        evc = ExperimentVersionControl.open(directory)
        if args.command == "record":
            oid = evc.record(args.message, author=args.author)
            if args.json:
                _emit({"recorded": oid})
            else:
                print(f"recorded {oid[:12]}")
        elif args.command == "status":
            report = evc.status()
            if args.json:
                _emit(dataclasses.asdict(report))
            else:
                head = report.head[:12] if report.head else "(unborn)"
                state = "clean" if report.clean else f"{len(report.changes)} change(s)"
                print(f"branch {report.branch} @ {head}: {state}")
                for change in report.changes:
                    print(f"  {change.status:9s} {change.path}")
        elif args.command == "log":
            revisions = evc.history(limit=args.limit)
            if args.json:
                _emit({"revisions": [dataclasses.asdict(rev) for rev in revisions]})
            else:
                for rev in revisions:
                    first_line = rev.message.splitlines()[0]
                    print(f"{rev.oid[:12]}  {_fmt_time(rev.author_time)}  {rev.author}  {first_line}")
        elif args.command == "show":
            rev = evc.show(args.rev)
            if args.json:
                _emit(dataclasses.asdict(rev))
            else:
                print(f"revision {rev.oid}")
                print(f"author   {rev.author}  {_fmt_time(rev.author_time)}")
                print(f"parents  {', '.join(p[:12] for p in rev.parents) or '(none)'}")
                print(f"message  {rev.message}")
                for path in rev.files:
                    print(f"  {path}")
        elif args.command == "diff":
            changes = evc.diff(args.rev_a, args.rev_b)
            if args.json:
                _emit({"changes": [dataclasses.asdict(change) for change in changes]})
            else:
                for change in changes:
                    print(f"{change.status:9s} {change.path}")
                    for param in change.param_changes:
                        print(f"    {param.key}: {param.old!r} -> {param.new!r}")
        elif args.command == "restore":
            result = evc.restore(args.rev)
            if args.json:
                _emit(dataclasses.asdict(result))
            else:
                print(f"working state set to {result.restored[:12]}")
                if result.safety_snapshot:
                    print(f"previous state preserved as {result.safety_snapshot[:12]} (see: recover)")
        elif args.command == "comment":
            notes_oid = evc.comment(args.rev, args.message)
            if args.json:
                _emit({"notes_commit": notes_oid})
            else:
                print("comment recorded")
        elif args.command == "comments":
            text = evc.comments(args.rev)
            if args.json:
                _emit({"comments": text})
            else:
                print(text if text is not None else "(no comments)")
        elif args.command == "recover":
            entries = evc.recover()
            if args.json:
                _emit({"journal": [dataclasses.asdict(entry) for entry in entries]})
            else:
                for entry in entries:
                    print(
                        f"{_fmt_time(entry.timestamp)}  {entry.op:16s} {entry.new[:12]}  {entry.ref}  {entry.message}"
                    )
        elif args.command == "push":
            remote = LocalDirectoryRemote.create(Path(args.remote_path))
            results = evc.push(remote)
            if args.json:
                _emit({"results": [dataclasses.asdict(result) for result in results]})
            else:
                for result in results:
                    state = "up to date" if result.up_to_date else f"{result.objects_sent} object(s)"
                    print(f"{result.ref}: {state} -> {result.new_oid[:12]}")
        elif args.command == "verify":
            report = verify_manifest(ExperimentWorkspace(directory).run_dir(args.run_id))
            if args.json:
                _emit({**dataclasses.asdict(report), "clean": report.clean})
            else:
                for rel in report.missing:
                    print(f"missing   {rel}")
                for rel in report.modified:
                    print(f"modified  {rel}")
                if report.clean:
                    print(f"ok: {len(report.verified)} artifact(s) verified")
                else:
                    print(
                        f"verification FAILED: {len(report.missing)} missing, "
                        f"{len(report.modified)} modified, {len(report.verified)} ok"
                    )
            if not report.clean:
                return 1
    except EVCError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
