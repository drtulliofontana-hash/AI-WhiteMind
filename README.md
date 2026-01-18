# AI-WhiteMind

## Kill switch (Ctrl+C)

Use Ctrl+C at any time during execution to abort the remaining commands. When interrupted, the runner stops immediately, records an `aborted` event in `task.events.jsonl`, and writes a `task.result.json` with `status="aborted"` and `reason="user_interrupt"`.
