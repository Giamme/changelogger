#!/usr/bin/env bash
# Build a deterministic throwaway git repo for a changelogger eval.
# Usage: make_fixture.sh <setup|after-commit|release|hotfix|ci> <dest-dir>
set -euo pipefail

name="${1:?fixture name}"
dest="${2:?destination}"
[ -e "$dest" ] && { echo "refusing to overwrite $dest" >&2; exit 1; }
mkdir -p "$dest"
cd "$dest"

export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
export GIT_AUTHOR_NAME="Dev" GIT_AUTHOR_EMAIL="dev@example.com"
export GIT_COMMITTER_NAME="Dev" GIT_COMMITTER_EMAIL="dev@example.com"
clock=1780000000
git init -q -b main
git config user.name Dev
git config user.email dev@example.com

commit() {  # commit "<message>"  (stages everything)
  (( clock += 3600 ))
  export GIT_AUTHOR_DATE="@$clock +0000" GIT_COMMITTER_DATE="@$clock +0000"
  git add -A
  git commit -q -m "$1"
}

fragment() {  # fragment <file> <type> <breaking> <audience> <text>
  mkdir -p .changelog/unreleased
  printf -- '---\ntype: %s\nbreaking: %s\naudience: %s\ncommits: \n---\n%s\n' "$2" "$3" "$4" "$5" \
    > ".changelog/unreleased/$1.md"
}

changelog_readme() {
  mkdir -p .changelog/unreleased
  touch .changelog/unreleased/.gitkeep
  cat > .changelog/README.md <<'EOF'
# .changelog

Changelog entries that have not been released yet. Maintained with the changelogger skill.

- `unreleased/` holds one Markdown fragment per user-visible change, written when the change is made.
  `skipped.txt` lists commits deliberately left out of the changelog.
- `released/<version>/` keeps the fragments of the most recent release as a backup.
- `changelog.json` is the structured release history (the source for "What's new" views and release notes).
- `config.json` holds settings: version files bumped together, changelog style, tag format, ignore rules.

A fragment looks like this (file name: anything ending in `.md`):

```
---
type: fixed          # added | changed | deprecated | removed | fixed | security
breaking: false
audience: user       # user | internal (internal entries stay out of What's new)
commits: 3f2a9c1
---
Exported CSV files no longer drop the last row.
```

Write it for the people who use the software, not for the people reading the diff.
EOF
}

case "$name" in
setup)
  mkdir -p src/tasklet
  cat > pyproject.toml <<'EOF'
[project]
name = "tasklet"
version = "0.3.0"
description = "A tiny command-line task list."
requires-python = ">=3.9"

[project.scripts]
tasklet = "tasklet.cli:main"

[tool.ruff]
target-version = "py39"
line-length = 100
EOF
  echo '__version__ = "0.3.0"' > src/tasklet/__init__.py
  tasklet_cli() {  # tasklet_cli <due> <empty-ok> <export> <missing-msg>  (1 = feature present)
    {
      echo 'import argparse'
      echo 'import json'
      echo 'import sys'
      [ "$1" = 1 ] && echo 'from datetime import date'
      echo 'from pathlib import Path'
      echo ''
      echo 'TASKS = Path("tasks.json")'
      echo ''
      echo ''
      echo 'def load():'
      if [ "$4" = 1 ]; then
        echo '    if not TASKS.exists():'
        echo '        print("No tasks.json in this folder. Create one with: echo [] > tasks.json", file=sys.stderr)'
        echo '        sys.exit(2)'
      fi
      if [ "$2" = 1 ]; then
        echo '    text = TASKS.read_text().strip()'
        echo '    return json.loads(text) if text else []'
      else
        echo '    return json.loads(TASKS.read_text())'
      fi
      echo ''
      echo ''
      echo 'def main(argv=None):'
      echo '    parser = argparse.ArgumentParser(prog="tasklet")'
      echo '    sub = parser.add_subparsers(dest="cmd", required=True)'
      echo '    ls = sub.add_parser("list", help="show your tasks")'
      [ "$1" = 1 ] && echo '    ls.add_argument("--due", type=date.fromisoformat, help="only tasks due before this date (YYYY-MM-DD)")'
      [ "$3" = 1 ] && echo '    sub.add_parser("export", help="save a copy of your tasks to another file").add_argument("path")'
      echo '    args = parser.parse_args(argv)'
      echo '    if args.cmd == "list":'
      echo '        for task in load():'
      if [ "$1" = 1 ]; then
        echo '            if args.due and not (task.get("due") and date.fromisoformat(task["due"]) < args.due):'
        echo '                continue'
      fi
      echo '            print("- " + task["title"])'
      if [ "$3" = 1 ]; then
        echo '    elif args.cmd == "export":'
        echo '        from .export import export'
        echo ''
        echo '        export(load(), args.path)'
      fi
      echo ''
      echo ''
      echo 'if __name__ == "__main__":'
      echo '    main()'
    } > src/tasklet/cli.py
  }
  tasklet_cli 0 0 0 0
  printf '# tasklet\n\nA tiny command-line task list.\n' > README.md
  commit "feat: initial task list CLI"
  git tag v0.3.0
  tasklet_cli 1 0 0 0
  commit "feat(cli): add --due filter to list tasks due before a date"
  tasklet_cli 1 1 0 0
  commit "fix: don't crash when tasks.json is empty"
  printf '\n## Filtering\n\n`tasklet list --due 2026-10-01` shows tasks due before that date.\n' >> README.md
  commit "docs: document the --due flag"
  sed -i.bak 's/line-length = 100/line-length = 100\n# ruff 0.6/' pyproject.toml && rm pyproject.toml.bak
  commit "chore: bump ruff to 0.6"
  cat > src/tasklet/export.py <<'EOF'
