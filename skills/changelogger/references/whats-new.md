# Showing changes to end users

CHANGELOG.md is for people who read repositories. End users need to see changes where they already are. Propose the surface that fits the project, and build it only after the user agrees.

## The data

`compile` maintains two files:

- **`.changelog/changelog.json`** is the full history, internal entries included. It's the source of truth, and `notes` reads from it.
- **The What's new JSON**, at `whats_new_path` in config, holds user-audience entries only, newest version first:

```json
{
  "versions": [
    {
      "version": "2.0.0",
      "date": "2026-09-29",
      "summary": "Scheduled reports and a faster exporter.",
      "entries": [
        {"type": "added", "text": "Reports can run on a schedule.", "breaking": false, "highlight": true},
        {"type": "removed", "text": "Python 3.8 is no longer supported.", "breaking": true, "highlight": false}
      ]
    }
  ]
}
```

Put `whats_new_path` where the app's build picks it up, so the data ships with the version it describes. Bundlers don't see `.changelog/`. Set the path in config, and it's written on the next compile. For an existing history, compile writes it from `changelog.json`, so older releases appear too.

| Project | Suggested `whats_new_path` | How the app gets it |
|---|---|---|
| Vite/React, Tauri frontend | `src/whats-new.json` (or `apps/<app>/src/…`) | `import data from "./whats-new.json"` |
| Next.js / static site | `public/whats-new.json` | `fetch("/whats-new.json")` |
| Python web UI served by the package | `<package>/web/whats-new.json` | served as a static file |

## In-app "What's new"

The pattern that works in most apps:

1. **An entry point that is always there**, e.g. "What's new" in the settings, help or about menu. It shows the full history from the JSON.
2. **An unread marker**, a dot on that entry, when the running version is newer than the last version the user viewed. Store `lastSeenVersion` locally: `localStorage` on the web, the app's settings store in desktop apps.
3. **Optionally, show it once after an update.** On first launch after an upgrade, open the view scrolled to the versions newer than `lastSeenVersion`. Keep it dismissible, and never show it on a fresh install (no `lastSeenVersion` means record the current version and stay quiet).
4. **Rendering:**
   - newest first;
   - version and date as the heading, then the summary;
   - entries grouped or tagged by type;
   - highlighted entries first and larger, since they're what the release is about;
   - breaking entries visually distinct;
   - plain text only, since the JSON has no Markdown beyond `code`.

Minimal React sketch (adapt to the app's components and styling):

```tsx
import { useEffect, useState } from "react";
import data from "./whats-new.json";

const KEY = "whatsNew.lastSeenVersion";
const parts = (v: string) => v.split("-")[0].split(".").map(Number);
export const isNewer = (a: string, b: string) => {
  const [x, y] = [parts(a), parts(b)];
  for (let i = 0; i < 3; i++) if (x[i] !== y[i]) return x[i] > y[i];
  return false;
};

export function useWhatsNew(currentVersion: string) {
  const [lastSeen, setLastSeen] = useState(() => localStorage.getItem(KEY));
  useEffect(() => {
    // Fresh install: remember the current version and announce nothing.
    if (!lastSeen) { localStorage.setItem(KEY, currentVersion); setLastSeen(currentVersion); }
  }, [lastSeen, currentVersion]);
  const unseen = lastSeen ? data.versions.filter(v => isNewer(v.version, lastSeen)) : [];
  const markSeen = () => { localStorage.setItem(KEY, currentVersion); setLastSeen(currentVersion); };
  return { versions: data.versions, unseen, hasUnseen: unseen.length > 0, markSeen };
}
```

- **Tauri:** get the running version with `getVersion()` from `@tauri-apps/api/app`. It comes from tauri.conf.json, which `bump` keeps in sync. Put the entry next to the existing settings or about dialog.
- **Web apps:** the version can come from `import.meta.env` or `package.json` at build time.
- **Python web UIs** (e.g. a local dashboard): serve the JSON next to the page and render the same structure in plain JS.

Keep the copy human. The fragment texts are already written for users, so show them as they are.

## GitHub Releases (optional)

Offer this only when the repo has a GitHub remote and the user publishes there. After the release commit and tag, and only on explicit request:

```sh
python3 <skill_dir>/scripts/changelogger.py notes 2.0.0 > /tmp/notes.md
gh release create v2.0.0 --title "v2.0.0" --notes-file /tmp/notes.md   # add --draft to review on GitHub first
```

- `notes` prints the summary plus the user-audience entries grouped by type. `--audience all` includes internal ones, for library releases whose users read everything.
- `gh release create` publishes immediately, notifies watchers, and may trigger release workflows.
- Suggest `--draft` the first time.
