---
name: changelogger
description: Use when committing work in a repository that has a .changelog/ folder, or when the user wants to keep a changelog, log a change, write or polish release notes, see what changed since the last release, decide how to version (SemVer, hotfixes, build numbers, custom formats) or bump version numbers, cut, tag or publish a release, backfill a changelog from git history, set up per-commit changelog entries, or give end users a "What's new" page. Keeps one fragment per user-visible change in .changelog/unreleased/, derives drafts for commits that lack one, bumps every version file together, and compiles fragments into CHANGELOG.md plus structured JSON at release time. Use it even when the user only says "commit this", "ship it", "release", "bump the version" or "what's new" in a repo that uses it. Not for general git history questions with no changelog, versioning or release intent.
---

# Changelogger

A changelog written at release time is reconstructed from commit subjects and memory, and it reads like it. Changelogger moves the writing to the moment of the change, when you still know why it was made and what a user will notice. Every user-visible change gets a small fragment file in `.changelog/unreleased/`. At release the fragments are compiled into a new section of `CHANGELOG.md` and `.changelog/changelog.json`, all version files are bumped together, and the fragments move to `.changelog/released/<version>/` as the backup of the last release.

Nothing gets lost when a commit is made without an agent. Any commit since the last release that no fragment covers shows up in `status` as a **derived draft**, with a type and text guessed from the commit message, and it has to be resolved before the release.

All mechanics live in one stdlib Python script. `<skill_dir>` is the directory containing this SKILL.md:

    python3 <skill_dir>/scripts/changelogger.py <command> [--help]

Run it from inside the target repository (or pass `-C <path>` before the command). Start every changelog or release task with `status`. It reports:
- whether the repo is set up;
- the current version;
- the fragments;
- the commits that still need one;
- the suggested next version.

## Setup (no .changelog/ yet)

1. **Ask first, then stop until the user answers.** Versioning and the release flow are team conventions that end up in tags, headings, CI and the app itself. A wrong guess means redoing the setup, so don't pick silently, even when the user said "go ahead".

   Run `init --dry-run` once, to learn the current version and any existing release tooling. Then ask everything in a single message, with concrete examples built from the current version:
   - **Kinds of releases:** major, minor, patch; hotfixes (urgent fixes on top of an already released version); pre-releases (beta, rc); a build number that grows with every release.
   - **What a version looks like:**
     - `1.4.2` (SemVer, `--scheme semver`)
     - `1.4.2.hotfix-1` (`--scheme semver-hotfix`)
     - `v1.4` (major.minor only, `--scheme two-part`)
     - `0.1.2893` (build counter, `--scheme build`)
     - their own pattern (`--version-format '{major}.{minor}[.hotfix-{hotfix}]'`, where `[...]` appears only when non-zero)
   - **Which changes bump what:** the default is breaking → major, new features → minor, anything else → the lowest regular level. Change it with `--bump-rule KEY=LEVEL`.
   - **Where the `v` shows:** tags (`--tag-format`, default `v{version}`) and/or changelog headings (`--heading-format '## v{version} — {date}'`).
   - **How releases happen:**
     - by hand, when someone asks;
     - automatically, via a branch or CI job that bumps and releases on every merge or PR;
     - through a tool the dry run found (semantic-release, release-please, changesets, a workflow that publishes on tags). In that case, ask whether changelogger replaces it or leaves versioning to it. `references/automation.md` covers these options.

   If they have no preference, recommend SemVer with manual releases. `references/versioning.md` has the format syntax and more patterns.

   Skip only the questions the user answered explicitly. If they described their scheme, don't ask about it again. "When I release" doesn't say whether releases are manual or automated, so still ask how releases happen.
2. Run `init --dry-run` with their choices. It shows:
   - the next version for every level, so the user can check the scheme does what they meant;
   - the version files it will bump together, plus files at other versions it left out;
   - compatibility warnings where a file's ecosystem rejects the format (npm, Cargo and Tauri need SemVer; Python needs PEP 440), with the per-file `--file-format` that fixes each one;
   - the existing changelog style, the lockfiles, and the baseline (latest version tag, else HEAD).
3. Show the user the result and what will be created. Once they confirm, run `init` with the same options plus any overrides (`--version-file` repeatable, `--baseline <ref>`, `--changelog`, `--whats-new <path>`). If the repo has no version anywhere, propose a `VERSION` file.
4. If the changelog has "Unreleased" sections, run `adopt`. It turns them into fragments, and entries without a type heading become drafts for you to classify.
5. Offer a backfill of the commits since the last release with `materialize --range <ref>..HEAD`. It writes draft fragments; polish them as described below.
6. Propose a place where end users can see what changed. Read `references/whats-new.md` for how to pick and build one. GitHub Releases is optional and needs a GitHub remote.
7. Mention the optional git hook (`hooks on`) that drafts entries for commits made by hand. See `references/adopting.md`.
8. If releases should happen in CI, follow `references/automation.md`. It covers a PR check that fails without a fragment, a release on every merge, and the workflow templates in `assets/github/`.

If `status` in an existing setup says versioning was "never chosen", ask the questions from step 1 and fill in `versioning` in `.changelog/config.json` (or re-run `init --force` with the options).

## Writing fragments (every commit you make here)

Write the fragment as part of the change, ideally before committing so it ships in the same commit:

    python3 <skill_dir>/scripts/changelogger.py new --type fixed --text "CSV exports no longer drop the last row."

If the commit already exists, add `--commits HEAD` (or a sha); the fragment then ships with the next commit.
- **Several commits, one change:** they share one fragment (`--commits a1b2c3d,e4f5a6b`).
- **One commit, several changes:** it can need several fragments.
- **Nothing a user would notice** (refactors, tests, CI, internal tooling): record `skip <sha>` so it stops showing up as a draft.

