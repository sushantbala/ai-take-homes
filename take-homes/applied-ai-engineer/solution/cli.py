"""Command line entry point.

    python -m solution.cli run            # propose; writes nothing
    python -m solution.cli review         # show the queue
    python -m solution.cli decide ...     # approve or reject
    python -m solution.cli apply          # write the approved ones
    python -m solution.cli eval           # score against the dev labels
    python -m solution.cli status         # ledger state
    python -m solution.cli reset          # wipe local state

The verbs are separate on purpose: `run` is expensive and produces a
proposal, `apply` is cheap and performs writes, and nothing crosses between
them without a recorded human decision.
"""

from __future__ import annotations

import argparse
import json
import sys

from . import config
from .ledger import Ledger
from .llm.provider import build_provider
from .pipeline import apply_approved, run
from .review import Decisions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="solution.cli", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="process transcripts and build the review queue")
    p_run.add_argument("--provider", default="replay", choices=["replay", "anthropic", "adversarial"])
    p_run.add_argument("--record", action="store_true", help="persist live responses as fixtures")
    p_run.add_argument("--only", nargs="*", help="limit to specific call ids, e.g. call-001 call-006")
    p_run.add_argument("--dev", action="store_true", help="shorthand for the labelled dev set, calls 001-015")
    p_run.add_argument("--force", action="store_true", help="reprocess even unchanged transcripts")
    p_run.add_argument("--verbose", action="store_true")

    p_review = sub.add_parser("review", help="print the pending review queue")
    p_review.add_argument("--json", action="store_true")

    p_decide = sub.add_parser("decide", help="record an approval or rejection")
    p_decide.add_argument("fingerprints", nargs="*")
    p_decide.add_argument("--approve", action="store_true")
    p_decide.add_argument("--reject", action="store_true")
    p_decide.add_argument("--approve-all", action="store_true")
    p_decide.add_argument("--reviewer", default="cli-user")
    p_decide.add_argument("--note", default="")

    p_apply = sub.add_parser("apply", help="write approved actions to the stubs")
    p_apply.add_argument("--dry-run", action="store_true")

    p_eval = sub.add_parser("eval", help="score against data/dev_labels.json")
    p_eval.add_argument("--provider", default="replay", choices=["replay", "anthropic", "adversarial"])
    p_eval.add_argument("--runs", type=int, default=1, help="repeat N times and report per-case pass rate")
    p_eval.add_argument("--json", action="store_true")

    sub.add_parser("status", help="show ledger state")
    p_reset = sub.add_parser("reset", help="delete local state (ledger, logs, review, outbox)")
    p_reset.add_argument("--yes", action="store_true", help="skip the confirmation prompt")

    args = parser.parse_args(argv)

    match args.command:
        case "run":
            return _cmd_run(args)
        case "review":
            return _cmd_review(args)
        case "decide":
            return _cmd_decide(args)
        case "apply":
            return _cmd_apply(args)
        case "eval":
            return _cmd_eval(args)
        case "status":
            return _cmd_status()
        case "reset":
            return _cmd_reset(args)
    return 1


def _cmd_run(args) -> int:
    only = args.only
    if args.dev:
        only = [f"call-{i:03d}" for i in range(1, 16)]

    provider = build_provider(args.provider, record=args.record)
    with Ledger() as ledger:
        result = run(provider, ledger, only=only, force=args.force, echo=args.verbose)

    print(result.summary.render())
    print()
    if result.actions:
        print(f"{len(result.actions)} item(s) awaiting review:")
        for action in result.actions:
            target = f" -> {action.dedup_target}" if action.dedup_target else ""
            print(f"  [{action.priority}] {action.outcome}{target}  {action.title[:68]}")
            print(f"        {action.fingerprint}  from {', '.join(s.call_id for s in action.sources)}")
    else:
        print("No items awaiting review.")
    print()
    print(f"Review digest: {result.digest_path}")
    print(f"Approve with:  python -m solution.cli decide --approve-all")
    print(f"Then:          python -m solution.cli apply")

    # Non-zero on a health alert so a scheduler notices. The run still
    # completed and committed whatever succeeded.
    return 2 if result.summary.health else 0


def _cmd_review(args) -> int:
    path = config.REVIEW_DIR / ("latest-queue.json" if args.json else "REVIEW.md")
    if not path.exists():
        print("No review queue yet. Run: python -m solution.cli run --dev", file=sys.stderr)
        return 1
    print(path.read_text(encoding="utf-8"))
    return 0


def _cmd_decide(args) -> int:
    decisions = Decisions.load()
    verdict = "approve" if (args.approve or args.approve_all) else "reject" if args.reject else None
    if verdict is None:
        print("Specify --approve, --reject or --approve-all", file=sys.stderr)
        return 1

    targets = list(args.fingerprints)
    if args.approve_all:
        queue_path = config.REVIEW_DIR / "latest-queue.json"
        if not queue_path.exists():
            print("No review queue to approve.", file=sys.stderr)
            return 1
        targets = [a["fingerprint"] for a in json.loads(queue_path.read_text(encoding="utf-8"))["actions"]]

    if not targets:
        print("No fingerprints given.", file=sys.stderr)
        return 1

    for fingerprint in targets:
        decisions.record(fingerprint, verdict, reviewer=args.reviewer, note=args.note)
    decisions.save()
    print(f"Recorded {verdict} for {len(targets)} item(s) as {args.reviewer}.")
    print("Apply with: python -m solution.cli apply")
    return 0


def _cmd_apply(args) -> int:
    with Ledger() as ledger:
        stats = apply_approved(ledger, dry_run=args.dry_run)
    label = " (dry run, nothing written)" if args.dry_run else ""
    print(f"apply{label}:")
    for key, value in stats.items():
        print(f"  {key:<10} {value}")
    if stats["pending"]:
        print(f"\n{stats['pending']} item(s) still have no decision and were left alone.")
    return 0


def _cmd_eval(args) -> int:
    from .evaluation.harness import run_eval

    provider = build_provider(args.provider)
    report = run_eval(provider, repeats=args.runs)
    if args.json:
        print(json.dumps(report.as_dict(), indent=2))
    else:
        print(report.render())
    return 0 if report.passed else 1


def _cmd_status() -> int:
    with Ledger() as ledger:
        stats = ledger.stats()
        errored = ledger.errored_transcripts()
    width = max(len(k) for k in stats)
    for key, value in stats.items():
        print(f"  {key:<{width}}  {value}")
    if errored:
        print(f"\n  transcripts needing retry: {', '.join(errored)}")
    return 0


def _cmd_reset(args) -> int:
    import shutil

    targets = [config.STATE_DIR, config.ROOT / "stubs" / "outbox"]
    if not args.yes:
        print("This deletes:")
        for t in targets:
            print(f"  {t}")
        if input("Proceed? [y/N] ").strip().lower() != "y":
            print("Aborted.")
            return 1
    for target in targets:
        if target.exists():
            shutil.rmtree(target)
    print("State cleared.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
