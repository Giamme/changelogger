"""Black-box tests for changelogger.py and claude_hook.py, run against throwaway git repos.

Run: python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "changelogger" / "scripts"
CLI = SCRIPTS / "changelogger.py"
HOOK = SCRIPTS / "claude_hook.py"


class RepoCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "repo"
        self.root.mkdir()
        self.clock = 1_780_000_000
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_") and k != "CLAUDECODE"}
        self.env.update({"GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "T",
                         "GIT_COMMITTER_EMAIL": "t@example.com", "GIT_CONFIG_GLOBAL": os.devnull,
                         "GIT_CONFIG_NOSYSTEM": "1"})
        self.git("init", "-q", "-b", "main")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args, check=True):
        env = dict(self.env)
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = f"@{self.clock} +0000"
        return subprocess.run(["git", *args], cwd=self.root, env=env, check=check, capture_output=True,
                              text=True).stdout.strip()

    def write(self, rel, content):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content).lstrip("\n"))

    def commit(self, message, files=None):
        self.clock += 60
        for rel, content in (files or {f"f{self.clock}.txt": message}).items():
            self.write(rel, content)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "--short=7", "HEAD")

    def cl(self, *args, expect=0):
        proc = subprocess.run([sys.executable, str(CLI), *args], cwd=self.root, env=self.env, capture_output=True,
                              text=True)
        self.assertEqual(proc.returncode, expect, f"changelogger {' '.join(args)}\n{proc.stdout}\n{proc.stderr}")
        return proc.stdout + proc.stderr

    def status(self):
        return json.loads(self.cl("status", "--json"))

    def python_project(self, version="1.4.2"):
        self.commit("chore: scaffold", {
            "pyproject.toml": f"""
                [project]
                name = "demo"
                version = "{version}"
                requires-python = ">=3.9"

                [tool.ruff]
                target-version = "py39"
                required-version = ">=0.5"
                """,
            "src/demo/__init__.py": f'__version__ = "{version}"\n',
        })
        self.git("tag", f"v{version}")

    def init(self, *extra):
        self.cl("init", *extra)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "chore: set up changelogger")


class DerivedDrafts(RepoCase):
    def test_conventional_commits_map_to_types_and_internal_work_is_ignored(self):
        self.python_project()
        self.init()
        self.commit("feat(export): add CSV export for reports")
        self.commit("fix: handle empty report files")
        self.commit("refactor!: rename the public report API")
        self.commit("test: cover the exporter")
        self.commit("Tweak colors in the header")
        self.commit("docs: explain exports [skip changelog]")
        drafts = {d["commits"][0]["subject"]: d for d in self.status()["drafts"]}
        self.assertEqual(drafts["feat(export): add CSV export for reports"]["type"], "added")
        self.assertEqual(drafts["feat(export): add CSV export for reports"]["text"], "Add CSV export for reports")
        self.assertEqual(drafts["fix: handle empty report files"]["type"], "fixed")
        self.assertTrue(drafts["refactor!: rename the public report API"]["breaking"])
        self.assertEqual(drafts["Tweak colors in the header"]["type"], "changed")
        self.assertNotIn("test: cover the exporter", drafts)
        self.assertEqual(len(drafts), 4)

    def test_normalize_collapses_repeated_machine_commits(self):
        self.python_project()
        self.init("--force", "--normalize", r"^forge\(\w+\) attempt \d+:\s*")
        self.commit("forge(cli) attempt 1: add export command")
        self.commit("forge(cli) attempt 2: add export command")
        drafts = self.status()["drafts"]
        self.assertEqual(len(drafts), 1)
        self.assertEqual(len(drafts[0]["commits"]), 2)

    def test_revert_pair_inside_range_cancels_out(self):
        self.python_project()
        self.init()
        sha = self.commit("feat: add dark mode")
        self.git("revert", "--no-edit", sha)
        self.assertEqual(self.status()["drafts"], [])


class Coverage(RepoCase):
    def setUp(self):
        super().setUp()
        self.python_project()
        self.init()

    def test_fragment_naming_the_commit_covers_it(self):
        sha = self.commit("feat: add CSV export")
        self.cl("new", "--type", "added", "--text", "Reports can be exported as CSV.", "--commits", "HEAD")
        self.assertEqual(self.status()["drafts"], [])
        self.assertEqual(self.status()["fragments"][0]["commits"], [sha])

    def test_fragment_added_in_the_same_commit_covers_it(self):
        self.cl("new", "--type", "added", "--text", "Reports can be exported as CSV.")
        self.commit("feat: add CSV export")
        st = self.status()
        self.assertEqual(st["drafts"], [])
        self.assertIsNotNone(st["fragments"][0]["added_by"])

    def test_ride_along_fragment_does_not_cover_the_commit_that_carries_it(self):
        self.commit("feat: add CSV export")
        self.cl("new", "--type", "added", "--text", "CSV export.", "--commits", "HEAD")
        self.commit("feat: add PDF export")
        subjects = [d["commits"][0]["subject"] for d in self.status()["drafts"]]
        self.assertEqual(subjects, ["feat: add PDF export"])

    def test_skip_covers_and_survives_amend_by_subject(self):
        self.commit("feat: internal telemetry switch")
        self.cl("skip", "HEAD")
        self.git("commit", "-q", "--amend", "--no-edit", "--allow-empty")
        self.assertEqual(self.status()["drafts"], [])

    def test_fragment_still_covers_after_history_is_rewritten(self):
        self.commit("fix: handle empty report files")
        self.cl("new", "--type", "fixed", "--text", "Empty reports no longer crash.", "--commits", "HEAD")
        self.git("commit", "-q", "--amend", "-m", "fix: handle empty report files", "--allow-empty")
        self.assertEqual(self.status()["drafts"], [])

    def test_squash_merge_carrying_the_branch_fragments_is_covered(self):
        self.git("checkout", "-q", "-b", "feature")
        self.commit("feat: add CSV export")
        self.cl("new", "--type", "added", "--text", "Reports can be exported as CSV.", "--commits", "HEAD")
        self.commit("test: cover the exporter")
        self.git("checkout", "-q", "main")
        self.git("merge", "-q", "--squash", "feature")
        self.git("commit", "-q", "-m", "Add CSV export (#12)")
        self.git("branch", "-q", "-D", "feature")
        self.git("reflog", "expire", "--expire=now", "--all")
        self.git("gc", "-q", "--prune=now")
        self.assertEqual(self.status()["drafts"], [])

    def test_materialized_drafts_are_reported_until_polished(self):
        self.commit("fix: handle empty report files")
        self.cl("materialize")
        st = self.status()
        self.assertEqual(st["drafts"], [])
        self.assertEqual(len(st["draft_only"]), 1)
        self.assertTrue(st["fragments"][0]["draft"])


class Versions(RepoCase):
    def test_bump_edits_only_the_real_version_strings(self):
        self.python_project("1.4.2")
        self.init()
        self.cl("bump", "2.0.0")
        pyproject = (self.root / "pyproject.toml").read_text()
        self.assertIn('version = "2.0.0"', pyproject)
        self.assertIn('target-version = "py39"', pyproject)
        self.assertIn('required-version = ">=0.5"', pyproject)
        self.assertIn('__version__ = "2.0.0"', (self.root / "src/demo/__init__.py").read_text())

    def test_bump_refuses_when_files_disagree_and_writes_nothing(self):
        self.python_project("1.4.2")
        self.init()
        self.write("src/demo/__init__.py", '__version__ = "1.4.1"\n')
        out = self.cl("bump", "minor", expect=2)
        self.assertIn("disagree", out)
        self.assertIn('version = "1.4.2"', (self.root / "pyproject.toml").read_text())

    def test_init_picks_files_at_the_main_version_in_a_multi_language_repo(self):
        self.commit("chore: scaffold", {
            "package.json": '{\n  "name": "app",\n  "version": "0.1.0",\n  "devDependencies": {"x": "0.1.0"}\n}\n',
            "apps/desktop/package.json": '{"name": "desktop", "version": "0.1.0", "dependencies": {"version": "1"}}',
            "Cargo.toml": '[workspace]\nmembers = ["crates/core"]\n\n[workspace.package]\nversion = "0.1.0"\n\n'
                          '[workspace.dependencies]\nserde = { version = "1.0.0" }\n',
            "crates/core/Cargo.toml": '[package]\nname = "core"\nversion.workspace = true\n',
            "src-tauri/tauri.conf.json": '{"productName": "App", "version": "0.1.0", "plugins": {"x": {"version": "9.9.9"}}}',
            "sdk/examples/demo/package.json": '{"name": "demo", "version": "1.0.0"}',
        })
        self.cl("init")
        cfg = json.loads((self.root / ".changelog/config.json").read_text())
        self.assertEqual(sorted(cfg["version_files"]),
                         ["Cargo.toml", "apps/desktop/package.json", "package.json", "src-tauri/tauri.conf.json"])
        self.cl("bump", "minor")
        self.assertIn('"version": "0.2.0"', (self.root / "package.json").read_text())
        self.assertIn('"x": "0.1.0"', (self.root / "package.json").read_text())
        self.assertIn('serde = { version = "1.0.0" }', (self.root / "Cargo.toml").read_text())
        self.assertIn('"version": "9.9.9"', (self.root / "src-tauri/tauri.conf.json").read_text())
        self.assertIn('"version": "1.0.0"', (self.root / "sdk/examples/demo/package.json").read_text())

    def test_suggestion_follows_semver_and_pre_1_0_rule(self):
        self.python_project("0.3.0")
        self.init()
        self.commit("feat!: drop the legacy config format")
        self.assertEqual(self.status()["suggestion"]["version"], "0.4.0")

    def test_pre_release_labels_increment_then_graduate(self):
        self.python_project("1.4.2")
        self.init()
        self.cl("bump", "major", "--pre", "beta")
        self.cl("bump", "major", "--pre", "beta")
        self.assertIn('version = "2.0.0-beta.2"', (self.root / "pyproject.toml").read_text())
        self.cl("bump", "major")
        self.assertIn('version = "2.0.0"', (self.root / "pyproject.toml").read_text())


class VersioningSchemes(RepoCase):
    def node_app(self, version="1.4.0", tag="v1.4"):
        self.commit("feat: app", {"package.json": f'{{\n  "name": "app",\n  "version": "{version}"\n}}\n'})
        self.git("tag", tag)

    def test_two_part_versions_with_hotfixes_store_valid_semver_in_package_json(self):
        self.node_app()
        out = self.cl("init", "--dry-run", "--version-format", "{major}.{minor}[.hotfix-{hotfix}]")
        self.assertIn("package.json={major}.{minor}.{hotfix}", out)  # hint to make package.json readable
        self.init("--version-format", "{major}.{minor}[.hotfix-{hotfix}]",
                  "--file-format", "package.json={major}.{minor}.0[+hotfix.{hotfix}]",
                  "--heading-format", "## v{version} — {date}")
        self.commit("fix(auth): expired sessions no longer show a blank page")
        self.assertEqual(self.status()["suggestion"]["version"], "1.5")  # hotfixes are never automatic
        self.cl("new", "--type", "fixed", "--text", "No more blank page after a session expires.", "--commits", "HEAD")
        self.cl("bump", "hotfix")
        self.assertIn('"version": "1.4.0+hotfix.1"', (self.root / "package.json").read_text())
        self.cl("compile", "v1.4.hotfix-1", "--date", "2026-09-29")
        self.assertIn("## v1.4.hotfix-1 — 2026-09-29", (self.root / "CHANGELOG.md").read_text())
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "chore(release): v1.4.hotfix-1")
        self.cl("bump", "minor")
        self.assertIn('"version": "1.5.0"', (self.root / "package.json").read_text())

    def test_bump_refuses_a_version_the_file_ecosystem_rejects(self):
        self.node_app("1.4.0", "v1.4.0")
        self.init("--scheme", "semver-hotfix")
        out = self.cl("bump", "hotfix", expect=2)
        self.assertIn("1.4.0.hotfix-1", out)
        self.assertIn("{major}.{minor}.{patch}[+hotfix.{hotfix}]", out)
        self.assertIn('"version": "1.4.0"', (self.root / "package.json").read_text())

    def test_build_counter_grows_with_every_release(self):
        self.commit("feat: app", {"VERSION": "0.1.2893\n"})
        self.init("--scheme", "build")
        self.commit("fix: handle empty lists")
        self.assertEqual(self.status()["suggestion"]["version"], "0.1.2894")
        self.cl("bump", "minor")
        self.assertEqual((self.root / "VERSION").read_text(), "0.2.2894\n")

    def test_status_says_when_versioning_was_never_chosen(self):
        self.python_project()
        self.init()
        self.assertTrue(self.status()["versioning_chosen"])
        cfg_path = self.root / ".changelog/config.json"
        cfg = json.loads(cfg_path.read_text())
        del cfg["versioning"]
        cfg_path.write_text(json.dumps(cfg))
        self.assertFalse(self.status()["versioning_chosen"])
        self.assertIn("never chosen", self.cl("status"))


class Automation(RepoCase):
    def setUp(self):
        super().setUp()
        self.python_project("1.4.2")
        self.init()

    def test_check_fails_until_every_user_visible_commit_has_a_fragment(self):
        self.commit("feat: add scheduled reports")
        self.commit("test: cover the scheduler")
        out = self.cl("check", expect=1)
        self.assertIn("add scheduled reports", out)
        self.assertNotIn("cover the scheduler", out)
        self.cl("new", "--type", "added", "--text", "Reports can run on a schedule.", "--commits", "HEAD~1")
        self.cl("check")

    def test_release_is_a_no_op_when_only_internal_work_landed(self):
        self.commit("chore: bump dependencies")
        self.assertIn("nothing to release", self.cl("release", "auto", "--tag"))
        self.assertEqual(self.git("tag").split(), ["v1.4.2"])

    def test_release_bumps_compiles_commits_and_tags_in_one_step(self):
        self.commit("feat: add scheduled reports")
        self.cl("new", "--type", "added", "--text", "Reports can run on a schedule.", "--commits", "HEAD",
                "--highlight")
        self.cl("new", "--type", "fixed", "--text", "CSV exports keep their last row.")
        self.cl("release", "auto", "--tag", "--date", "2026-09-29")
        self.assertEqual(self.git("log", "-1", "--format=%s"), "chore(release): v1.5.0")
        self.assertIn("v1.5.0", self.git("tag").split())
        self.assertEqual(self.git("status", "--porcelain"), "")
        text = (self.root / "CHANGELOG.md").read_text()
        self.assertLess(text.index("### Highlights"), text.index("### Fixed"))
        self.assertNotIn("### Added", text)  # the only addition is the highlight, not repeated
        history = json.loads((self.root / ".changelog/changelog.json").read_text())
        self.assertTrue(next(e for e in history["versions"][0]["entries"] if "schedule" in e["text"])["highlight"])

    def test_release_refuses_with_drafts_and_writes_nothing(self):
        self.commit("fix: handle empty report files")
        self.cl("release", "auto", "--commit", expect=2)
        self.assertIn('version = "1.4.2"', (self.root / "pyproject.toml").read_text())

    def test_vendor_and_existing_tooling_detection(self):
        self.cl("vendor")
        self.assertTrue((self.root / ".changelog/changelogger.py").is_file())
        self.write(".github/workflows/publish.yml", "on:\n  push:\n    tags: ['v*']\njobs:\n  p:\n    steps:\n"
                   "      - run: twine upload dist/*\n")
        self.write(".changeset/config.json", "{}")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "ci: publish on tags")
        out = self.cl("init", "--dry-run", "--force")
        self.assertIn(".changeset/config.json: changesets", out)
        self.assertIn(".github/workflows/publish.yml: triggers on tag pushes, publishes packages", out)


HAND_WRITTEN = """
# Changelog

