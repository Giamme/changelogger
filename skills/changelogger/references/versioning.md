# Versioning

## Choosing a scheme (ask the user first)

A version's format is a team convention: it shows up in tags, changelog headings, the app's About screen and package registries. So agree on it with the user before `init`. Ask these, and show examples built from the repo's current version:

1. **Which releases do you make?**
   - major / minor / patch;
   - hotfixes (urgent fixes shipped on top of a released version, outside the normal flow);
   - pre-releases (beta, rc);
   - a build number that grows with every release.
2. **What does a version look like?** Offer the presets, or take their own pattern.
3. **Which changes bump what?** The defaults are:
   - breaking → the first level;
   - `added` → minor;
   - anything else → the lowest regular level (patch, build, or minor in a two-part scheme).
4. **Where does the `v` go?** Tags only (`v1.4.2`), or changelog headings too (`## v1.4.2 — 2026-09-29`)?

| Preset | Looks like | Levels | Notes |
|---|---|---|---|
| `semver` (default) | `1.4.2` | major.minor.patch | Standard; works everywhere. |
| `semver-hotfix` | `1.4.2`, then `1.4.2.hotfix-1` | major.minor.patch + hotfix | The hotfix part only appears when non-zero. |
| `two-part` | `1.4`, `v1.10` | major.minor | Every normal change bumps minor. |
| `build` | `0.1.2893` | major.minor.build | `build` counts every release and never resets. |

If the user has no preference, recommend `semver`: it's what every tool expects.

## Custom formats

`--version-format` takes a template:
- `{name}` is a numeric component. Components are ordered by significance, left to right.
- `[...]` wraps an optional segment, written only when a component inside it is non-zero.
- Everything else is literal text.

| Template | Versions it produces |
|---|---|
| `{major}.{minor}.{patch}` | 1.4.2, 1.5.0, 2.0.0 |
| `{major}.{minor}[.hotfix-{hotfix}]` | 1.4, 1.4.hotfix-1, 1.4.hotfix-2, 1.5 |
| `{major}.{minor}.{patch}[.{hotfix}]` | 1.4.2, 1.4.2.1 |
| `{major}.{minor}.{build}` + `--counter build` | 0.1.2893, 0.1.2894, 0.2.2895 |
| `r{major}.{minor}` | r3.7, r3.8 |

How the levels behave:
- **Bumping a level** increments it and resets every level to its right, except the counter.
- **The counter** (`--counter build`) never resets and goes up by one on every release, whatever else is bumped.
- **A level named `hotfix`** is never chosen automatically. It's bumped only by an explicit `bump hotfix`, and bumping any higher level resets it, so `1.4.hotfix-2` → minor → `1.5`.
- **Pre-releases** are a suffix on any format: `bump minor --pre beta` → `1.5.0-beta.1`, again → `1.5.0-beta.2`, then `bump minor` without `--pre` graduates to `1.5.0`.
- **Before 1.0:** while the first level is 0, a breaking change bumps the second level instead (`zero_major`, on by default).

Bump rules map a change to a level: `--bump-rule breaking=major --bump-rule added=minor --bump-rule default=patch`. Keys are `breaking`, a fragment type (`added`, `fixed`, `security`, …) or `default`. When several changes are unreleased, the most significant level wins.

`init --dry-run` prints the next version for every level. Always show it to the user: it's the fastest way to catch a format that doesn't mean what they intended.

Everything lands in `config.json`:

```json
"versioning": {
  "format": "{major}.{minor}[.hotfix-{hotfix}]",
  "bump_rules": {"breaking": "major", "added": "minor", "default": "minor"},
  "zero_major": true
}
```

## Version files and their ecosystems

`init` finds tracked files that hold a version and keeps those that agree with the main one:
- The main one is the shallowest file, in the order VERSION, pyproject.toml, package.json, Cargo.toml, setup.py, `.claude-plugin/plugin.json`, tauri.conf.json.
- Files at a different version are listed as "left out". Examples are an SDK versioned on its own, or example projects.
- Confirm the list with the user.

Some files must hold versions their tooling accepts:

| File | Rule | Consequence |
|---|---|---|
| package.json, Cargo.toml, tauri.conf.json, `.claude-plugin/plugin.json` | SemVer: `X.Y.Z`, optional `-pre` and `+build` | `1.4`, `1.4.hotfix-1` and `1.4.2.1` are invalid |
| pyproject.toml, setup.py, `__version__` | PEP 440 | `1.4` and `1.4.2.1` are fine; `1.4.hotfix-1` is invalid |
| VERSION, custom patterns | anything | |

When the chosen format doesn't fit a file, that file gets its own format with the same components. `init` and `bump` suggest one:

