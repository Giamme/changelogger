# changelogger

An agent skill that keeps a changelog while you work. You don't have to write one from sixty commit subjects on release day.

- **Fragments while you work:** every user-visible change gets a small entry in `.changelog/unreleased/`, written when the agent still knows why the change was made.
- **Derived drafts:** commits made without an agent, or where the agent forgot, show up as drafts guessed from the commit message, and must be resolved before a release.
- **Releases:** one command compiles the fragments into `CHANGELOG.md` (in the style the file already uses), `changelog.json` and an optional user-facing What's new JSON. The fragments of the last release are kept as a backup.
- **Versioning:** SemVer, hotfixes, two-part versions, build counters or your own format. A suggested bump, then every version file (package.json, pyproject.toml, Cargo.toml, tauri.conf.json, `__version__`, …) edited together, with lockfile hints and tag safety.
- **Hooks:** a plugin hook points out commits without a fragment right after the agent makes them. An opt-in git hook drafts entries for commits made by hand.
- **CI:** a PR check that fails without a fragment, and release-on-merge workflow templates for GitHub Actions.

The skill is a plain [Agent Skills](https://agentskills.io) folder (`skills/changelogger/`) with a stdlib-only Python script (3.9+). It needs `python3` and `git`, nothing else.

## Install

### Claude Code

As a plugin, so you get the skill and the commit hook:

```
/plugin marketplace add Giamme/changelogger
/plugin install changelogger@changelogger
```

From a shell: `claude plugin marketplace add Giamme/changelogger && claude plugin install changelogger@changelogger`.

### Codex

Codex reads the same plugin, hook included:

```sh
codex plugin marketplace add Giamme/changelogger
codex plugin add changelogger@changelogger
```

Codex asks you to review and trust the plugin's hook before it runs.

### GitHub Copilot CLI

```sh
copilot plugin marketplace add Giamme/changelogger
copilot plugin install changelogger@changelogger
```

### Cursor, Gemini CLI, Antigravity, OpenCode, Windsurf/Devin, Amp, Kiro and others

Install the skill with [`npx skills`](https://github.com/vercel-labs/skills), which knows where each agent looks:

```sh
npx skills add Giamme/changelogger            # pick agents interactively
npx skills add Giamme/changelogger -g -a cursor -a gemini-cli -a opencode -y
```

These agents get the skill without the commit hook. `status` still catches every commit that was missed, at the latest at release time. For the same nudge after each commit, add a line to your project's `AGENTS.md`: "This repo keeps a changelog in .changelog/: after each user-visible commit, add a fragment with the changelogger skill."

### From a clone

To track `main` and update every agent with a `git pull`, clone the repo and symlink the skill into each agent that's installed:

```sh
git clone https://github.com/Giamme/changelogger ~/src/changelogger
~/src/changelogger/scripts/install --dry-run   # see what would be linked
~/src/changelogger/scripts/install             # every detected agent; or --client codex --client opencode
~/src/changelogger/scripts/install --uninstall
```

It also links `~/.local/bin/changelogger`, the command the opt-in git hook calls. With any other install method, `hooks on` prints the `ln -s` that creates it.

Install the skill in one place per agent. With the Claude Code plugin installed, don't also copy the skill into `~/.claude/skills`, or Claude Code lists it twice.

## Use

Ask your agent:

- "Set up changelogs in this repo." It asks how you version and release, then writes `.changelog/config.json`.
- "Log this change." / "Commit this." It writes a fragment with the commit.
- "What's unreleased?"
- "Cut a release." It suggests the version, asks what to lead with, bumps every version file, compiles the changelog and makes the release commit. It never tags or pushes unless you ask.

A fragment is a small Markdown file:

```
---
type: fixed
breaking: false
audience: user
commits: 3f2a9c1
---
CSV exports no longer drop the last row.
```

Or run the script directly (`python3 skills/changelogger/scripts/changelogger.py`, or `changelogger` once linked):

```sh
changelogger init --dry-run
changelogger status
changelogger new --type fixed --text "CSV exports no longer drop the last row." --commits HEAD
changelogger bump minor --dry-run
changelogger compile 1.5.0 --summary "Scheduled reports."
changelogger notes 1.5.0
changelogger hooks on
```

[`SKILL.md`](skills/changelogger/SKILL.md) is the full workflow. The [references](skills/changelogger/references/) cover fragments, versioning, adopting an existing changelog, What's new pages and CI.

## Develop

```sh
python3 -m unittest discover -s tests -v
claude plugin validate --strict .
```

Evals for the skill live in `skills/changelogger/evals/`. Their fixture repos are built by `evals/fixtures/make_fixture.sh`.

## License

[MIT](LICENSE)
