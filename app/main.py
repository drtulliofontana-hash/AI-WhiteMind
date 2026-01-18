import json
import os
import shlex
import shutil
import subprocess
import sys
from datetime import datetime
from typing import Iterable, Sequence

EVENTS_PATH = os.environ.get("TASK_EVENTS_PATH", "task.events.jsonl")
RESULT_PATH = os.environ.get("TASK_RESULT_PATH", "task.result.json")
POLICY_PATH = os.environ.get(
    "TASK_POLICY_PATH",
    os.path.join(os.path.dirname(__file__), "..", "policy", "policy.json"),
)

DANGEROUS_TOKENS = ("&&", "|", ";", ">", "<")


def write_event(event: str, **fields: object) -> None:
    payload = {
        "event": event,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        **fields,
    }
    with open(EVENTS_PATH, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def write_task_result(outcome: str, hint: str) -> None:
    payload = {
        "outcome": outcome,
        "hint": hint,
    }
    with open(RESULT_PATH, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def write_task_abort(reason: str) -> None:
    payload = {
        "status": "aborted",
        "reason": reason,
    }
    with open(RESULT_PATH, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def get_executable(command: str | Sequence[str]) -> str:
    if isinstance(command, str):
        parts = shlex.split(command)
    else:
        parts = list(command)
    return parts[0] if parts else ""


def normalize_command(command: str | Sequence[str]) -> list[str]:
    if isinstance(command, str):
        return shlex.split(command)
    return list(command)


def load_policy() -> dict[str, object]:
    with open(POLICY_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def is_git_repo(cwd: str) -> bool:
    if os.path.exists(os.path.join(cwd, ".git")):
        return True
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=cwd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def preflight(command: str, cwd: str) -> bool:
    executable = get_executable(command)
    if not executable or shutil.which(executable) is None:
        write_event(
            "preflight_failed",
            reason="executable_not_found",
            executable=executable,
            command=command,
        )
        hint = f"instale {executable}" if executable else "instale o executável"
        write_task_result("failed", hint)
        return False

    if executable == "git" and not is_git_repo(cwd):
        write_event(
            "preflight_failed",
            reason="not_a_git_repo",
            executable=executable,
            command=command,
        )
        write_task_result("failed", "rode git init ou aponte para um repo")
        return False

    return True


def policy_check(command: str, policy: dict[str, object]) -> str | None:
    if any(token in command for token in DANGEROUS_TOKENS):
        write_event(
            "policy_denied",
            reason="dangerous_tokens",
            command=command,
        )
        write_task_result(
            "failed",
            "remova caracteres perigosos (&& | ; > <)",
        )
        return None

    normalized = normalize_command(command)
    allowlist = policy.get("allowlist", [])
    for entry in allowlist:
        if entry.get("cmd") == normalized:
            return entry.get("risk", "low")

    write_event(
        "policy_denied",
        reason="not_allowed",
        command=command,
        normalized=normalized,
    )
    write_task_result("failed", "comando não permitido pela policy")
    return None


def confirm() -> bool:
    response = input("Confirm execution? [y/N]: ").strip().lower()
    return response in {"y", "yes"}


def confirm_medium_risk() -> bool:
    response = input("Medium risk command. Continue? [y/N]: ").strip().lower()
    return response in {"y", "yes"}


def run_commands(commands: Iterable[str], cwd: str) -> None:
    for command in commands:
        subprocess.run(command, cwd=cwd, shell=True, check=False)


def handle_user_interrupt() -> None:
    write_event(
        "aborted",
        reason="user_interrupt",
        signal="SIGINT",
    )
    write_task_abort("user_interrupt")


def main() -> None:
    commands = sys.argv[1:]
    if not commands:
        print("No commands provided.")
        return

    try:
        policy = load_policy()

        print("Execution plan:")
        for command in commands:
            print(f"- {command}")

        risks: list[str] = []
        for command in commands:
            if not preflight(command, os.getcwd()):
                return
            risk = policy_check(command, policy)
            if risk is None:
                return
            risks.append(str(risk))

        if not confirm():
            print("Execution cancelled.")
            return

        if "medium" in risks and not confirm_medium_risk():
            print("Execution cancelled.")
            return

        run_commands(commands, os.getcwd())
    except KeyboardInterrupt:
        handle_user_interrupt()
        return


if __name__ == "__main__":
    main()