In Claude Code, a hook reports commits without a fragment right after `git commit`; handle those the same way.

The type is one of `added`, `changed`, `deprecated`, `removed`, `fixed` or `security`. Add `--breaking` when users must do something to upgrade, and say what in the text. Add `--audience internal` for things worth keeping in CHANGELOG.md but not in the end-user What's new.

Write for the person using the software, not for the person reading the diff:

| Commit | Fragment |
|---|---|
| `fix(csv): off-by-one in row iterator` | fixed: CSV exports no longer drop the last row. |
| `feat(auth): add PKCE flow to oauth client` | added: You can now sign in with Google from the desktop app. |
| `feat!: remove --legacy flag` | removed, breaking: The `--legacy` flag is gone; use `--format v1` instead. |
| `refactor(db): split repository module` | none: `skip` it |

Say what changed for the user and where, in one or two sentences. Leave out file names, function names and ticket numbers, unless the users are developers: for a library or CLI the API names are the point. `references/fragments.md` has the full guide and more examples.

Drafts are fragments with `draft: true`, written by `materialize`, `adopt` or the git hook. Rewrite the text, fix the type, then delete the `draft: true` line.

## Releasing

1. Run `status` and resolve everything before compiling:
   - Every uncovered commit needs a fragment or a `skip`.
   - Every `draft: true` fragment needs polishing.
   - Merge fragments that describe the same change.
   - Drop fragments for reverted work; `status` warns about these.
2. **Ask before shaping the release**, in one message:
   - **Version:** the one `status` suggests, with its reasoning. It follows the repo's bump rules; `status` prints them and the next version for every level.
     - A hotfix is never suggested automatically. When the user calls a release a hotfix, use `bump hotfix`.
     - For pre-releases use `--pre beta`.
   - **Focus:** which changes this release should lead with. Propose two or three candidates from the fragments. The chosen ones get `highlight: true` and appear in a Highlights block at the top, and they're flagged in the What's new JSON so the app can feature them. They are also what the `--summary` talks about.
   - **Length:** how detailed the notes should be:
     - *brief*: one line per entry;
     - *standard*: one or two sentences;
     - *detailed*: highlights get a short paragraph under the first line explaining what changed and why it matters.

     Edit the fragment texts to match before compiling.

   Skip what the user already answered in their request. The user has the final say on all three.
3. Run `bump <level|auto|explicit version> --dry-run`, then again without `--dry-run`. It refuses, writing nothing, when:
   - the version files disagree: show the user the mismatch instead of forcing it;
   - a file's ecosystem would reject the new version: add the per-file format it suggests to `config.json`.

   It also lists the lockfiles that record the version; refresh them with the printed commands once the user agrees.
4. Run `compile <version> --summary "<one or two sentences a user would care about>"`. Use `--dry-run` first on a first release or an unfamiliar changelog. It:
   - writes the section at the top of CHANGELOG.md in the file's existing style;
   - updates `changelog.json` and the What's new JSON if one is configured;
   - moves the fragments to `released/<version>/`, replacing the previous backup.
5. Show the user the new section. Then commit the release: `git add -A .changelog <changelog> <version files> <lockfiles>` and `git commit -m "chore(release): v<version>"`.
6. Tag (`tag_format` in config, default `v<version>`) only when the user asks: in some repos a `v*` tag triggers CI publishing. The same goes for pushing and for `gh release create v<version> --notes "$(python3 <skill_dir>/scripts/changelogger.py notes <version>)"`.

If a compile went wrong before the release commit, restore the touched files with git (`git restore` / `git clean` on the paths it changed), fix the fragments and compile again. If the release was already committed, revert that commit.

## Approval gates

| Ask first | No need to ask |
|---|---|
| the versioning scheme, creating .changelog/ (`init`), `adopt`, backfill | writing, polishing, merging or skipping fragments |
| choosing the version, `bump`, lockfile refresh | `status`, `notes`, any `--dry-run` |
| `hooks on`, building a What's new UI, CI workflows | the release commit, once the user asked for the release |
| tagging, pushing, `gh release create` | |

## Common mistakes

- Copying the commit subject as the fragment. Rewrite it for the user.
- One fragment per commit, mechanically. Five "fix csv" commits are one entry, or none.
- Hand-editing the new CHANGELOG section after `compile`. Edit the fragments and recompile instead, or `changelog.json` and the What's new view drift. Older sections are fine to edit.
- Hand-editing version numbers, or bumping only one file. Always go through `bump`.
- Tagging or pushing because the user said "release".
- Passing `--allow-drafts` to get past a refusal. Resolve the drafts; that refusal is the point.

## References

- `references/fragments.md`: format, how coverage works, a writing guide with examples for apps and libraries. Read it when polishing drafts or when unsure how to phrase an entry.
- `references/versioning.md`: version formats and presets, bump rules, hotfixes, build counters, pre-releases, per-file formats for npm, Cargo and Python, lockfiles, tags and the release baseline. Read it during setup, before a repo's first release, or when `bump` complains.
- `references/adopting.md`: existing changelogs, backfill, the opt-in git hook and the Claude Code hook, other agents. Read it during setup.
- `references/whats-new.md`: end-user surfaces (an in-app What's new view, optional GitHub Releases). Read it when proposing or building one.
- `references/automation.md`: releases in CI (a PR check with `check`, release on merge with `release`, `vendor`, the workflow templates in `assets/github/`) and coexisting with semantic-release, release-please or changesets. Read it when the user wants automated releases or the repo already has release tooling.
