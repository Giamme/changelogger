# Fragments

## Format

One Markdown file per change in `.changelog/unreleased/`. The script names them `<UTC timestamp>-<slug>.md`, but any `*.md` name works:

```
---
type: fixed
breaking: false
audience: user
commits: 3f2a9c1, 8b0d1e4
---
CSV exports no longer drop the last row.
```

| Field | Values | Meaning |
|---|---|---|
| `type` | added, changed, deprecated, removed, fixed, security | The Keep a Changelog group it appears under. |
| `breaking` | true / false | Users must act to upgrade. Rendered with a **Breaking:** prefix, and it drives a major bump. |
| `audience` | user / internal | `internal` entries appear in CHANGELOG.md and changelog.json, but not in the What's new JSON or `notes`. |
| `commits` | comma-separated shas, may be empty | The commits this entry covers. Leave it empty when you write the fragment before committing: the commit that adds the file counts as its owner. |
| `draft` | true, or absent | Written by `materialize`, `adopt` or the git hook. `compile` refuses to release until it's removed. |
| `highlight` | true, or absent | Featured in a Highlights block at the top of the release, and flagged in the What's new JSON. Chosen with the user at release time (`new --highlight` or edit the file). |

The body is the entry text. The first line becomes the bullet, and further lines are indented under it, so a breaking change can carry a short migration note. In detailed notes, a highlight's extra lines can explain what changed and why it matters.

Prefer `new` over writing the file by hand: it validates the type and resolves `--commits HEAD` to a sha.

## Coverage: when a commit counts as handled

A commit since the last release is covered when any of these holds:
- a fragment lists it in `commits`;
- the commit itself added a fragment with an empty `commits` field;
- it's listed in `unreleased/skipped.txt` (by sha or exact subject);
- a fragment lists a commit with the same subject. This covers rebased or amended history.

These commits are ignored automatically:
- merge commits;
- the internal conventional types in `skip_types` (build, chore, ci, docs, refactor, style, test), unless marked breaking with `!`;
- messages matching `ignore` (release commits, `[skip changelog]`);
- commits that only touch `.changelog/`;
- a change together with its revert, when both are in the same range.

Anything else is a derived draft in `status`.

A fragment that rides along in a later commit doesn't cover that later commit, only the ones it names. So write a fragment for each change, or `skip` the carrier commit if it's internal.

## Writing guide

Ask: *what would a user notice, and would they care?* Then write it down plainly.

- **Lead with the effect.** "Exports no longer drop the last row", not "Fix off-by-one in exporter".
- **Name the place:** the screen, command, setting or API the user touches.
- **Tense and length:** past or present-state, one sentence, two at most. There's no need for "we".
- **Leave out implementation detail**, like file names, internal function names, refactors or ticket numbers, unless users are developers.
- **Breaking changes** say what breaks and what to do instead: "The `--legacy` flag is removed; use `--format v1`."
- **Merge related work.** Five commits that polish one feature make one `added` entry for the feature, not five `changed` entries.
- **Drop work that never reached users**, such as a feature added and then reverted within the release, or a fix for a bug that never shipped.
- **Security fixes** state the impact without an exploit recipe: "Session cookies are now marked `Secure`."

### Who the users are

**Apps (desktop, web, mobile).** Users never see code. Talk about screens, actions and outcomes.

| Commit | Fragment |
|---|---|
| `feat(settings): persist theme in tauri store` | added: Your theme choice is remembered between launches. |
| `fix(sync): retry on 429 with backoff` | fixed: Sync no longer fails when the server is busy; it retries automatically. |
| `perf(list): virtualize task rows` | changed: Long task lists scroll smoothly. |

**Libraries and SDKs.** Users are developers, so API names are the content.

| Commit | Fragment |
|---|---|
| `feat(client): add timeout option` | added: `Client(timeout=...)` sets a per-request timeout in seconds. |
| `feat!: make parse() async` | changed, breaking: `parse()` is now async; `await` it, or use `parse_sync()` for the old behaviour. |
| `fix: handle BOM in csv reader` | fixed: `read_csv()` accepts files that start with a UTF-8 byte order mark. |

**CLIs.** Name the command and flag the user types.

| Commit | Fragment |
|---|---|
| `feat(cli): add --quiet` | added: `tasklet --quiet` suppresses progress output, handy in scripts. |
| `fix: exit code on missing file` | fixed: `tasklet run` exits with code 2, not 0, when the task file is missing. |

### What gets no fragment (`skip` it)

- refactors, tests, CI, formatting, and dependency bumps with no user-visible effect;
- internal tooling and developer docs, unless the project's users are those developers;
- fixes to things that were never released.

When in doubt, ask whether a user reading the release would miss the line if it were gone.
