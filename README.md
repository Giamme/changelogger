# changelogger

An agent skill that keeps a changelog while you work. You don't have to write one from sixty commit subjects on release day.

- **Fragments while you work:** every user-visible change gets a small entry in `.changelog/unreleased/`, written when the agent still knows why the change was made.
- **Derived drafts:** commits made without an agent, or where the agent forgot, show up as drafts guessed from the commit message, and must be resolved before a release.
- **Releases:** one command compiles the fragments into `CHANGELOG.md` (in the style the file already uses), `changelog.json` and an optional user-facing What's new JSON. The fragments of the last release are kept as a backup.
- **Versioning:** a suggested SemVer bump, then every version file (package.json, pyproject.toml, Cargo.toml, tauri.conf.json, `__version__`, …) edited together, with lockfile hints and tag safety.
- **Hooks:** a Claude Code hook points out commits without a fragment right after they are made. An opt-in git hook drafts entries for commits made by hand.

The skill is a plain `SKILL.md` folder with a stdlib-only Python script (3.9+). Any agent that reads Agent Skills can use it.

## Install

**Claude Code** (skill plus commit hook, as a plugin):

```
/plugin marketplace add ~/dev/wizaird/changelogger
/plugin install changelogger@changelogger
```

**Codex, OpenClaude, OpenCode, Kimi, Antigravity** (symlinks), and the `changelogger` command used by the git hook:

```sh
scripts/install --dry-run      # see what would be linked
scripts/install                # every detected agent; or --client codex --client opencode
scripts/install --uninstall
```

Don't also copy the skill into `~/.claude/skills`: with the plugin installed, Claude Code would list it twice.

## Use

Ask your agent: "set up changelogs in this repo", "log this change", "what's unreleased?", "cut a release". Or run the script directly:

```sh
changelogger init --dry-run
changelogger status
changelogger new --type fixed --text "CSV exports no longer drop the last row." --commits HEAD
changelogger bump minor --dry-run
changelogger compile 1.5.0 --summary "Scheduled reports."
changelogger notes 1.5.0
changelogger hooks on
```

## Develop

```sh
python3 -m unittest discover -s tests -v
```

Evals for the skill live in `skills/changelogger/evals/`. Their fixture repos are built by `evals/fixtures/make_fixture.sh`.
