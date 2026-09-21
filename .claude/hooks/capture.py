#!/usr/bin/env python3
"""
Automatic prompt/response capture for Claude Code.

Wired in .claude/settings.json to two lifecycle events:
  UserPromptSubmit -> capture.py prompt   (writes the PROMPT entry)
  Stop             -> capture.py stop     (writes the RESPONSE entry)

Both events receive a JSON payload on stdin. Stop's payload carries
transcript_path, which points at the session JSONL; the final response text is
read from there (text blocks after the last tool_use of the turn - no thinking,
no tool calls, no intermediate steps).

Output: .agent-logs/YYYY-MM-DD_HH-MM-SS_<session-id>.md  (one file per session)

This script never edits or rewrites existing entries. The only mutable region of
a log file is the YAML frontmatter counter block (total_exchanges /
last_prompt_time), which is metadata, not content.
"""

import datetime
import glob
import json
import os
import re
import sys

AUTHOR = "fozangardezi"
PROJECT = "fathom-ai-clone"
TOOL = "claude-code"


def now_iso():
    n = datetime.datetime.now(datetime.timezone.utc)
    return n.strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (n.microsecond // 1000)


def project_dir(payload):
    return (
        os.environ.get("CLAUDE_PROJECT_DIR")
        or payload.get("cwd")
        or os.getcwd()
    )


def log_dir(payload):
    d = os.path.join(project_dir(payload), ".agent-logs")
    os.makedirs(d, exist_ok=True)
    return d


def debug_dump(payload, event):
    """Raw payload dump - used to discover the real hook schema, kept for audit."""
    try:
        d = os.path.join(project_dir(payload), ".claude", "hook-debug")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "%s.json" % event), "w") as fh:
            json.dump(payload, fh, indent=2)
    except Exception:
        pass


# ---------------------------------------------------------------- transcript

def read_transcript(path):
    rows = []
    if not path or not os.path.exists(path):
        return rows
    with open(path, "r", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def is_human_prompt(row):
    if row.get("type") != "user" or row.get("isSidechain"):
        return False
    if row.get("toolUseResult") is not None:
        return False
    origin = row.get("origin") or {}
    if origin and origin.get("kind") not in (None, "human"):
        return False
    return True


def text_of(message):
    content = message.get("content")
    if isinstance(content, str):
        return content
    out = []
    for block in content or []:
        if isinstance(block, dict) and block.get("type") == "text":
            out.append(block.get("text", ""))
    return "\n".join(out)


def latest_model(rows):
    for row in reversed(rows):
        if row.get("type") == "assistant" and not row.get("isSidechain"):
            model = (row.get("message") or {}).get("model")
            if model:
                return model
    return None


def resolve_model(payload, rows):
    return (
        payload.get("model")
        or (payload.get("modelInfo") or {}).get("id")
        or latest_model(rows)
        or "unknown"  # first prompt of a session: no assistant turn exists yet.
        # Deliberately NOT guessed from other sessions - that produced a wrong
        # model name once. The RESPONSE entry always carries the true model.
    )


def last_human_prompt(rows):
    for row in reversed(rows):
        if is_human_prompt(row):
            return text_of(row.get("message") or {})
    return None


def final_response(rows):
    """
    Text of the final assistant message group for the most recent turn.
    Walk forward from the last human prompt; keep text blocks, and drop
    everything collected so far whenever a tool_use appears - what survives to
    the end is the answer the user actually read.
    """
    start = 0
    for i in range(len(rows) - 1, -1, -1):
        if is_human_prompt(rows[i]):
            start = i
            break
    chunks, uuid, ts, model = [], None, None, None
    for row in rows[start + 1:]:
        if row.get("type") != "assistant" or row.get("isSidechain"):
            continue
        msg = row.get("message") or {}
        for block in msg.get("content") or []:
            btype = block.get("type")
            if btype == "tool_use":
                chunks = []
            elif btype == "text" and block.get("text", "").strip():
                chunks.append(block["text"])
                uuid, ts, model = row.get("uuid"), row.get("timestamp"), msg.get("model")
    return "\n".join(chunks).strip(), uuid, ts, model


# ------------------------------------------------------------------ log file

FRONTMATTER = """---
session_id: {sid}
date: {date}
author: {author}
model: {model}
tool: {tool}
project: {project}
total_exchanges: 0
first_prompt_time: {ts}
last_prompt_time: {ts}
---

# Session Log - {date}

Session: `{short}` | Project: `{project}` | Author: `{author}`

---

"""


def log_path(payload, sid, ts, create=True):
    d = log_dir(payload)
    existing = glob.glob(os.path.join(d, "*_%s.md" % sid))
    if existing:
        return existing[0]
    if not create:
        return None
    name = "%s_%s_%s.md" % (ts[0:10], ts[11:19].replace(":", "-"), sid)
    path = os.path.join(d, name)
    with open(path, "w") as fh:
        fh.write(
            FRONTMATTER.format(
                sid=sid,
                date=ts[0:10],
                author=AUTHOR,
                model=payload.get("_model", "unknown"),
                tool=TOOL,
                project=PROJECT,
                ts=ts,
                short=sid[0:8],
            )
        )
    return path


def entry_count(text, kind):
    return len(re.findall(r"\[LOG_ENTRY type=%s num=" % kind, text))


def bump_frontmatter(text, total, last_ts, model, is_prompt):
    text = re.sub(r"^total_exchanges: .*$", "total_exchanges: %d" % total, text, count=1, flags=re.M)
    if is_prompt:
        text = re.sub(r"^last_prompt_time: .*$", "last_prompt_time: %s" % last_ts, text, count=1, flags=re.M)
        if total == 1:
            text = re.sub(r"^first_prompt_time: .*$", "first_prompt_time: %s" % last_ts, text, count=1, flags=re.M)
    if re.search(r"^model: unknown$", text, flags=re.M) and model != "unknown":
        text = re.sub(r"^model: unknown$", "model: %s" % model, text, count=1, flags=re.M)
    return text


def append_entry(path, sid, kind, num, ts, model, body, backfill=False):
    with open(path, "r") as fh:
        text = fh.read()
    mark = "backfill: true (written from the transcript; hook was not installed yet)\n" if backfill else ""
    entry = "[LOG_ENTRY type=%s num=%d session=%s]\ntimestamp: %s\nmodel: %s\n%s\n%s\n\n\n" % (
        kind, num, sid[0:8], ts, model, mark, body.rstrip("\n"),
    )
    text = text + entry
    total = entry_count(text, "PROMPT")
    text = bump_frontmatter(text, total, ts, model, kind == "PROMPT")
    with open(path, "w") as fh:
        fh.write(text)


# --------------------------------------------------------------- state guard

def state_file(payload, sid):
    d = os.path.join(project_dir(payload), ".claude", "hook-state")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "%s.json" % sid)