```json
"version_files": [
  "pyproject.toml",
  {"path": "package.json", "format": "{major}.{minor}.0[+hotfix.{hotfix}]"}
]
```

With that, `1.4.hotfix-1` is written as `1.4.0+hotfix.1` in package.json, and still read back as `1.4.hotfix-1`.

Pick the per-file format with the user, since there are trade-offs:
- **`+hotfix.1` (SemVer build metadata)** is valid, but doesn't change precedence. For an app whose package.json is never published, that's fine. **npm cannot publish `1.4.0+hotfix.1` after `1.4.0`**, so for a published package use `{major}.{minor}.{hotfix}` (the hotfix becomes the SemVer patch number).
- **Python:** `{major}.{minor}.{patch}[.post{hotfix}]` gives `1.4.2.post1`, which pip orders correctly. `[.{hotfix}]` gives `1.4.2.1`, also valid.

`bump` refuses, writing nothing, if any file would get an invalid version.

What `bump` edits in each file, and only that:

| File | Edited | Never touched |
|---|---|---|
| `*.json` | the top-level `"version"` string | nested `"version"` keys, dependency versions, path-valued versions |
| `*.toml` | `version = "..."` in `[project]`, `[package]`, `[workspace.package]`, `[tool.poetry]` | `target-version`, `required-version`, inline dependency tables, `version.workspace = true`, `dynamic = ["version"]` |
| `*.py` | `__version__ = "..."`; in setup.py, `version="..."` | anything computed |
| `VERSION`, other plain files | the whole (stripped) content | |

**Other formats** (Info.plist, build.gradle, a Go constant, …): add an entry with a regex that has exactly one capture group and matches exactly once. Add a `format` too if the file needs one:

```json
{"path": "ios/App/Info.plist", "pattern": "<key>CFBundleShortVersionString</key>\\s*<string>([^<]+)</string>",
 "format": "{major}.{minor}.{patch}"}
```

**Safety:** `bump` reads every file first. It writes nothing if a file is unreadable, the versions disagree, or the new version isn't greater than the current one.

**Switching schemes:** when the current version doesn't fit the new format (e.g. going from `1.4.2` to two-part), a level bump is impossible. Run `bump <explicit version>` once, e.g. `bump 1.5`, to convert.

## Hotfix releases

A hotfix ships a fix on top of an already released version without the unreleased work on main. The usual flow:

1. Branch from the release tag: `git switch -c hotfix/1.4.hotfix-1 v1.4`.
2. Commit the fix with its fragment on that branch.
3. `bump hotfix`, `compile <version>`, then the release commit. Tag only if the user asks.
4. Merge the branch back into main, so main's CHANGELOG.md and changelog.json contain the hotfix. A conflict in `.changelog/released/` (the last-release backup) can be resolved either way.

If the user just wants the fix released from main, with nothing else pending, `bump hotfix` on main is fine too. Ask which they want when main has other unreleased fragments.

## Lockfiles

Some lockfiles record the project's own version and go stale after a bump, which breaks `npm ci` and `cargo build --locked`. `bump` lists the ones it finds, with the command that refreshes them:

| Lockfile | Refresh |
|---|---|
| package-lock.json | `npm install --package-lock-only --ignore-scripts` |
| pnpm-lock.yaml | `pnpm install --lockfile-only` |
| yarn.lock | `yarn install --mode update-lockfile` |
| Cargo.lock | `cargo update --workspace --offline` |
| uv.lock | `uv lock` |
| poetry.lock | `poetry lock --no-update` |

Run these after the user agrees, since they can touch the network or other dependency pins. Include the results in the release commit.

## Tags

- `tag_format` defaults to `v{version}`. Match what the repo already uses.
- Tags that look like versions but don't match the format (e.g. `v.0.1.2`) are ignored, with a warning. Don't "fix" existing tags; mention them.
- Create a tag only when the user asks: `git tag -a v1.4.hotfix-1 -m "v1.4.hotfix-1"`.
- Check `.github/workflows` for `on: push: tags` first. If a tag triggers a publish, say so before tagging.
- Never push without an explicit request.

## The release baseline ("since the last release")

Tags are optional, so the script finds the last release in this order:
1. The commit that added the newest version to `.changelog/changelog.json`, which is the release commit.
2. The highest tag matching `tag_format` that is reachable from HEAD.
3. The `baseline` recorded by `init`.

If `status` shows far too many commits, check the baseline line it prints. `baseline` in `config.json` can be set to a sha or tag.

## Monorepos and separately versioned packages

v1 manages one version per `.changelog/`. For a package with its own release cycle (e.g. an SDK inside an app repo), leave it out of `version_files` and tell the user about the limit, instead of bumping it along with the app.