"""Save a copy of the tasks to another JSON file (`tasklet export <path>`)."""

import json
from pathlib import Path


def export(tasks, path):
    target = Path(path)
    target.write_text(json.dumps(tasks, indent=2) + "\n")
    print(f"Exported {len(tasks)} tasks to {target}")
EOF
  tasklet_cli 1 1 1 0
  commit "feat(export): save a copy of your tasks with tasklet export"
  mkdir -p tests && printf 'from datetime import date\n\n\ndef test_due():\n    assert date.fromisoformat("2026-10-01")\n' > tests/test_due.py
  commit "test: cover due-date parsing"
  tasklet_cli 1 1 1 1
  commit "fix(cli): show a helpful message and exit 2 when the task file is missing"
  ;;

after-commit|ci)
  mkdir -p src/reportly
  cat > pyproject.toml <<'EOF'
[project]
name = "reportly"
version = "1.2.0"
description = "Build and share usage reports from the command line."
requires-python = ">=3.9"
EOF
  echo '__version__ = "1.2.0"' > src/reportly/__init__.py
  cat > src/reportly/cli.py <<'EOF'
import argparse

from .reports import build_report


def main(argv=None):
    parser = argparse.ArgumentParser(prog="reportly")
    sub = parser.add_subparsers(dest="cmd", required=True)
    show = sub.add_parser("show", help="print a report")
    show.add_argument("name")
    args = parser.parse_args(argv)
    if args.cmd == "show":
        print(build_report(args.name))
EOF
  cat > src/reportly/reports.py <<'EOF'
def build_report(name):
    return {"name": name, "columns": ["day", "users"], "rows": [["mon", 3], ["tue", 5]]}
EOF
  commit "feat: reports CLI"
  git tag v1.2.0
  changelog_readme
  cat > .changelog/config.json <<'EOF'
{
  "changelog": "CHANGELOG.md",
  "heading_format": "## [{version}] - {date}",
  "group_by_type": true,
  "tag_format": "v{version}",
  "versioning": {"preset": "semver", "format": "{major}.{minor}.{patch}",
                 "bump_rules": {"breaking": "major", "added": "minor", "default": "patch"}, "zero_major": true},
  "version_files": ["pyproject.toml", "src/reportly/__init__.py"],
  "whats_new_path": null,
  "baseline": null
}
EOF
  commit "chore: set up changelogger"
  sed -i.bak 's/    return {"name": name/    if not name:\n        raise ValueError("report name is required")\n    return {"name": name/' src/reportly/reports.py && rm src/reportly/reports.py.bak
  fragment 20260910-093000-empty-report-name fixed false user \
    "\`reportly show\` explains that a report name is required instead of crashing."
  commit "fix(reports): validate report name"
  cat > src/reportly/export.py <<'EOF'
import csv


def export_csv(report, path):
    """Write a report to CSV: a header row with the column names, then one row per data row."""
    with open(path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(report["columns"])
        writer.writerows(report["rows"])
EOF
  cat > src/reportly/cli.py <<'EOF'
import argparse

from .export import export_csv
from .reports import build_report


def main(argv=None):
    parser = argparse.ArgumentParser(prog="reportly")
    sub = parser.add_subparsers(dest="cmd", required=True)
    show = sub.add_parser("show", help="print a report")
    show.add_argument("name")
    export = sub.add_parser("export", help="save a report to a file")
    export.add_argument("name")
    export.add_argument("--format", choices=["csv"], default="csv")
    export.add_argument("-o", "--output", required=True)
    args = parser.parse_args(argv)
    if args.cmd == "show":
        print(build_report(args.name))
    elif args.cmd == "export":
        export_csv(build_report(args.name), args.output)
EOF
  commit "feat(reports): add CSV export for reports"
  if [ "$name" = ci ]; then
    mkdir -p .github/workflows
    cat > .github/workflows/test.yml <<'WF'
name: test
on:
  pull_request:
  push:
    branches: [main]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python3 -m compileall src
WF
    commit "ci: run tests on pull requests"
  fi
  ;;

release)
  mkdir -p src/reportly web
  cat > pyproject.toml <<'EOF'
[project]
name = "reportly"
version = "1.4.2"
description = "Build and share usage reports."
requires-python = ">=3.8"