Notes for people upgrading.

## Unreleased — 2026-09-08

- Faster startup when the cache is warm.

## 1.4.2 — 2026-08-03

A maintenance release.

| Old | New |
| --- | --- |
| a   | b   |

## Context reliability

Some prose that is not a release.
"""


class Compile(RepoCase):
    def setUp(self):
        super().setUp()
        self.python_project("1.4.2")
        self.write("CHANGELOG.md", HAND_WRITTEN)
        self.init("--whats-new", "web/whats-new.json")

    def test_adopt_then_compile_preserves_the_hand_written_file(self):
        out = self.cl("compile", "1.5.0", expect=2)
        self.assertIn("Unreleased", out)
        self.cl("adopt")
        self.commit("feat: add scheduled reports")
        self.cl("new", "--type", "added", "--text", "Reports can run on a schedule.", "--commits", "HEAD")
        self.cl("new", "--type", "changed", "--text", "Builds use uv.", "--audience", "internal")
        adopted = [f for f in self.status()["fragments"] if "startup" in f["text"]][0]
        self.assertTrue(adopted["draft"])
        self.cl("compile", "1.5.0", expect=2)  # the adopted entry is still a draft
        path = self.root / adopted["path"]
        path.write_text(path.read_text().replace("draft: true\n", ""))
        self.cl("compile", "1.5.0", "--date", "2026-09-29", "--summary", "Scheduling arrives.")

        text = (self.root / "CHANGELOG.md").read_text()
        self.assertNotIn("Unreleased", text)
        self.assertLess(text.index("## 1.5.0 — 2026-09-29"), text.index("## 1.4.2 — 2026-08-03"))
        self.assertLess(text.index("Notes for people upgrading."), text.index("## 1.5.0"))
        for kept in ("| a   | b   |", "## Context reliability", "Some prose that is not a release."):
            self.assertIn(kept, text)
        self.assertNotIn("### Added", text)  # the hand-written file uses plain bullets
        self.assertIn("- Reports can run on a schedule.", text)

        history = json.loads((self.root / ".changelog/changelog.json").read_text())
        self.assertEqual(history["versions"][0]["version"], "1.5.0")
        whats_new = json.loads((self.root / "web/whats-new.json").read_text())
        texts = [e["text"] for e in whats_new["versions"][0]["entries"]]
        self.assertIn("Reports can run on a schedule.", texts)
        self.assertNotIn("Builds use uv.", texts)
        self.assertEqual(list((self.root / ".changelog/unreleased").glob("*.md")), [])
        self.assertEqual(len(list((self.root / ".changelog/released/1.5.0").glob("*.md"))), 3)

    def test_release_commit_becomes_the_new_baseline_and_archive_keeps_only_the_last_release(self):
        self.cl("adopt")
        for f in (self.root / ".changelog/unreleased").glob("*.md"):
            f.write_text(f.read_text().replace("draft: true\n", ""))
        self.commit("fix: keep the last row in CSV exports")
        self.cl("new", "--type", "fixed", "--text", "CSV exports keep their last row.", "--commits", "HEAD")
        self.cl("compile", "1.4.3")
        self.assertEqual(self.status()["drafts"], [])  # release not committed yet: backup still covers
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "chore(release): v1.4.3")
        self.assertEqual(self.status()["commits_since"], 0)
        self.commit("feat: add PDF export")
        self.cl("new", "--type", "added", "--text", "PDF export.", "--commits", "HEAD")
        self.cl("compile", "1.5.0")
        self.assertEqual([p.name for p in (self.root / ".changelog/released").iterdir()], ["1.5.0"])

    def test_untracked_fragment_from_another_branch_is_not_released(self):
        self.cl("adopt")
        for f in (self.root / ".changelog/unreleased").glob("*.md"):
            f.write_text(f.read_text().replace("draft: true\n", ""))
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "chore: adopt old entries")
        self.git("checkout", "-q", "-b", "spike")
        self.commit("feat: experimental sync")
        self.cl("new", "--type", "added", "--text", "Experimental sync.", "--commits", "HEAD")
        self.git("checkout", "-q", "main")  # the untracked fragment follows the checkout
        out = self.cl("compile", "1.5.0", expect=2)
        self.assertIn("not on this branch", out)
        self.cl("compile", "1.5.0", "--skip-unreachable")
        self.assertNotIn("Experimental sync", (self.root / "CHANGELOG.md").read_text())
        self.assertEqual(len(list((self.root / ".changelog/unreleased").glob("*.md"))), 1)


class Hooks(RepoCase):
    def setUp(self):
        super().setUp()
        self.python_project()
        self.init()
        bindir = Path(self.tmp.name) / "bin"
        bindir.mkdir()
        (bindir / "changelogger").symlink_to(CLI)
        self.env["PATH"] = f"{bindir}{os.pathsep}{self.env['PATH']}"

    def test_git_hook_writes_a_draft_for_manual_commits_and_can_be_removed(self):
        self.cl("hooks", "on")
        self.commit("fix: handle empty report files")
        st = self.status()
        self.assertEqual(len(st["fragments"]), 1)
        self.assertTrue(st["fragments"][0]["draft"])
        self.cl("hooks", "off")
        self.assertFalse((self.root / ".git/hooks/post-commit").exists())

    def test_git_hook_stays_quiet_during_rebase_and_agent_sessions(self):
        self.cl("hooks", "on")
        self.env["CLAUDECODE"] = "1"
        self.commit("feat: add CSV export")
        del self.env["CLAUDECODE"]
        self.assertEqual(self.status()["fragments"], [])
        self.cl("hooks", "off")
        self.git("checkout", "-q", "-b", "topic", "HEAD~1")
        self.commit("feat: topic work")
        self.cl("hooks", "on")
        self.git("rebase", "-q", "main")  # replays "feat: topic work"; post-commit fires for the pick
        self.assertEqual(self.status()["fragments"], [])

    def test_existing_hook_is_kept(self):
        self.write(".git/hooks/post-commit", "#!/bin/sh\necho mine\n")
        self.cl("hooks", "on")
        self.cl("hooks", "off")
        self.assertEqual((self.root / ".git/hooks/post-commit").read_text(), "#!/bin/sh\necho mine\n")

    def test_claude_hook_reports_uncovered_commits_once(self):
        self.commit("feat(export): add CSV export")

        def run(command="git commit -m x"):
            payload = json.dumps({"cwd": str(self.root), "tool_input": {"command": command}})
            return subprocess.run([sys.executable, str(HOOK)], input=payload, env=self.env, capture_output=True,
                                  text=True).stdout

        # Harnesses that ignore the hook's `if` field run it after every shell command.
        self.assertEqual(run("ls -la"), "")
        out = json.loads(run())
        context = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("feat(export): add CSV export", context)
        self.assertIn("Derived draft (added): Add CSV export", context)
        self.assertEqual(run(), "")


if __name__ == "__main__":
    unittest.main()
