# Automated releases

By default a human decides when to release, and the agent runs `bump` and `compile` step by step with approvals. Some teams want CI to do it:
- **Release on merge:** every merge to `main`, or to a release branch, bumps the version, compiles the changelog, commits and tags.
- **PR gate:** a pull request can't merge while a user-visible commit lacks a changelog fragment.

Ask about this during setup ("How do releases happen?"). The answer changes what to install.

## Existing release tooling comes first

`init --dry-run` lists the release tooling it finds: semantic-release, release-please, changesets, bump-my-version or bump2version, commitizen, standard-version, release-it, cargo-release, towncrier, and workflows that bump versions, run on tag pushes, publish packages or create GitHub Releases.

Two tools bumping the same version fight each other. When something is already there, ask the user which of these they want:
- **Changelogger replaces it.** Remove or disable the old tool in the same change, after approval, and say what goes away.
- **The existing tool keeps versioning and releasing.** Changelogger then only collects fragments. Don't run `bump` or `compile`; hand the fragments to the tool's own format if it has one (towncrier and changesets both use fragment files), or keep CHANGELOG.md compiled by changelogger with `bump` left unused.
- **Publishing workflows stay as they are.** For example, a workflow that publishes to PyPI on `v*` tags. Changelogger's tags trigger them; say so before the first tag.

## PR gate: `check`

    python3 .changelog/changelogger.py check --range origin/main..HEAD

This exits 1 when a commit in the range has no fragment, or a fragment is a draft or invalid, and prints what's missing. Commits that are internal types, merges or marked `[skip changelog]` pass.

Template: `assets/github/changelog-check.yml`. It only blocks merges once it's marked as a required status check in the branch protection settings, which the user has to do on GitHub.

## Release on merge: `release`

    python3 .changelog/changelogger.py release auto --tag

It runs non-interactively:
1. When nothing user-visible is unreleased, it prints "nothing to release" and exits 0. Merges that only touch internals don't release.
2. Otherwise it picks the level from the bump rules, or takes an explicit level or version.
3. It dry-runs bump and compile first, so it fails, writing nothing, on drafts, uncovered commits or incompatible version files.
4. It bumps, compiles, commits `chore(release): v<version>` and tags it (`--commit` without `--tag` skips the tag).

Template: `assets/github/release-on-merge.yml`. It skips its own release commits, which keeps it from looping.

In CI nobody writes fragments, so the fragments must arrive with the PRs. That's why release-on-merge needs the PR gate, and why agents should write the fragment in the same commit as the change.

**Merge strategy.** Fragments written in the same commit as the change, with an empty `commits:` field, survive every merge strategy.
- **Squash merge:** also fine for fragments that name PR-branch commits. The squash commit adds them, and their commits are no longer on the branch, so it counts as covered.
- **Rebase merge:** fragments that name commits rewrite those commits, and CI can't always match them after the PR branch is deleted.

Ask which strategy the repo uses, and prefer same-commit fragments.

## Setting it up (after the user agrees)

1. Run `vendor`. It copies the script to `.changelog/changelogger.py`, so CI runs the same code without the skill installed. Re-run it when the skill is updated.
2. Copy the templates from `<skill_dir>/assets/github/` into `.github/workflows/`, and adapt them:
   - the release branch (`branches: [main]`);
   - whether to tag;
   - lockfile refresh steps if `bump` lists lockfiles, e.g. `npm install --package-lock-only --ignore-scripts` before the commit. Add them to the workflow and use `release --dry-run` locally to see the plan.
3. Tell the user what CI can't do on its own:
   - **Protected branch:** the default `GITHUB_TOKEN` can't push to a protected branch. Allow the GitHub Actions bot, or use a GitHub App or personal token.
   - **Follow-on workflows:** tags pushed with `GITHUB_TOKEN` don't trigger other workflows. Put the publish step in the release job, or push with an App or personal token.
   - **Pre-releases and hotfixes:** these stay manual (`bump hotfix`, `--pre`), so run them locally or through a manually dispatched workflow.
4. Commit the workflows and the vendored script. Don't push unless asked.

## Other CI systems

The commands are plain Python 3.9+ with git, so any CI can run them:
- `check --range <base>..HEAD` on merge requests;
- `release auto --tag` followed by `git push --follow-tags` on the release branch.

In GitLab, the MR base is `$CI_MERGE_REQUEST_DIFF_BASE_SHA`.