[tool.ruff]
target-version = "py38"
EOF
  echo '__version__ = "1.4.2"' > src/reportly/__init__.py
  printf 'def build_report(name):\n    return {"name": name}\n' > src/reportly/reports.py
  cat > CHANGELOG.md <<'EOF'
# Changelog

What changed in reportly, release by release. Upgrade notes are called out where you need to act.

## 1.4.2 — 2026-08-03

A small maintenance release.

- Report titles no longer overflow the page header.
- `reportly show` prints dates in your local time zone.

## 1.4.1 — 2026-07-10

- Fixed a crash when a report had no rows.
EOF
  changelog_readme
  cat > .changelog/config.json <<'EOF'
{
  "changelog": "CHANGELOG.md",
  "heading_format": "## {version} — {date}",
  "group_by_type": false,
  "tag_format": "v{version}",
  "versioning": {"preset": "semver", "format": "{major}.{minor}.{patch}",
                 "bump_rules": {"breaking": "major", "added": "minor", "default": "patch"}, "zero_major": true},
  "version_files": ["pyproject.toml", "src/reportly/__init__.py"],
  "whats_new_path": "web/whats-new.json",
  "baseline": null
}
EOF
  cat > .changelog/changelog.json <<'EOF'
{
  "versions": [
    {
      "version": "1.4.2",
      "date": "2026-08-03",
      "summary": "A small maintenance release.",
      "entries": [
        {"type": "fixed", "text": "Report titles no longer overflow the page header.", "breaking": false, "audience": "user", "commits": []},
        {"type": "changed", "text": "`reportly show` prints dates in your local time zone.", "breaking": false, "audience": "user", "commits": []}
      ]
    }
  ]
}
EOF
  cat > web/whats-new.json <<'EOF'
{
  "versions": [
    {
      "version": "1.4.2",
      "date": "2026-08-03",
      "summary": "A small maintenance release.",
      "entries": [
        {"type": "fixed", "text": "Report titles no longer overflow the page header.", "breaking": false},
        {"type": "changed", "text": "`reportly show` prints dates in your local time zone.", "breaking": false}
      ]
    }
  ]
}
EOF
  commit "chore(release): v1.4.2"
  git tag v1.4.2
  printf '\ndef schedule(report, cron):\n    return (report, cron)\n' >> src/reportly/reports.py
  fragment 20260901-100000-scheduled-reports added false user \
    "Reports can run on a schedule: \`reportly schedule <report> --cron \"0 8 * * 1\"\`."
  commit "feat(schedule): run reports on a schedule"
  sed -i.bak 's/requires-python = ">=3.8"/requires-python = ">=3.9"/; s/target-version = "py38"/target-version = "py39"/' pyproject.toml && rm pyproject.toml.bak
  fragment 20260902-100000-drop-python-38 removed true user \
    "Python 3.8 is no longer supported; reportly now needs Python 3.9 or newer."
  commit "feat!: drop Python 3.8 support"
  printf '\ndef embed_fonts(pdf):\n    return pdf\n' >> src/reportly/reports.py
  commit "fix(pdf): embed fonts so exported PDFs render on Linux"
  printf 'uv lock\n' > Makefile
  fragment 20260904-100000-builds-use-uv changed false internal \
    "Builds and CI use uv; contributors need uv installed to run \`make\`."
  commit "build: switch the build to uv"
  printf '\ndef export_rows(rows):\n    return list(rows)\n' >> src/reportly/reports.py
  fragment 20260905-100000-csv-last-row fixed false user "CSV exports no longer drop the last row."
  commit "fix(export): keep the last row in CSV exports"
  printf '\nQUIET = False\n' >> src/reportly/reports.py
  commit "feat(cli): add --quiet to suppress progress output"
  printf '# deps\n' >> Makefile
  commit "chore: bump dependencies"
  mkdir -p tests && printf 'def test_schedule():\n    assert True\n' > tests/test_schedule.py
  commit "test: cover the scheduler"
  ;;

hotfix)
  mkdir -p src
  cat > package.json <<'EOF'
{
  "name": "pulseboard",
  "version": "1.4.0",
  "private": true,
  "description": "Live usage dashboards for small teams.",
  "scripts": {
    "start": "node src/server.js"
  }
}
EOF
  cat > src/session.js <<'EOF'
// Session handling for the dashboard.
export function onApiResponse(response, router) {
  if (response.status === 401) {
    return null; // session expired: nothing to render
  }
  return response.json();
}
EOF
  printf '# pulseboard\n\nLive usage dashboards for small teams.\n' > README.md
  commit "feat: live usage dashboards"
  git tag v1.4
  cat > src/session.js <<'EOF'
// Session handling for the dashboard.
export function onApiResponse(response, router) {
  if (response.status === 401) {
    router.replace("/sign-in?reason=expired"); // was: render nothing, leaving a blank page
    return null;
  }
  return response.json();
}
EOF
  commit "fix(auth): send users to sign-in when their session expires instead of a blank page"
  ;;

*)
  echo "unknown fixture: $name (setup | after-commit | release | hotfix | ci)" >&2
  exit 1
  ;;
esac

git log --oneline | head -20
