# Capture Test

Proof that prompt/response capture is installed, automatic, and works across sessions.

## 1. Tool and model

| | |
|---|---|
| Tool | **Claude Code** v2.1.261 (desktop app, Code tab) |
| Model (plans) | `claude-opus-5` |
| Model (executes) | `claude-opus-5` — same model plans and executes; there is no separate planner/executor split |
| Other models seen | `claude-sonnet-5` — the headless `claude -p` canary session answered as Sonnet. The log shows the switch, which is the point of recording the model per entry. |
| Automatic mechanism? | **Yes.** Claude Code has lifecycle hooks configured in `.claude/settings.json`. Nothing here is manual. |

## 2. Mechanism

Two hook events are wired, both firing on their own:

| Event | Fires | Writes |
|---|---|---|
| `UserPromptSubmit` | the moment a prompt is submitted | the `PROMPT` entry |
| `Stop` | end of turn, when the agent finishes responding | the `RESPONSE` entry |

**Config file changed:** `.claude/settings.json` (committed, repo-local)

```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [{ "type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/capture.py\" prompt" }] }
    ],
    "Stop": [
      { "hooks": [{ "type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/capture.py\" stop" }] }
    ]
  }
}
```

**Script:** `.claude/hooks/capture.py` (stdlib only, no dependencies)

Both events deliver a JSON payload on stdin. The real payload schemas, confirmed by dumping stdin rather than by guessing:

- `UserPromptSubmit` → `session_id`, `transcript_path`, `cwd`, `scratchpad_dir`, `prompt_id`, `permission_mode`, `hook_event_name`, `prompt`, `session_title`
- `Stop` → `session_id`, `transcript_path`, `cwd`, `scratchpad_dir`, `prompt_id`, `permission_mode`, `effort`, `hook_event_name`, `stop_hook_active`, **`last_assistant_message`**, `background_tasks`, `session_crons`

The prompt text comes verbatim from `prompt`. The response text comes from `last_assistant_message`, which is exactly the final message the user saw — no thinking, no tool calls, no intermediate steps. If that field is ever absent, the script falls back to reconstructing the final response from the session JSONL at `transcript_path`: it walks forward from the last human prompt, keeps `text` blocks, and discards everything collected so far each time a `tool_use` block appears, so only the trailing answer survives. Sidechain (subagent) messages are excluded.

The script never edits or deletes an entry once written. The only mutable region of a log file is the YAML frontmatter counter block (`total_exchanges`, `first_prompt_time`, `last_prompt_time`, and `model` while it is still `unknown`).

## 3. Where the canaries landed

| Session | File |
|---|---|
| 1 — this in-app session, `ef89296f` | `.agent-logs/2026-09-21_13-20-47_ef89296f-a107-4eb5-a06e-a6bf1ecc5298.md` |
| 2 — separate headless session, `10ce0a6b` | `.agent-logs/2026-09-21_13-23-56_10ce0a6b-6dde-4882-8f24-32ca2f713a89.md` |

Session 2 was started with `claude -p` from a shell — a genuinely different session with its own session id, proving the hook is not scoped to the session that installed it.

## 4. Canary entries, pasted raw

### Canary 1 — session `ef89296f` (in-app, Opus)

```
[LOG_ENTRY type=PROMPT num=1 session=ef89296f]
timestamp: 2026-09-21T13:22:53.426Z
model: claude-opus-5

CAPTURE TEST — 8x assignment,Fozan Gardezi
```

The matching `RESPONSE num=1` entry is written by the `Stop` hook when this turn ends, so it appears in the committed log file rather than here — it does not exist yet at the moment this file is being written.

### Canary 2 — session `10ce0a6b` (headless `claude -p`, Sonnet)

```
[LOG_ENTRY type=PROMPT num=1 session=10ce0a6b]
timestamp: 2026-09-21T13:23:56.412Z
model: claude-opus-5

CAPTURE TEST — 8x assignment, Fozan Gardezi. Reply with one short sentence confirming you received this canary. Do not use any tools.


[LOG_ENTRY type=RESPONSE num=1 session=10ce0a6b]
timestamp: 2026-09-21T13:23:59.031Z
model: claude-sonnet-5

Received the canary.
```

## 5. What did not work first time

1. **Guessing the hook payload schema.** I did not know whether `UserPromptSubmit` carried the model name. Instead of assuming, I made the script dump raw stdin to `.claude/hook-debug/*.json` on every fire and read the actual keys. That is how `last_assistant_message` was found — it removed the need for most of the transcript parsing I had already written.

2. **A shell-quoting failure faked a hook failure.** My first dry run piped a payload built with `echo` in zsh, which interpreted `\n` inside the JSON string and produced invalid JSON. The script fell back to an empty payload and logged `session: unknown-` with `(prompt text unavailable in hook payload)`. The hook was fine; the test harness was wrong. Rebuilt the payloads with `json.dumps`.

3. **`last_prompt_time` was being overwritten by response timestamps.** The frontmatter bump ran on every entry. Now it only runs for `PROMPT` entries.

4. **The `Stop` hook created an empty log file.** At the end of the turn *before* the hook existed, `Stop` fired, created a log file with frontmatter, then correctly declined to write a response (no prompt entry to answer). The file's `first_prompt_time` was therefore the file-creation time, not the first prompt. Fixed two ways: `Stop` no longer creates a file when there is nothing to write, and `first_prompt_time` is now set from the first `PROMPT` entry. The one stale value in session 1's frontmatter was corrected by hand; it is metadata, and no log entry was touched.

5. **Cross-session model inference was wrong.** For the first prompt of a session no assistant turn exists yet, so the model is unknown. My first version guessed by scanning the most recent transcripts in the project — and canary 2 proved it wrong: it recorded `claude-opus-5` for the prompt while the session actually answered as `claude-sonnet-5`. That wrong guess is still visible in canary 2 above, unedited. I removed the cross-session guess; the first prompt of a session now records `unknown` and the `RESPONSE` entry always carries the true model.

6. **The duplicate guard swallowed a real response.** `Stop` can fire more than once per turn, so I keyed de-duplication on the UUID of the final assistant message in the transcript. A regression test with two turns exposed the flaw: the guard dropped the *second* turn's response whenever the UUID had not changed. Both hook payloads carry a `prompt_id`, which is the exact turn identity, so the guard now keys on that. The test now covers four cases and all pass: duplicate `Stop` ignored, new turn written, an interrupted turn left with a prompt and no response, and numbering still aligned for the turn after it.

7. **Turn 1 of session 1 is not in the log at all.** The assignment brief arrived before any hook existed, so no `PROMPT` entry was captured for it. The full text is recoverable from the session transcript, but backfilling it would mean writing an entry the hook did not produce, so it is left out and noted here instead.

## 6. Notes

- `.agent-logs/` is **not** in `.gitignore` and ships with the repo. `.gitignore` excludes only `.claude/hook-debug/` (raw payload dumps) and `.claude/hook-state/` (per-session duplicate-suppression bookkeeping).
- `Stop` can fire more than once for a turn; the script suppresses duplicates by keying on the final assistant message UUID and by refusing to write a response when one already exists for the open prompt.
- A logging failure never blocks the session: `capture.py` catches everything and exits 0.