def read_state(payload, sid):
    try:
        with open(state_file(payload, sid)) as fh:
            return json.load(fh)
    except Exception:
        return {}


def write_state(payload, sid, state):
    with open(state_file(payload, sid), "w") as fh:
        json.dump(state, fh)


# ------------------------------------------------------------------- events

def handle_prompt(payload):
    sid = payload.get("session_id") or "unknown-session"
    rows = read_transcript(payload.get("transcript_path"))
    model = resolve_model(payload, rows)
    prompt = payload.get("prompt")
    if prompt is None:
        prompt = last_human_prompt(rows) or "(prompt text unavailable in hook payload)"
    ts = payload.get("_backfill_ts") or now_iso()
    payload["_model"] = model
    path = log_path(payload, sid, ts)
    with open(path) as fh:
        num = entry_count(fh.read(), "PROMPT") + 1
    append_entry(path, sid, "PROMPT", num, ts, model, prompt,
                 backfill=bool(payload.get("_backfill_ts")))
    state = read_state(payload, sid)
    state.setdefault("turns", {})[str(payload.get("prompt_id"))] = num
    write_state(payload, sid, state)


def handle_stop(payload):
    """
    Turns are keyed by prompt_id, which both events carry. That makes the guard
    exact: a repeated Stop for the same turn is dropped, while a new turn is
    always written - an earlier version keyed on the transcript UUID and
    silently swallowed a legitimate second response.
    """
    sid = payload.get("session_id") or "unknown-session"
    pid = str(payload.get("prompt_id"))
    state = read_state(payload, sid)
    if pid in state.get("answered", []):
        return

    rows = read_transcript(payload.get("transcript_path"))
    body, _uuid, asst_ts, asst_model = final_response(rows)
    payload_body = payload.get("last_assistant_message")
    if isinstance(payload_body, str) and payload_body.strip():
        body = payload_body.strip()  # authoritative: what the user actually saw
    if not body:
        return

    ts = asst_ts or now_iso()
    model = asst_model or resolve_model(payload, rows)
    payload["_model"] = model
    path = log_path(payload, sid, ts, create=False)
    if path is None:
        return  # no prompt has been logged for this session yet
    with open(path) as fh:
        text = fh.read()

    num = state.get("turns", {}).get(pid) or entry_count(text, "RESPONSE") + 1
    if re.search(r"\[LOG_ENTRY type=RESPONSE num=%d " % num, text):
        return  # already answered
    append_entry(path, sid, "RESPONSE", num, ts, model, body)
    state.setdefault("answered", []).append(pid)
    write_state(payload, sid, state)


def main():
    event = sys.argv[1] if len(sys.argv) > 1 else "prompt"
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        payload = {}
    debug_dump(payload, event)
    try:
        if event == "prompt":
            handle_prompt(payload)
        else:
            handle_stop(payload)
    except Exception as exc:  # never block the session on a logging failure
        sys.stderr.write("capture.py %s failed: %s\n" % (event, exc))
    sys.exit(0)


if __name__ == "__main__":
    main()
