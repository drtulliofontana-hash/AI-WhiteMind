#!/usr/bin/env python3
import argparse
import json
import os
import sys
import threading
import time
from typing import Any, Dict, Optional


JSONL_PATH = "task.jsonl"
RESULT_PATH = "task.result.json"


def append_jsonl(payload: Dict[str, Any]) -> None:
    with open(JSONL_PATH, "a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")


def write_result(
    status: str,
    reason: Optional[str] = None,
    abort_after_seconds: Optional[int] = None,
) -> None:
    payload: Dict[str, Any] = {"status": status}
    if reason is not None:
        payload["reason"] = reason
    if abort_after_seconds is not None:
        payload["abort_after_seconds"] = abort_after_seconds
    with open(RESULT_PATH, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def preflight() -> None:
    append_jsonl({"event": "preflight_passed"})


def policy_check() -> None:
    append_jsonl({"event": "policy_passed"})


def confirm() -> bool:
    response = input("Continue? [y/N]: ").strip().lower()
    return response in {"y", "yes"}


def start_abort_timer(
    abort_after_seconds: int,
    abort_event: threading.Event,
) -> threading.Timer:
    def abort_due_to_timeout() -> None:
        if abort_event.is_set():
            return
        abort_event.set()
        append_jsonl(
            {
                "event": "aborted",
                "reason": "timeout_abort",
                "abort_after_seconds": abort_after_seconds,
            }
        )
        write_result(
            status="aborted",
            reason="timeout_abort",
            abort_after_seconds=abort_after_seconds,
        )
        os._exit(1)

    timer = threading.Timer(abort_after_seconds, abort_due_to_timeout)
    timer.daemon = True
    timer.start()
    return timer


def run_tasks() -> None:
    append_jsonl({"event": "task_started"})
    time.sleep(0.1)
    append_jsonl({"event": "task_completed"})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI-WhiteMind runner")
    parser.add_argument(
        "--abort-after",
        type=int,
        default=None,
        metavar="N",
        help="Aborta a execução após N segundos (N >= 1).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.abort_after is not None and args.abort_after < 1:
        print("--abort-after must be >= 1", file=sys.stderr)
        return 2

    abort_event = threading.Event()

    try:
        policy_check()
        preflight()
        if not confirm():
            append_jsonl({"event": "aborted", "reason": "user_declined"})
            write_result(status="aborted", reason="user_declined")
            return 0

        if args.abort_after is not None:
            start_abort_timer(args.abort_after, abort_event)

        run_tasks()
        append_jsonl({"event": "completed"})
        write_result(status="completed")
        return 0
    except KeyboardInterrupt:
        append_jsonl({"event": "aborted", "reason": "keyboard_interrupt"})
        write_result(status="aborted", reason="keyboard_interrupt")
        return 130


if __name__ == "__main__":
    sys.exit(main())
