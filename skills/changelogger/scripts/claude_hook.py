#!/usr/bin/env python3
"""Claude Code PostToolUse hook: report commits that have no changelog fragment yet.

Reads the hook payload on stdin. After a `git commit` or `git revert` in a repository with
.changelog/config.json, it compares HEAD with the last commit it reported on and returns the uncovered
commits (with their derived drafts) as additionalContext. It prints nothing, and exits 0, in every other
case. It filters the command itself because harnesses that load Claude plugins (Codex, Copilot) ignore
the hook's `if` field and run it after every shell command.
"""

from __future__ import annotations

import json
import re
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import changelogger as cl  # noqa: E402

COMMITTING = re.compile(r"\bgit\b.*\b(commit|revert)\b", re.S)


def target_dir(command: str, cwd: Path) -> Path:
    """Best effort: honour `cd <dir> && git ...` and `git -C <dir> ...` in the command."""
    try:
        tokens = shlex.split(command)
    except ValueError:
        return cwd
    here = cwd
    for i, token in enumerate(tokens[:-1]):
        if token == "cd":
            here = (here / tokens[i + 1]).resolve()
        elif token == "git" and tokens[i + 1] == "-C" and i + 2 < len(tokens):
            return (here / tokens[i + 2]).resolve()
    return here


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not isinstance(command, str) or not COMMITTING.search(command):
        return 0
    cwd = Path(payload.get("cwd") or ".")
    try:
        repo = cl.Repo(target_dir(command, cwd))
        if not repo.initialized:
            return 0
        head = repo.git("rev-parse", "HEAD", check=False)
        if not head:
            return 0
        state = Path(repo.git("rev-parse", "--git-path", "changelogger/last-seen"))
        state = state if state.is_absolute() else repo.root / state
        last = state.read_text(encoding="utf-8").strip() if state.is_file() else ""
        if last == head:
            return 0
        cfg = repo.config()
        revs = ["-1", head]
        if last and repo.ok("merge-base", "--is-ancestor", last, head):
            baseline, _ = cl.find_baseline(repo, cfg, [])
            if not baseline or repo.ok("merge-base", "--is-ancestor", baseline, last):
                revs = [f"{last}..{head}"]
        an = cl.analyze(repo, cfg, revs=revs)
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(head + "\n", encoding="utf-8")
    except Exception:  # noqa: BLE001 - never disturb the session over a changelog check
        return 0

    lines = []
    for d in an.drafts:
        shas = ",".join(c.short for c in d.commits)
        flag = ", breaking" if d.breaking else ""
        lines.append(f'- {shas} "{d.subject}" has no changelog fragment. Derived draft ({d.type}{flag}): {d.text}')
    for c, f in an.draft_only:
        lines.append(f'- {c.short} "{c.subject}" has only a draft fragment: {repo.rel(f.path)}')
    if not lines:
        return 0
    script = cl.SCRIPT
    context = "\n".join([
        "changelogger: this repository records user-facing changes as fragments in .changelog/unreleased/ "
        "(changelogger skill).",
        *lines,
        f'Fragments are written with `python3 "{script}" new --type <type> --text "<what changed for users>" '
        f"--commits <sha>`; commits users will not notice are recorded with `python3 \"{script}\" skip <sha>`.",
    ])
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": context}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
