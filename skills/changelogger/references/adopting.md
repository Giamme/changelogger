# Adopting changelogger in an existing repo

## An existing CHANGELOG.md

`init` reads the file and matches its style, so new sections look like the old ones:
- **`heading_format`** is taken from the first versioned `##` heading. For example, `## 2.0.0 — 2026-08-03` becomes `## {version} — {date}`, and `## [1.0.0] - 2017-06-20` becomes `## [{version}] - {date}`.
- **`group_by_type`** is true only if the file already uses `### Added` / `### Fixed` subsections. Otherwise entries are plain bullets, still ordered by type.

`compile` inserts the new section before the first `##` heading and leaves everything else untouched: the preamble, older releases, tables, prose, and non-release sections.

**"Unreleased" sections** (`## Unreleased`, `## [Unreleased]`, `## Unreleased — 2026-09-08`) must be converted first. `compile` refuses while they exist, because their entries would otherwise be lost or end up below the new release. `adopt` handles the conversion:
- It turns each bullet into a fragment.
- A bullet gets its type from the `###` heading above it.
- Anything without a type heading becomes a `changed` draft.
- It then removes those sections from the file.

After adopting, reclassify the drafts. Merge entries that belong together, since a dated Unreleased section per day often repeats itself. Remove `draft: true` once each one reads well.

## No changelog yet

The file is created at the first `compile`, with a Keep a Changelog header. Nothing is written at `init`.

## Backfill

`init` sets the baseline to the newest version tag, or to HEAD when there are none. So a repo with no tags starts clean.

To bring in the commits since the last release anyway:

    python3 <skill_dir>/scripts/changelogger.py materialize --range v1.4.2..HEAD

This writes one draft per uncovered commit, with the internal types and ignore patterns already filtered out. Then:
- Polish them, merging where commits belong to one change.
- Delete the drafts that shouldn't be in a changelog (deleting the draft file brings the draft back in `status`, so use `skip <sha>` instead).

For a repo that released without tags, like a 2.0.0 that exists only in the changelog, pass `--range <sha of that release>..HEAD`. Find the sha with `git log --oneline -- CHANGELOG.md` or with the user's help.

## Noisy histories

The default `ignore` list covers merges, release commits and `[skip changelog]`. For more:
- **Bots and automation:** `init --ignore '^Update llm-pricing\.yml$'`, or edit `ignore` in `config.json` later.
- **Repeated machine commits** (for example forge's `forge(cli) attempt 3: add export`): `--normalize '^forge\(\w+\) attempt \d+:\s*'` strips the prefix. Attempts at the same change then collapse into one draft that covers all of them.
- **Internal conventional types:** `skip_types` in config. Remove `docs` from it for a documentation project, whose docs *are* the product.

## The opt-in git hook (commits made by hand)

    python3 <skill_dir>/scripts/changelogger.py hooks on | off | status

**What it does:**
- It adds a marked block to `post-commit`. After a commit made outside an agent session, the block writes a `draft: true` fragment for that commit.
- It only acts in repos with `.changelog/config.json`.
- It never touches the index, never amends, and never fails a commit.

**When it stays quiet:**
- during rebase, cherry-pick, revert and merge (`GIT_REFLOG_ACTION`, or the state files under `git rev-parse --git-path`);
- inside a Claude Code session (`CLAUDECODE` is set), where the plugin hook handles it;
- for internal or ignored commits.

**How it runs and where it installs:**
- It calls the `changelogger` command, found on `PATH` or at `~/.local/bin/changelogger`. Without it, the hook does nothing. `hooks on` and `hooks status` print the `ln -s` that creates it; the repo's `scripts/install` creates it too.
- It respects `core.hooksPath` if set in the repo, and puts the block in `.husky/post-commit` for Husky v9.
- It refuses when `core.hooksPath` is set globally, because it would then run in every repo.
- Linked worktrees share the hook.
- An existing `post-commit` is kept, and the block is appended. `hooks off` removes only the block.

Draft files written by the hook are untracked until the next commit. If you switch branches, they follow you. `compile` notices fragments whose commits aren't on the current branch, and refuses to release them without `--skip-unreachable`.

The hook is optional, because `status` already derives drafts for hand-made commits. It's for people who like to see and edit the entry right away.

## The Claude Code hook (plugin)

The plugin's PostToolUse hook runs after `git commit`, `git -C … commit` and `git revert` in Claude Code. It compares HEAD with the last commit it reported on (stored under `git rev-parse --git-path changelogger/`). It lists each new commit without a fragment, with its derived draft, as context for Claude. It stays silent in repos without `.changelog/`, and when every commit is covered.

## Other agents (Codex, Copilot, Cursor, Gemini, OpenCode, …)

Codex and GitHub Copilot CLI can install the Claude Code plugin, hook included. The others get the skill only (through `npx skills` or `scripts/install`), without a commit hook. Two things keep them on track:
- `status` surfaces anything they missed, at the latest at release time.
- A line in the project's `AGENTS.md` (propose it; don't add it unasked): "This repo keeps a changelog in .changelog/: after each user-visible commit, add a fragment with the changelogger skill."

## Config reference (`.changelog/config.json`)

| Key | Default | Purpose |
|---|---|---|
| `changelog` | CHANGELOG.md | Changelog path |
| `heading_format` | `## [{version}] - {date}` | Section heading |
| `group_by_type` | true | `### Added` subsections, or plain bullets |
| `tag_format` | `v{version}` | Tag parsing and naming |
| `versioning` | SemVer preset | Format, bump rules, counter, `zero_major` (see versioning.md) |
| `internal_label` | For contributors | Label for `audience: internal` entries in CHANGELOG.md |
| `version_files` | detected | Files `bump` edits (strings or `{path, format?, pattern?}`) |
| `whats_new_path` | null | User-facing JSON written on compile |
| `skip_types` | build, chore, ci, docs, refactor, style, test(s) | Conventional types that never need a fragment |
| `ignore` | merges, release commits, `[skip changelog]` | Regexes over the full commit message |
| `normalize` | [] | Regexes stripped from subjects before drafting and deduplicating |
| `baseline` | tag or HEAD at init | Fallback start of "unreleased" |
