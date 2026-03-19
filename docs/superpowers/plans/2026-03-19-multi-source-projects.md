# Multi-Source Projects Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve Slack Mirror from single-source workspaces to multi-source projects supporting Slack and Teams, with vault index files and migration from the old data model.

**Architecture:** Projects contain N sources (Slack/Teams). Each source syncs independently via its own Playwright browser instance. Python backend receives all config via env vars, routes to the correct scraper, and writes to namespaced vault paths. Electron app manages project/source CRUD with a tree sidebar.

**Tech Stack:** Python 3.8+ (Playwright, python-dotenv), Electron 41, Obsidian CLI

**Spec:** `docs/superpowers/specs/2026-03-19-multi-source-projects-design.md`

---

## File Structure

### Python Backend (`slack_mirror/`)

| File | Action | Responsibility |
|------|--------|---------------|
| `config.py` | Modify | New env vars: `SOURCE_TYPE`, `SOURCE_ID`, `PROJECT_ID`, `PROJECT_NAME`, `SOURCE_LABEL`, `SOURCE_URL`, `SYNC_DMS`, `SYNC_GROUPS`, `SOURCE_DIR` |
| `utils.py` | Create | Shared `resolve_date()` extracted from scraper |
| `slack_scraper.py` | Create (rename) | Rename `scraper.py`, update imports to use `utils.resolve_date` and `config.SOURCE_URL` |
| `scraper.py` | Delete | Replaced by `slack_scraper.py` |
| `teams_scraper.py` | Create | Teams DOM scraper, same interface as `slack_scraper.py` |
| `auth.py` | Modify | Use `SOURCE_URL` instead of `SLACK_WORKSPACE_URL` |
| `obsidian_writer.py` | Modify | Namespaced paths, index file generation |
| `main.py` | Modify | Route by `SOURCE_TYPE`, gate DM/group sync, pass project/source to writer |
| `sync_state.py` | No change | Already generic |

### Electron App (`slack_mirror_app/`)

| File | Action | Responsibility |
|------|--------|---------------|
| `main.js` | Modify | Projects/sources CRUD, migration, updated IPC, new env vars for spawn |
| `preload.js` | Modify | New API methods for projects/sources |
| `index.html` | Modify | Tree sidebar, source-level panels, project-level panel |

### Docs

| File | Action |
|------|--------|
| `README.md` | Modify | Update for projects/sources/Teams |

---

## Task 1: Extract `utils.py` from scraper

**Files:**
- Create: `slack_mirror/utils.py`
- Modify: `slack_mirror/scraper.py:11-37`

- [ ] **Step 1: Create `utils.py` with `resolve_date()`**

Extract the `_resolve_date` function from `scraper.py` into a shared utility:

```python
"""Shared utilities for scrapers."""
import re
from datetime import datetime, timedelta


def resolve_date(date_str: str) -> str:
    """Convert relative dates (Today, Yesterday) to YYYY-MM-DD format."""
    today = datetime.now()
    lower = date_str.lower().strip()

    if lower == "today":
        return today.strftime("%Y-%m-%d")
    if lower == "yesterday":
        return (today - timedelta(days=1)).strftime("%Y-%m-%d")

    # Try to parse dates like "Sunday, March 15th" or "Mar 15th"
    cleaned = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str)
    cleaned = re.sub(r'^\w+day,?\s*', '', cleaned)

    for fmt in ("%B %d", "%b %d", "%B %d, %Y", "%b %d, %Y"):
        try:
            parsed = datetime.strptime(cleaned.strip(), fmt)
            if parsed.year == 1900:
                parsed = parsed.replace(year=today.year)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return date_str
```

- [ ] **Step 2: Update `scraper.py` to import from utils**

In `scraper.py`, replace the `_resolve_date` function definition (lines 11-37) with:

```python
from utils import resolve_date
```

And update the call site at line 93 from `_resolve_date(date_str)` to `resolve_date(date_str)`.

- [ ] **Step 3: Verify scraper still works**

Run: `cd slack_mirror && python -c "from scraper import scrape_all; print('import ok')"`
Expected: `import ok`

- [ ] **Step 4: Commit**

```bash
git add slack_mirror/utils.py slack_mirror/scraper.py
git commit -m "refactor: extract resolve_date to shared utils"
```

---

## Task 2: Rename `scraper.py` to `slack_scraper.py`

**Files:**
- Rename: `slack_mirror/scraper.py` → `slack_mirror/slack_scraper.py`
- Modify: `slack_mirror/main.py:12`

- [ ] **Step 1: Rename the file**

```bash
cd slack_mirror && git mv scraper.py slack_scraper.py
```

- [ ] **Step 2: Update import in `main.py`**

Change line 12 of `main.py` from:
```python
from scraper import scrape_all
```
to:
```python
from slack_scraper import scrape_all
```

- [ ] **Step 3: Verify imports**

Run: `cd slack_mirror && python -c "from main import main; print('import ok')"`
Expected: `import ok`

- [ ] **Step 4: Commit**

```bash
git add slack_mirror/slack_scraper.py slack_mirror/main.py
git commit -m "refactor: rename scraper.py to slack_scraper.py"
```

---

## Task 3: Update `config.py` for multi-source

**Files:**
- Modify: `slack_mirror/config.py` (full rewrite, 28 lines → ~35 lines)

- [ ] **Step 1: Rewrite config.py**

Replace the entire contents of `slack_mirror/config.py` with:

```python
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent

# Source configuration (passed by Electron or set manually)
SOURCE_TYPE = os.getenv("SOURCE_TYPE", "slack")  # "slack" or "teams"
SOURCE_ID = os.getenv("SOURCE_ID", "default")
PROJECT_ID = os.getenv("PROJECT_ID", "default")
PROJECT_NAME = os.getenv("PROJECT_NAME", "Default")
SOURCE_LABEL = os.getenv("SOURCE_LABEL", "default")
SOURCE_URL = os.getenv("SOURCE_URL", os.getenv("SLACK_WORKSPACE_URL", "https://app.slack.com"))
OBSIDIAN_VAULT = os.getenv("OBSIDIAN_VAULT", "my-vault")

# Sync toggles
SYNC_DMS = os.getenv("SYNC_DMS", "true").lower() == "true"
SYNC_GROUPS = os.getenv("SYNC_GROUPS", "true").lower() == "true"

# Channels (comma-separated)
CHANNELS = [c.strip() for c in os.getenv("CHANNELS", "general").split(",") if c.strip()]

# Source directory for state files (auth, sync_state)
if os.getenv("SOURCE_DIR"):
    SOURCE_DIR = Path(os.getenv("SOURCE_DIR"))
elif os.getenv("WORKSPACE_DIR"):
    # Backward compat for migration period
    SOURCE_DIR = Path(os.getenv("WORKSPACE_DIR"))
else:
    SOURCE_DIR = BASE_DIR / "workspaces" / SOURCE_ID

SOURCE_DIR.mkdir(parents=True, exist_ok=True)

AUTH_STATE_PATH = SOURCE_DIR / "auth.json"
SYNC_STATE_PATH = SOURCE_DIR / "sync_state.json"
```

- [ ] **Step 2: Verify imports still work**

Run: `cd slack_mirror && python -c "from config import SOURCE_TYPE, SOURCE_URL, AUTH_STATE_PATH, SYNC_DMS; print(SOURCE_TYPE, SOURCE_URL, SYNC_DMS)"`
Expected: `slack https://app.slack.com True`

- [ ] **Step 3: Commit**

```bash
git add slack_mirror/config.py
git commit -m "feat: update config.py for multi-source project model"
```

---

## Task 4: Update `auth.py` to use `SOURCE_URL`

**Files:**
- Modify: `slack_mirror/auth.py:11,29`

- [ ] **Step 1: Update imports**

Change line 11 of `auth.py` from:
```python
from config import AUTH_STATE_PATH, SLACK_WORKSPACE_URL, WORKSPACE_DIR
```
to:
```python
from config import AUTH_STATE_PATH, SOURCE_URL, SOURCE_DIR
```

- [ ] **Step 2: Update SIGNAL_FILE path**

Change line 14 from:
```python
SIGNAL_FILE = WORKSPACE_DIR / ".auth_done"
```
to:
```python
SIGNAL_FILE = SOURCE_DIR / ".auth_done"
```

- [ ] **Step 3: Update page.goto call**

Change line 29 from:
```python
page.goto(SLACK_WORKSPACE_URL)
```
to:
```python
page.goto(SOURCE_URL)
```

- [ ] **Step 4: Update print message**

Change line 31 from:
```python
print("\n=== Slack Login ===")
```
to:
```python
print(f"\n=== Login ({SOURCE_URL}) ===")
```

- [ ] **Step 5: Verify**

Run: `cd slack_mirror && python -c "from auth import login_and_save_session; print('import ok')"`
Expected: `import ok`

- [ ] **Step 6: Commit**

```bash
git add slack_mirror/auth.py
git commit -m "feat: update auth.py to use generic SOURCE_URL"
```

---

## Task 5: Update `slack_scraper.py` imports

**Files:**
- Modify: `slack_mirror/slack_scraper.py:8`

- [ ] **Step 1: Update imports**

Change line 8 of `slack_scraper.py` from:
```python
from config import AUTH_STATE_PATH, SLACK_WORKSPACE_URL, CHANNELS
```
to:
```python
from config import AUTH_STATE_PATH, SOURCE_URL, CHANNELS
```

- [ ] **Step 2: Update URL references**

Change line 249 from:
```python
page.goto(SLACK_WORKSPACE_URL, wait_until="domcontentloaded", timeout=60000)
```
to:
```python
page.goto(SOURCE_URL, wait_until="domcontentloaded", timeout=60000)
```

- [ ] **Step 3: Verify**

Run: `cd slack_mirror && python -c "from slack_scraper import scrape_all; print('import ok')"`
Expected: `import ok`

- [ ] **Step 4: Commit**

```bash
git add slack_mirror/slack_scraper.py
git commit -m "feat: update slack_scraper to use SOURCE_URL"
```

---

## Task 6: Update `obsidian_writer.py` for namespaced paths and index files

**Files:**
- Modify: `slack_mirror/obsidian_writer.py` (full rewrite)

- [ ] **Step 1: Rewrite obsidian_writer.py**

Replace the entire contents with:

```python
"""
Writes scraped messages to Obsidian vault via the obsidian CLI.
Supports namespaced paths: {project_name}/{source_prefix}/channels|dms|groups/
"""
import subprocess
from config import OBSIDIAN_VAULT


def _run_obsidian(args: str) -> str:
    cmd = f'obsidian vault="{OBSIDIAN_VAULT}" {args}'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip()


def _file_exists(path: str) -> bool:
    result = _run_obsidian(f'read path="{path}"')
    return bool(result) and "Error" not in result


def _ensure_file(path: str, title: str, description: str = "Auto-synced messages."):
    if not _file_exists(path):
        header = f"# {title}\\n\\n{description}"
        _run_obsidian(f'create path="{path}" content="{header}" silent')


def format_messages(messages: list[dict]) -> str:
    """Format messages as markdown text for appending."""
    lines = []
    current_date = None

    for msg in messages:
        date = msg.get("date", "Unknown date")
        if date != current_date:
            lines.append(f"\\n### {date}\\n")
            current_date = date

        author = msg.get("author", "Unknown")
        time_str = msg.get("time", "")
        text = msg.get("text", "").replace('"', '\\"').replace("\n", "\\n")

        timestamp = f"{date} {time_str}".strip()
        lines.append(f"**{timestamp} - {author}** : {text}\\n")

    return "\\n".join(lines)


def _build_path(project_name: str, source_prefix: str, category: str, name: str) -> str:
    """Build vault path: {project}/{source_prefix}/{category}/{name}.md
    For Teams sources, DMs use 'chats/' instead of 'dms/'."""
    safe_name = name.replace("/", "-")
    # Teams uses "chats" for DMs per spec
    if category == "dms" and source_prefix.startswith("teams-"):
        category = "chats"
    if project_name and source_prefix:
        return f"{project_name}/{source_prefix}/{category}/{safe_name}.md"
    # Fallback for legacy mode (no project context)
    return f"slack/{category}/{safe_name}.md"


def write_channel_messages(channel_name: str, messages: list[dict],
                           project_name: str = "", source_prefix: str = ""):
    if not messages:
        return
    path = _build_path(project_name, source_prefix, "channels", channel_name)
    _ensure_file(path, f"#{channel_name}")
    content = format_messages(messages)
    _run_obsidian(f'append path="{path}" content="{content}"')


def write_dm_messages(person_name: str, messages: list[dict],
                      project_name: str = "", source_prefix: str = ""):
    if not messages:
        return
    path = _build_path(project_name, source_prefix, "dms", person_name)
    _ensure_file(path, f"DM — {person_name}")
    content = format_messages(messages)
    _run_obsidian(f'append path="{path}" content="{content}"')


def write_group_messages(group_name: str, messages: list[dict],
                         project_name: str = "", source_prefix: str = ""):
    if not messages:
        return
    path = _build_path(project_name, source_prefix, "groups", group_name)
    _ensure_file(path, f"Group — {group_name}")
    content = format_messages(messages)
    _run_obsidian(f'append path="{path}" content="{content}"')


def write_source_index(project_name: str, source_prefix: str, source_label: str,
                       channels: list[str], dms: list[str], groups: list[str]):
    """Write/overwrite the source index file with wikilinks to all conversations."""
    if not project_name or not source_prefix:
        return

    path = f"{project_name}/{source_prefix}/index.md"
    base = f"{project_name}/{source_prefix}"
    # Teams uses "chats" folder, Slack uses "dms"
    dm_folder = "chats" if source_prefix.startswith("teams-") else "dms"
    dm_label = "Chats" if source_prefix.startswith("teams-") else "Direct Messages"

    lines = [f"# {source_label}", ""]

    if channels:
        lines.append("## Channels")
        for ch in sorted(channels):
            lines.append(f"- [[{base}/channels/{ch}|#{ch}]]")
        lines.append("")

    if dms:
        lines.append(f"## {dm_label}")
        for dm in sorted(dms):
            lines.append(f"- [[{base}/{dm_folder}/{dm}|{dm}]]")
        lines.append("")

    if groups:
        lines.append("## Groups")
        for g in sorted(groups):
            lines.append(f"- [[{base}/groups/{g}|{g}]]")
        lines.append("")

    content = "\\n".join(lines).replace('"', '\\"')

    # Overwrite the index file
    if _file_exists(path):
        _run_obsidian(f'delete path="{path}" silent')
    _run_obsidian(f'create path="{path}" content="{content}" silent')


def write_project_index(project_name: str, sources: list[dict]):
    """Write/overwrite the project index file with links to all sources.

    sources: list of {"prefix": "slack-acme", "label": "Slack - Acme"}
    """
    if not project_name:
        return

    path = f"{project_name}/index.md"

    lines = [f"# {project_name}", "", "## Sources", ""]
    for src in sources:
        prefix = src["prefix"]
        label = src["label"]
        lines.append(f"### [[{project_name}/{prefix}/index|{label}]]")

    lines.append("")
    content = "\\n".join(lines).replace('"', '\\"')

    if _file_exists(path):
        _run_obsidian(f'delete path="{path}" silent')
    _run_obsidian(f'create path="{path}" content="{content}" silent')
```

- [ ] **Step 2: Verify imports**

Run: `cd slack_mirror && python -c "from obsidian_writer import write_channel_messages, write_source_index, write_project_index; print('import ok')"`
Expected: `import ok`

- [ ] **Step 3: Commit**

```bash
git add slack_mirror/obsidian_writer.py
git commit -m "feat: update obsidian_writer for namespaced paths and index files"
```

---

## Task 7: Update `main.py` for multi-source routing

**Files:**
- Modify: `slack_mirror/main.py` (full rewrite)

- [ ] **Step 1: Rewrite main.py**

Replace the entire contents of `slack_mirror/main.py` with:

```python
"""
Multi-Source → Obsidian Mirror
Scrapes messages from Slack or Teams and writes them to an Obsidian vault.

Usage:
    python main.py              # Sync new messages only
    python main.py --history    # First run: load all historical messages

Configuration via environment variables:
    SOURCE_TYPE     - "slack" or "teams"
    PROJECT_NAME    - project name for vault path
    SOURCE_LABEL    - source label for vault path
    SOURCE_URL      - workspace/tenant URL
    OBSIDIAN_VAULT  - target Obsidian vault
    CHANNELS        - comma-separated channel names
    SYNC_DMS        - "true"/"false"
    SYNC_GROUPS     - "true"/"false"
"""
import argparse
import sys
from config import AUTH_STATE_PATH, SOURCE_TYPE, PROJECT_NAME, SOURCE_LABEL, SYNC_DMS, SYNC_GROUPS
from obsidian_writer import (
    write_channel_messages, write_dm_messages, write_group_messages,
    write_source_index, write_project_index,
)
from sync_state import filter_new_messages, get_latest_timestamp, update_last_message_ts


def _get_scraper():
    """Import the correct scraper based on SOURCE_TYPE."""
    if SOURCE_TYPE == "teams":
        from teams_scraper import scrape_all
    else:
        from slack_scraper import scrape_all
    return scrape_all


def _source_prefix() -> str:
    """Build source prefix for vault paths: e.g., 'slack-acme'."""
    return f"{SOURCE_TYPE}-{SOURCE_LABEL}" if SOURCE_LABEL else SOURCE_TYPE


def sync_messages(category_name: str, conv_name: str, all_messages: list[dict],
                  writer_fn, project_name: str, source_prefix: str):
    """Filter new messages and write them. Returns count of new messages."""
    conv_id = f"{category_name}:{conv_name}"
    new_messages = filter_new_messages(conv_id, all_messages)

    if new_messages:
        writer_fn(conv_name, new_messages, project_name=project_name, source_prefix=source_prefix)
        latest_ts = get_latest_timestamp(new_messages)
        if latest_ts:
            update_last_message_ts(conv_id, latest_ts)
        print(f"  {conv_id}: {len(new_messages)} new messages (of {len(all_messages)} total)")
    else:
        print(f"  {conv_id}: no new messages")

    return len(new_messages)


def main():
    parser = argparse.ArgumentParser(description="Multi-Source → Obsidian mirror")
    parser.add_argument("--history", action="store_true", help="Load historical messages (first run)")
    args = parser.parse_args()

    if not AUTH_STATE_PATH.exists():
        print("No saved session found. Run auth.py first to log in.")
        sys.exit(1)

    scrape_all = _get_scraper()
    prefix = _source_prefix()

    print(f"Scraping {SOURCE_TYPE} ({SOURCE_LABEL})...")
    data = scrape_all(load_history=args.history)

    total_new = 0

    # Write channels
    for name, messages in data["channels"].items():
        total_new += sync_messages("channel", name, messages, write_channel_messages, PROJECT_NAME, prefix)

    # Write DMs (if enabled)
    if SYNC_DMS:
        for name, messages in data["dms"].items():
            total_new += sync_messages("dm", name, messages, write_dm_messages, PROJECT_NAME, prefix)

    # Write group DMs (if enabled)
    if SYNC_GROUPS:
        for name, messages in data["groups"].items():
            total_new += sync_messages("group", name, messages, write_group_messages, PROJECT_NAME, prefix)

    # Update index files if we have project context
    if PROJECT_NAME and prefix:
        all_channels = list(data["channels"].keys())
        all_dms = list(data["dms"].keys()) if SYNC_DMS else []
        all_groups = list(data["groups"].keys()) if SYNC_GROUPS else []

        write_source_index(PROJECT_NAME, prefix, f"{SOURCE_TYPE.title()} - {SOURCE_LABEL}",
                           all_channels, all_dms, all_groups)

        # Generate project index if we have the sources list
        import os, json
        sources_json = os.getenv("SOURCES_JSON", "")
        if sources_json:
            try:
                sources = json.loads(sources_json)
                project_sources = [
                    {"prefix": f"{s['type']}-{s['label']}", "label": f"{s['type'].title()} - {s['label']}"}
                    for s in sources
                ]
                write_project_index(PROJECT_NAME, project_sources)
            except (json.JSONDecodeError, KeyError):
                pass

    total_scraped = sum(
        len(msgs)
        for category in data.values()
        for msgs in category.values()
    )
    print(f"\nDone! {total_new} new messages synced (of {total_scraped} scraped).")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify imports**

Run: `cd slack_mirror && python -c "from main import main; print('import ok')"`
Expected: `import ok`

- [ ] **Step 3: Commit**

```bash
git add slack_mirror/main.py
git commit -m "feat: update main.py for multi-source routing with sync toggles"
```

---

## Task 8: Create `teams_scraper.py`

**Files:**
- Create: `slack_mirror/teams_scraper.py`

**Note:** Teams DOM selectors are a best-effort starting point. They will need refinement against a live Teams instance during testing. The structure and interface match `slack_scraper.py` exactly.

- [ ] **Step 1: Create teams_scraper.py**

```python
"""
Playwright-based Microsoft Teams scraper.
Reads messages from channels, 1:1 chats, and group chats.

NOTE: Teams DOM selectors may need adjustment as Microsoft updates
the Teams web client. Test against a live Teams instance.
"""
import re
from playwright.sync_api import sync_playwright, Page, BrowserContext
from config import AUTH_STATE_PATH, SOURCE_URL, CHANNELS
from utils import resolve_date


def _create_context(playwright) -> BrowserContext:
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(storage_state=str(AUTH_STATE_PATH))
    return context


def _wait_for_teams(page: Page):
    """Wait for Teams to fully load."""
    # Teams app container
    page.wait_for_selector('[data-tid="app-layout"]', timeout=60000)
    page.wait_for_timeout(5000)


def _extract_messages(page: Page) -> list[dict]:
    """Extract visible messages from the current Teams conversation."""
    messages = []
    current_date = ""

    # Teams messages are in message containers
    message_elements = page.query_selector_all('[data-tid="chat-pane-message"]')
    if not message_elements:
        # Fallback selector for newer Teams client
        message_elements = page.query_selector_all('[role="listitem"]')

    for el in message_elements:
        try:
            # Check for date divider
            divider = el.query_selector('[data-tid="message-group-date-header"]')
            if not divider:
                divider = el.query_selector('.ui-chat__message__dateDivider')
            if divider:
                current_date = divider.inner_text().strip()
                continue

            # Get author
            author_el = el.query_selector('[data-tid="message-author-name"]')
            if not author_el:
                author_el = el.query_selector('.ui-chat__message__author')
            author = author_el.inner_text().strip() if author_el else None

            # Get timestamp
            time_el = el.query_selector('[data-tid="message-timestamp"]')
            if not time_el:
                time_el = el.query_selector('time')
            time_str = ""
            date_str = current_date
            if time_el:
                # Teams timestamps vary: "3:45 PM", "Yesterday 3:45 PM", etc.
                raw_time = time_el.get_attribute("aria-label") or time_el.inner_text().strip()
                if raw_time:
                    # Split date and time parts
                    time_match = re.search(r'(\d+:\d+(?::\d+)?\s*[AP]M)', raw_time, re.IGNORECASE)
                    if time_match:
                        time_str = time_match.group(1)
                        date_part = raw_time[:time_match.start()].strip()
                        if date_part:
                            date_str = date_part

            # Resolve date
            date_str = resolve_date(date_str)

            # Convert 12h time to 24h
            time_clean = time_str
            time_24h_match = re.match(r'(\d+):(\d+):?(\d+)?\s*([AP]M)', time_str, re.IGNORECASE)
            if time_24h_match:
                h = int(time_24h_match.group(1))
                m = int(time_24h_match.group(2))
                s = int(time_24h_match.group(3) or 0)
                ampm = time_24h_match.group(4).upper()
                if ampm == "PM" and h != 12:
                    h += 12
                elif ampm == "AM" and h == 12:
                    h = 0
                time_clean = f"{h:02d}:{m:02d}:{s:02d}"

            # Get message text
            text_el = el.query_selector('[data-tid="message-body"]')
            if not text_el:
                text_el = el.query_selector('.ui-chat__message__content')
            if not text_el:
                text_el = el.query_selector('[role="document"]')
            text = text_el.inner_text().strip() if text_el else ""

            if not text:
                continue

            messages.append({
                "author": author or "Unknown",
                "date": date_str or "Unknown date",
                "time": time_clean or time_str,
                "text": text,
            })
        except Exception:
            continue

    return messages


def _scroll_to_load_history(page: Page, max_scrolls: int = 50):
    """Scroll up to load historical messages in Teams."""
    for _ in range(max_scrolls):
        page.evaluate("""
            const container = document.querySelector('[data-tid="message-pane-list-container"]')
                || document.querySelector('[role="main"] [role="list"]');
            if (container) container.scrollTop = 0;
        """)
        page.wait_for_timeout(1500)

        body_text = page.inner_text("body")
        if "This is the beginning" in body_text or "started this conversation" in body_text:
            break


def scrape_conversation(page: Page, load_history: bool = False) -> list[dict]:
    """Scrape messages from the currently open Teams conversation."""
    page.wait_for_timeout(3000)

    if load_history:
        _scroll_to_load_history(page)
        page.wait_for_timeout(2000)

    return _extract_messages(page)


def _click_sidebar_item(page: Page, name: str) -> bool:
    """Click a channel or chat in the Teams sidebar by name."""
    # Try finding by text in the sidebar
    items = page.query_selector_all('[data-tid="team-channel-item"], [role="treeitem"]')
    for item in items:
        try:
            item_text = item.inner_text().strip()
            if name.lower() in item_text.lower():
                item.click()
                page.wait_for_timeout(3000)
                return True
        except Exception:
            continue
    return False


def _navigate_to_teams_section(page: Page):
    """Click the Teams icon in the left rail to show team channels."""
    teams_btn = page.query_selector('[data-tid="app-bar-Teams"]')
    if not teams_btn:
        teams_btn = page.query_selector('[aria-label="Teams"]')
    if teams_btn:
        teams_btn.click()
        page.wait_for_timeout(2000)


def _navigate_to_chat_section(page: Page):
    """Click the Chat icon in the left rail to show chats."""
    chat_btn = page.query_selector('[data-tid="app-bar-Chat"]')
    if not chat_btn:
        chat_btn = page.query_selector('[aria-label="Chat"]')
    if chat_btn:
        chat_btn.click()
        page.wait_for_timeout(2000)


def _get_chat_names(page: Page) -> list[dict]:
    """Get chat conversation names and types from the Chat section.
    Returns list of {"name": str, "is_group": bool}."""
    chats = []
    chat_items = page.query_selector_all('[data-tid="chat-list-item"]')
    if not chat_items:
        chat_items = page.query_selector_all('[role="listitem"]')

    for item in chat_items:
        try:
            name = item.inner_text().strip().split("\n")[0]
            if not name:
                continue
            is_group = "," in name or "and" in name.lower()
            chats.append({"name": name, "is_group": is_group})
        except Exception:
            continue

    return chats


def scrape_channels(page: Page, channel_names: list[str], load_history: bool = False) -> dict:
    """Scrape specified Teams channels. Returns {channel_name: [messages]}."""
    results = {}
    _navigate_to_teams_section(page)

    for name in channel_names:
        print(f"  Opening Teams channel {name}...")
        if _click_sidebar_item(page, name):
            messages = scrape_conversation(page, load_history=load_history)
            results[name] = messages
            print(f"  Found {len(messages)} messages in {name}")
        else:
            print(f"  Could not find Teams channel {name}")

    return results


def scrape_all(load_history: bool = False) -> dict:
    """
    Scrape everything from Teams: channels, 1:1 chats, group chats.
    Returns {"channels": {...}, "dms": {...}, "groups": {...}}
    """
    with sync_playwright() as p:
        context = _create_context(p)
        page = context.new_page()

        print("  Loading Teams...")
        page.goto(SOURCE_URL, wait_until="domcontentloaded", timeout=60000)
        _wait_for_teams(page)
        print("  Teams loaded!")

        # Scrape channels
        print("\n  --- Teams Channels ---")
        channels = scrape_channels(page, CHANNELS, load_history=load_history)

        # Scrape chats
        print("\n  --- Teams Chats ---")
        _navigate_to_chat_section(page)
        all_chats = _get_chat_names(page)

        individual_chats = {}
        group_chats = {}

        for chat in all_chats:
            name = chat["name"]
            print(f"  Opening chat with {name}...")
            if _click_sidebar_item(page, name):
                messages = scrape_conversation(page, load_history=load_history)
                if messages:
                    if chat["is_group"]:
                        group_chats[name] = messages
                    else:
                        individual_chats[name] = messages
                    print(f"  Found {len(messages)} messages with {name}")

        context.close()

        return {
            "channels": channels,
            "dms": individual_chats,
            "groups": group_chats,
        }
```

- [ ] **Step 2: Verify imports**

Run: `cd slack_mirror && python -c "from teams_scraper import scrape_all; print('import ok')"`
Expected: `import ok`

- [ ] **Step 3: Commit**

```bash
git add slack_mirror/teams_scraper.py
git commit -m "feat: add Teams scraper with same interface as Slack scraper"
```

---

## Task 9: Update Electron `main.js` — data model and migration

**Files:**
- Modify: `slack_mirror_app/main.js` (significant rewrite)

This is the largest task. The full rewrite covers: projects/sources CRUD, migration, updated sync/auth spawning with new env vars, updated logging keyed by `projectId-sourceId`.

- [ ] **Step 1: Rewrite main.js**

Replace the entire contents of `slack_mirror_app/main.js` with:

```javascript
const { app, BrowserWindow, ipcMain, Tray, Menu, nativeImage } = require("electron");
const path = require("path");
const { spawn } = require("child_process");
const fs = require("fs");

// Paths adapt to dev vs packaged mode
const IS_PACKAGED = app.isPackaged;

const SCRAPER_DIR = IS_PACKAGED
  ? path.join(process.resourcesPath, "scraper")
  : path.join(__dirname, "..", "slack_mirror");

// User data dir for configs (survives updates)
const USER_DATA_DIR = path.join(app.getPath("userData"), "data");
if (!fs.existsSync(USER_DATA_DIR)) fs.mkdirSync(USER_DATA_DIR, { recursive: true });

const PROJECTS_CONFIG_PATH = path.join(USER_DATA_DIR, "projects.json");
const PROJECTS_DIR = path.join(USER_DATA_DIR, "projects");
if (!fs.existsSync(PROJECTS_DIR)) fs.mkdirSync(PROJECTS_DIR, { recursive: true });

// Legacy paths for migration
const LEGACY_WORKSPACES_CONFIG = path.join(USER_DATA_DIR, "workspaces.json");
const LEGACY_WORKSPACES_DIR = path.join(USER_DATA_DIR, "workspaces");

let mainWindow;
let tray = null;

// Per-source state: { "projectId-sourceId": { interval, process, logs } }
const sourceState = {};

// Global logs
let logs = [];

// --- Window ---

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 960,
    height: 700,
    resizable: true,
    titleBarStyle: "hiddenInset",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.loadFile("index.html");

  mainWindow.on("close", (e) => {
    e.preventDefault();
    mainWindow.hide();
  });
}

function createTray() {
  const icon = nativeImage.createFromDataURL(
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABHNCSVQICAgIfAhkiAAAAAlwSFlzAAAAdgAAAHYBTnsmCAAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoAAADjSURBVDiNpZMxDoJAEEX/LAkFhYWVHdfwCHoCj+NRvIGx0MQCG+9gZWFBAmFn/RYssCzq62Yyf/68zCQDfBlJ5z0ASafnlPQWwIr0FsCW9Kau60Hf92VJN8AijuNz3/cPcRwfq6p6T5Kkm82mBkA7qiTPQRAkAK6dc/tF36qq6pxlmV5x0g1J5xERETMfmfluxzYDcBiGYZFlmQLwnKbpPgzD26LjIh+NRvsoimoAbwBeq8cNyd00TV/SNK2XNj8AWJI+Bda6SzOAveu6PYD7OI53fy2wxv7Llsjsz/gAfAA+L1YT2bYJJwAAAABJRU5ErkJggg=="
  );
  tray = new Tray(icon);
  tray.setToolTip("Slack Mirror");

  const contextMenu = Menu.buildFromTemplate([
    { label: "Show", click: () => mainWindow.show() },
    { type: "separator" },
    { label: "Quit", click: () => { app.exit(0); } },
  ]);
  tray.setContextMenu(contextMenu);
  tray.on("click", () => mainWindow.show());
}

app.whenReady().then(async () => {
  // Run migration before anything else
  migrateWorkspacesToProjects();

  createWindow();
  createTray();

  if (IS_PACKAGED) {
    await ensurePythonSetup();
  }

  // Auto-start all enabled sources
  const projects = loadProjects();
  for (const proj of projects) {
    for (const src of proj.sources || []) {
      if (src.autoSync) {
        startSourceSync(proj.id, src.id);
      }
    }
  }
});

async function ensurePythonSetup() {
  const venvDir = path.join(USER_DATA_DIR, "venv");
  const venvPython = path.join(venvDir, "bin", "python");

  if (fs.existsSync(venvPython)) return;

  addLog("system", "system", "First run: setting up Python environment...");

  return new Promise((resolve) => {
    const setup = spawn("python3", ["-m", "venv", venvDir]);
    setup.on("close", () => {
      const install = spawn(venvPython, ["-m", "pip", "install", "playwright", "python-dotenv"]);
      install.on("close", () => {
        const pw = spawn(venvPython, ["-m", "playwright", "install", "chromium"]);
        pw.on("close", () => {
          addLog("system", "system", "Python environment ready!");
          resolve();
        });
      });
    });
  });
}

function getPythonPath() {
  if (!IS_PACKAGED) {
    return path.join(SCRAPER_DIR, "venv", "bin", "python");
  }
  const venvPython = path.join(USER_DATA_DIR, "venv", "bin", "python");
  return fs.existsSync(venvPython) ? venvPython : "python3";
}

app.on("before-quit", () => {
  for (const key of Object.keys(sourceState)) {
    const [projectId, sourceId] = key.split("::");
    stopSourceSync(projectId, sourceId);
  }
});

// --- Migration ---

function migrateWorkspacesToProjects() {
  if (!fs.existsSync(LEGACY_WORKSPACES_CONFIG)) return;
  if (fs.existsSync(PROJECTS_CONFIG_PATH)) return; // Already migrated

  try {
    const workspaces = JSON.parse(fs.readFileSync(LEGACY_WORKSPACES_CONFIG, "utf-8"));
    const projects = [];

    for (const ws of workspaces) {
      const sourceId = "src-" + Date.now() + "-" + Math.random().toString(36).slice(2, 6);
      const project = {
        id: ws.id,
        name: ws.name,
        sources: [{
          id: sourceId,
          type: "slack",
          label: extractDomain(ws.slackUrl || ws.url || ""),
          url: ws.slackUrl || ws.url || "",
          vault: ws.vault || "",
          channels: ws.channels || "",
          intervalMinutes: ws.intervalMinutes || 30,
          autoSync: ws.autoSync || false,
          syncDMs: ws.syncDMs !== false,
          syncGroups: ws.syncGroups !== false,
        }],
      };
      projects.push(project);

      // Copy workspace data to new project/source directory
      const oldDir = path.join(LEGACY_WORKSPACES_DIR, ws.id);
      const newDir = path.join(PROJECTS_DIR, ws.id, sourceId);
      if (fs.existsSync(oldDir)) {
        fs.mkdirSync(newDir, { recursive: true });
        for (const file of fs.readdirSync(oldDir)) {
          fs.copyFileSync(path.join(oldDir, file), path.join(newDir, file));
        }
      }
    }

    fs.writeFileSync(PROJECTS_CONFIG_PATH, JSON.stringify(projects, null, 2));
    fs.renameSync(LEGACY_WORKSPACES_CONFIG, LEGACY_WORKSPACES_CONFIG + ".backup");

    console.log(`Migrated ${workspaces.length} workspaces to projects`);
  } catch (err) {
    console.error("Migration failed:", err);
  }
}

function extractDomain(url) {
  try {
    const hostname = new URL(url).hostname;
    // "acme.slack.com" -> "acme", "teams.microsoft.com" -> "teams"
    return hostname.split(".")[0];
  } catch {
    return "default";
  }
}

// --- Projects Config ---

function loadProjects() {
  try {
    return JSON.parse(fs.readFileSync(PROJECTS_CONFIG_PATH, "utf-8"));
  } catch {
    saveProjects([]);
    return [];
  }
}

function saveProjects(projects) {
  fs.writeFileSync(PROJECTS_CONFIG_PATH, JSON.stringify(projects, null, 2));
}

function getProject(projectId) {
  return loadProjects().find((p) => p.id === projectId);
}

function getSource(projectId, sourceId) {
  const proj = getProject(projectId);
  return proj?.sources?.find((s) => s.id === sourceId);
}

ipcMain.handle("get-projects", () => loadProjects());

ipcMain.handle("save-project", (_, project) => {
  const projects = loadProjects();
  const idx = projects.findIndex((p) => p.id === project.id);
  if (idx >= 0) {
    projects[idx] = project;
  } else {
    projects.push(project);
  }
  saveProjects(projects);
  return { ok: true };
});

ipcMain.handle("delete-project", (_, projectId) => {
  // Stop all sources in this project
  const proj = getProject(projectId);
  if (proj) {
    for (const src of proj.sources || []) {
      stopSourceSync(projectId, src.id);
    }
  }
  const projects = loadProjects().filter((p) => p.id !== projectId);
  saveProjects(projects);
  return { ok: true };
});

ipcMain.handle("add-source", (_, { projectId, source }) => {
  const projects = loadProjects();
  const proj = projects.find((p) => p.id === projectId);
  if (!proj) return { ok: false, error: "Project not found" };

  if (!proj.sources) proj.sources = [];

  // Enforce unique labels within a project
  const duplicate = proj.sources.find((s) => s.label === source.label);
  if (duplicate) return { ok: false, error: `Source label "${source.label}" already exists in this project` };

  proj.sources.push(source);
  saveProjects(projects);

  // Create source directory
  const srcDir = path.join(PROJECTS_DIR, projectId, source.id);
  if (!fs.existsSync(srcDir)) fs.mkdirSync(srcDir, { recursive: true });

  return { ok: true };
});

ipcMain.handle("delete-source", (_, { projectId, sourceId }) => {
  stopSourceSync(projectId, sourceId);
  const projects = loadProjects();
  const proj = projects.find((p) => p.id === projectId);
  if (proj) {
    proj.sources = (proj.sources || []).filter((s) => s.id !== sourceId);
    saveProjects(projects);
  }
  return { ok: true };
});

ipcMain.handle("save-source", (_, { projectId, source }) => {
  const projects = loadProjects();
  const proj = projects.find((p) => p.id === projectId);
  if (!proj) return { ok: false, error: "Project not found" };

  // Enforce unique labels within a project (excluding self)
  const duplicate = (proj.sources || []).find((s) => s.label === source.label && s.id !== source.id);
  if (duplicate) return { ok: false, error: `Source label "${source.label}" already exists in this project` };

  const idx = (proj.sources || []).findIndex((s) => s.id === source.id);
  if (idx >= 0) {
    proj.sources[idx] = source;
  }
  saveProjects(projects);

  const srcDir = path.join(PROJECTS_DIR, projectId, source.id);
  if (!fs.existsSync(srcDir)) fs.mkdirSync(srcDir, { recursive: true });

  return { ok: true };
});

// --- Logging ---

function sourceKey(projectId, sourceId) {
  return `${projectId}::${sourceId}`;
}

function addLog(projectId, sourceId, message) {
  const key = sourceKey(projectId, sourceId);
  const ts = new Date().toLocaleTimeString();
  const entry = `[${ts}] [${key}] ${message}`;
  logs.push(entry);
  if (logs.length > 500) logs.shift();

  if (!sourceState[key]) {
    sourceState[key] = { interval: null, process: null, logs: [] };
  }
  sourceState[key].logs.push(entry);
  if (sourceState[key].logs.length > 200) {
    sourceState[key].logs.shift();
  }

  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send("log", { projectId, sourceId, message: entry });
  }
}

ipcMain.handle("get-logs", (_, { projectId, sourceId }) => {
  const key = sourceKey(projectId, sourceId);
  if (sourceState[key]) {
    return sourceState[key].logs;
  }
  return [];
});

// --- Sync ---

function runSourceSync(projectId, sourceId) {
  const src = getSource(projectId, sourceId);
  const proj = getProject(projectId);
  if (!src || !proj) {
    addLog(projectId, sourceId, "Source or project not found!");
    return;
  }

  const key = sourceKey(projectId, sourceId);
  if (sourceState[key]?.process) {
    addLog(projectId, sourceId, "Sync already running, skipping...");
    return;
  }

  addLog(projectId, sourceId, "Starting sync...");

  const srcDir = path.join(PROJECTS_DIR, projectId, sourceId);
  if (!fs.existsSync(srcDir)) fs.mkdirSync(srcDir, { recursive: true });

  const env = {
    ...process.env,
    SOURCE_TYPE: src.type || "slack",
    SOURCE_ID: sourceId,
    PROJECT_ID: projectId,
    PROJECT_NAME: proj.name,
    SOURCE_LABEL: src.label || "default",
    SOURCE_URL: src.url || "",
    OBSIDIAN_VAULT: src.vault || "",
    CHANNELS: src.channels || "",
    SYNC_DMS: String(src.syncDMs !== false),
    SYNC_GROUPS: String(src.syncGroups !== false),
    SOURCE_DIR: srcDir,
    SOURCES_JSON: JSON.stringify(proj.sources || []),
  };

  if (!sourceState[key]) {
    sourceState[key] = { interval: null, process: null, logs: [] };
  }

  const proc = spawn(getPythonPath(), ["main.py"], { cwd: SCRAPER_DIR, env });
  sourceState[key].process = proc;

  proc.stdout.on("data", (data) => {
    data.toString().trim().split("\n").forEach((line) => addLog(projectId, sourceId, line));
  });

  proc.stderr.on("data", (data) => {
    data.toString().trim().split("\n").forEach((line) => addLog(projectId, sourceId, `ERROR: ${line}`));
  });

  proc.on("close", (code) => {
    addLog(projectId, sourceId, `Sync finished (exit code: ${code})`);
    if (sourceState[key]) {
      sourceState[key].process = null;
    }
    sendStatus(projectId, sourceId);
  });
}

function startSourceSync(projectId, sourceId) {
  const src = getSource(projectId, sourceId);
  if (!src) return;

  const key = sourceKey(projectId, sourceId);
  if (!sourceState[key]) {
    sourceState[key] = { interval: null, process: null, logs: [] };
  }

  if (sourceState[key].interval) {
    clearInterval(sourceState[key].interval);
  }

  const intervalMin = src.intervalMinutes || 30;

  runSourceSync(projectId, sourceId);

  sourceState[key].interval = setInterval(
    () => runSourceSync(projectId, sourceId),
    intervalMin * 60 * 1000
  );

  addLog(projectId, sourceId, `Auto-sync started: every ${intervalMin} minutes`);
  sendStatus(projectId, sourceId);
}

function stopSourceSync(projectId, sourceId) {
  const key = sourceKey(projectId, sourceId);
  const state = sourceState[key];
  if (!state) return;

  if (state.interval) {
    clearInterval(state.interval);
    state.interval = null;
  }
  if (state.process) {
    state.process.kill();
    state.process = null;
  }
  addLog(projectId, sourceId, "Sync stopped");
  sendStatus(projectId, sourceId);
}

function sendStatus(projectId, sourceId) {
  if (mainWindow && !mainWindow.isDestroyed()) {
    const key = sourceKey(projectId, sourceId);
    const state = sourceState[key];
    mainWindow.webContents.send("sync-status", {
      projectId,
      sourceId,
      running: !!state?.interval,
      syncing: !!state?.process,
    });
  }
}

ipcMain.handle("start-sync", (_, { projectId, sourceId }) => {
  startSourceSync(projectId, sourceId);
  return { ok: true };
});

ipcMain.handle("stop-sync", (_, { projectId, sourceId }) => {
  stopSourceSync(projectId, sourceId);
  return { ok: true };
});

ipcMain.handle("run-once", (_, { projectId, sourceId }) => {
  runSourceSync(projectId, sourceId);
  return { ok: true };
});

ipcMain.handle("get-status", (_, { projectId, sourceId }) => {
  const key = sourceKey(projectId, sourceId);
  const state = sourceState[key];
  return {
    running: !!state?.interval,
    syncing: !!state?.process,
  };
});

ipcMain.handle("get-all-statuses", () => {
  const statuses = {};
  const projects = loadProjects();
  for (const proj of projects) {
    for (const src of proj.sources || []) {
      const key = sourceKey(proj.id, src.id);
      const state = sourceState[key];
      statuses[key] = {
        projectId: proj.id,
        sourceId: src.id,
        running: !!state?.interval,
        syncing: !!state?.process,
      };
    }
  }
  return statuses;
});

// --- Auth ---

ipcMain.handle("run-auth", (_, { projectId, sourceId }) => {
  const src = getSource(projectId, sourceId);
  if (!src) return { ok: false, error: "Source not found" };

  addLog(projectId, sourceId, `Opening browser for ${src.type} login...`);

  const srcDir = path.join(PROJECTS_DIR, projectId, sourceId);
  if (!fs.existsSync(srcDir)) fs.mkdirSync(srcDir, { recursive: true });

  const env = {
    ...process.env,
    SOURCE_TYPE: src.type || "slack",
    SOURCE_ID: sourceId,
    PROJECT_ID: projectId,
    SOURCE_URL: src.url || "",
    OBSIDIAN_VAULT: src.vault || "",
    CHANNELS: src.channels || "",
    SOURCE_DIR: srcDir,
    DISPLAY: ":0",
  };

  const authProcess = spawn(getPythonPath(), ["auth.py", "--signal"], {
    cwd: SCRAPER_DIR,
    env,
  });

  authProcess.stdout.on("data", (data) => addLog(projectId, sourceId, data.toString().trim()));
  authProcess.stderr.on("data", (data) => addLog(projectId, sourceId, `AUTH: ${data.toString().trim()}`));
  authProcess.on("close", (code) => addLog(projectId, sourceId, `Auth finished (exit code: ${code})`));

  return { ok: true };
});

ipcMain.handle("signal-auth", (_, { projectId, sourceId }) => {
  const srcDir = path.join(PROJECTS_DIR, projectId, sourceId);
  if (!fs.existsSync(srcDir)) fs.mkdirSync(srcDir, { recursive: true });
  fs.writeFileSync(path.join(srcDir, ".auth_done"), "done");
  // Also write to scraper root for backward compat
  fs.writeFileSync(path.join(SCRAPER_DIR, ".auth_done"), "done");
  addLog(projectId, sourceId, "Auth signal sent — saving session...");
  return { ok: true };
});

// --- Login at startup ---

ipcMain.handle("set-login-at-startup", (_, enabled) => {
  app.setLoginItemSettings({ openAtLogin: enabled, openAsHidden: true });
  return { ok: true };
});

ipcMain.handle("get-login-at-startup", () => {
  return app.getLoginItemSettings().openAtLogin;
});
```

- [ ] **Step 2: Verify syntax**

Run: `cd slack_mirror_app && node -e "require('./main.js')" 2>&1 | head -5`

Note: This will fail because Electron APIs aren't available in plain Node, but it should NOT show syntax errors. A `TypeError: Cannot read...` or `ReferenceError: app is not defined` is expected and acceptable.

- [ ] **Step 3: Commit**

```bash
git add slack_mirror_app/main.js
git commit -m "feat: rewrite main.js for projects/sources model with migration"
```

---

## Task 10: Update `preload.js`

**Files:**
- Modify: `slack_mirror_app/preload.js` (full rewrite)

- [ ] **Step 1: Rewrite preload.js**

Replace the entire contents of `slack_mirror_app/preload.js` with:

```javascript
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("api", {
  // Projects
  getProjects: () => ipcRenderer.invoke("get-projects"),
  saveProject: (proj) => ipcRenderer.invoke("save-project", proj),
  deleteProject: (id) => ipcRenderer.invoke("delete-project", id),

  // Sources
  addSource: (projectId, source) => ipcRenderer.invoke("add-source", { projectId, source }),
  deleteSource: (projectId, sourceId) => ipcRenderer.invoke("delete-source", { projectId, sourceId }),
  saveSource: (projectId, source) => ipcRenderer.invoke("save-source", { projectId, source }),

  // Sync
  startSync: (projectId, sourceId) => ipcRenderer.invoke("start-sync", { projectId, sourceId }),
  stopSync: (projectId, sourceId) => ipcRenderer.invoke("stop-sync", { projectId, sourceId }),
  runOnce: (projectId, sourceId) => ipcRenderer.invoke("run-once", { projectId, sourceId }),
  getStatus: (projectId, sourceId) => ipcRenderer.invoke("get-status", { projectId, sourceId }),
  getAllStatuses: () => ipcRenderer.invoke("get-all-statuses"),

  // Auth
  runAuth: (projectId, sourceId) => ipcRenderer.invoke("run-auth", { projectId, sourceId }),
  signalAuth: (projectId, sourceId) => ipcRenderer.invoke("signal-auth", { projectId, sourceId }),

  // Logs
  getLogs: (projectId, sourceId) => ipcRenderer.invoke("get-logs", { projectId, sourceId }),

  // Startup
  setLoginAtStartup: (enabled) => ipcRenderer.invoke("set-login-at-startup", enabled),
  getLoginAtStartup: () => ipcRenderer.invoke("get-login-at-startup"),

  // Events
  onLog: (callback) => ipcRenderer.on("log", (_, data) => callback(data)),
  onSyncStatus: (callback) => ipcRenderer.on("sync-status", (_, status) => callback(status)),
});
```

- [ ] **Step 2: Commit**

```bash
git add slack_mirror_app/preload.js
git commit -m "feat: update preload.js for project/source API"
```

---

## Task 11: Update `index.html` — tree sidebar and source panels

**Files:**
- Modify: `slack_mirror_app/index.html` (full rewrite)

- [ ] **Step 1: Rewrite index.html**

Replace the entire contents of `slack_mirror_app/index.html` with the updated UI. The key changes are:

1. Sidebar becomes a tree: projects with nested sources
2. Clicking a project shows project settings (name, add source, delete)
3. Clicking a source shows config/auth/logs tabs
4. "Add Project" button at sidebar bottom
5. "Add Source" dropdown (Slack/Teams) when viewing a project
6. Status dots on sources (not projects)

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <title>Slack Mirror</title>
    <style>
      * { margin: 0; padding: 0; box-sizing: border-box; }
      body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        background: #1a1a2e;
        color: #eee;
        height: 100vh;
        display: flex;
        flex-direction: column;
        -webkit-app-region: drag;
      }
      button, input, select, label { -webkit-app-region: no-drag; }

      .titlebar {
        height: 38px;
        display: flex;
        align-items: center;
        padding: 0 80px 0 16px;
        background: #0d1117;
        font-size: 13px;
        font-weight: 600;
        color: #888;
        flex-shrink: 0;
      }

      .app-layout {
        display: flex;
        flex: 1;
        overflow: hidden;
        -webkit-app-region: no-drag;
      }

      /* Sidebar */
      .sidebar {
        width: 240px;
        background: #16213e;
        border-right: 1px solid #0f3460;
        display: flex;
        flex-direction: column;
        flex-shrink: 0;
      }
      .sidebar-header {
        padding: 12px 16px 8px;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #555;
      }
      .tree-list {
        flex: 1;
        overflow-y: auto;
      }

      /* Project item */
      .project-item {
        padding: 8px 12px;
        cursor: pointer;
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 13px;
        font-weight: 600;
        color: #aaa;
        border-left: 3px solid transparent;
        transition: all 0.15s;
      }
      .project-item:hover { background: #1a2744; color: #ddd; }
      .project-item.active {
        background: #1a2744;
        color: #fff;
        border-left-color: #e94560;
      }
      .project-item .arrow {
        font-size: 10px;
        width: 12px;
        transition: transform 0.15s;
      }
      .project-item .arrow.expanded { transform: rotate(90deg); }

      /* Source item */
      .source-item {
        padding: 7px 12px 7px 36px;
        cursor: pointer;
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 12px;
        color: #888;
        border-left: 3px solid transparent;
        transition: all 0.15s;
      }
      .source-item:hover { background: #1a2744; color: #ccc; }
      .source-item.active {
        background: #1a2744;
        color: #fff;
        border-left-color: #e94560;
      }
      .source-item .dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        flex-shrink: 0;
      }
      .source-item .dot.running { background: #4caf50; }
      .source-item .dot.stopped { background: #555; }
      .source-item .src-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .source-item .src-type {
        font-size: 10px;
        padding: 1px 5px;
        border-radius: 3px;
        background: #0f3460;
        color: #666;
        text-transform: uppercase;
      }

      .sidebar-bottom {
        padding: 12px;
        border-top: 1px solid #0f3460;
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      .btn-add {
        width: 100%;
        padding: 8px;
        background: #0f3460;
        border: 1px dashed #1a4a7a;
        border-radius: 6px;
        color: #888;
        font-size: 12px;
        cursor: pointer;
        text-align: center;
      }
      .btn-add:hover { background: #1a4a7a; color: #ccc; }

      .startup-toggle {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 11px;
        color: #666;
        padding: 0 4px;
      }
      .startup-toggle input { width: 14px; height: 14px; }

      /* Main content */
      .main {
        flex: 1;
        display: flex;
        flex-direction: column;
        overflow: hidden;
      }

      .ws-header {
        padding: 16px 20px;
        background: #16213e;
        border-bottom: 1px solid #0f3460;
        display: flex;
        align-items: center;
        gap: 12px;
      }
      .ws-header h2 { font-size: 16px; font-weight: 600; flex: 1; }
      .status-badge {
        padding: 3px 10px;
        border-radius: 10px;
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
      }
      .status-badge.running { background: #0a3d0a; color: #4caf50; border: 1px solid #4caf50; }
      .status-badge.stopped { background: #3d0a0a; color: #f44336; border: 1px solid #f44336; }

      .inner-tabs {
        display: flex;
        background: #16213e;
        border-bottom: 1px solid #0f3460;
      }
      .inner-tab {
        padding: 8px 16px;
        cursor: pointer;
        font-size: 12px;
        color: #666;
        border-bottom: 2px solid transparent;
      }
      .inner-tab:hover { color: #aaa; }
      .inner-tab.active { color: #e94560; border-bottom-color: #e94560; }

      .panel { display: none; flex: 1; overflow: auto; padding: 16px 20px; }
      .panel.active { display: flex; flex-direction: column; }

      .controls { display: flex; gap: 8px; margin-bottom: 14px; flex-wrap: wrap; }
      button {
        padding: 7px 16px;
        border: none;
        border-radius: 5px;
        font-size: 12px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.15s;
      }
      button:active { transform: scale(0.97); }
      .btn-start { background: #4caf50; color: white; }
      .btn-start:hover { background: #45a049; }
      .btn-stop { background: #f44336; color: white; }
      .btn-stop:hover { background: #d32f2f; }
      .btn-sync { background: #2196f3; color: white; }
      .btn-sync:hover { background: #1976d2; }
      .btn-auth { background: #ff9800; color: white; }
      .btn-auth:hover { background: #f57c00; }
      .btn-save { background: #e94560; color: white; }
      .btn-save:hover { background: #c73650; }
      .btn-secondary { background: #333; color: #ccc; }
      .btn-secondary:hover { background: #444; }
      .btn-danger { background: transparent; color: #f44336; border: 1px solid #f44336; }
      .btn-danger:hover { background: #3d0a0a; }

      .form-group { margin-bottom: 14px; }
      .form-group label {
        display: block;
        font-size: 11px;
        color: #666;
        margin-bottom: 4px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }
      .form-group input, .form-group select {
        width: 100%;
        padding: 9px 12px;
        background: #0f3460;
        border: 1px solid #1a4a7a;
        border-radius: 5px;
        color: #eee;
        font-size: 13px;
        outline: none;
      }
      .form-group input:focus, .form-group select:focus { border-color: #e94560; }
      .form-row { display: flex; gap: 12px; }
      .form-row .form-group { flex: 1; }

      .toggle-row {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 10px;
        font-size: 13px;
        color: #aaa;
      }
      .toggle-row input { width: 16px; height: 16px; }

      .log-container {
        flex: 1;
        background: #0d1117;
        border-radius: 6px;
        padding: 10px;
        font-family: "SF Mono", "Fira Code", monospace;
        font-size: 11px;
        overflow-y: auto;
        line-height: 1.6;
        min-height: 200px;
      }
      .log-entry { color: #8b949e; }
      .log-entry.error { color: #f85149; }

      .auth-box {
        background: #16213e;
        border-radius: 6px;
        padding: 16px;
        margin-bottom: 14px;
      }
      .auth-box p { font-size: 13px; color: #888; margin-bottom: 10px; line-height: 1.5; }
      .auth-box ol { font-size: 13px; color: #aaa; margin: 10px 0; padding-left: 20px; }
      .auth-box ol li { margin-bottom: 4px; }

      .empty-state {
        flex: 1;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #444;
        font-size: 14px;
      }

      /* Add source dropdown */
      .add-source-dropdown {
        position: relative;
        display: inline-block;
      }
      .add-source-menu {
        display: none;
        position: absolute;
        top: 100%;
        left: 0;
        background: #16213e;
        border: 1px solid #0f3460;
        border-radius: 6px;
        overflow: hidden;
        z-index: 10;
        min-width: 140px;
        margin-top: 4px;
      }
      .add-source-menu.show { display: block; }
      .add-source-option {
        padding: 8px 14px;
        cursor: pointer;
        font-size: 12px;
        color: #aaa;
      }
      .add-source-option:hover { background: #1a2744; color: #fff; }
    </style>
  </head>
  <body>
    <div class="titlebar">Slack Mirror</div>

    <div class="app-layout">
      <!-- Sidebar -->
      <div class="sidebar">
        <div class="sidebar-header">Projects</div>
        <div class="tree-list" id="tree-list"></div>
        <div class="sidebar-bottom">
          <div class="btn-add" id="btn-add-project">+ Add Project</div>
          <label class="startup-toggle">
            <input type="checkbox" id="chk-startup" />
            Launch at startup
          </label>
        </div>
      </div>

      <!-- Main -->
      <div class="main" id="main-content">
        <div class="empty-state" id="empty-state">
          Select a project or source, or add a new project
        </div>
      </div>
    </div>

    <script>
      let projects = [];
      let statuses = {};
      let selectedProjectId = null;
      let selectedSourceId = null; // null = project level, string = source level
      let expandedProjects = new Set();

      // --- Sidebar ---
      function renderSidebar() {
        const list = document.getElementById("tree-list");
        list.innerHTML = "";

        for (const proj of projects) {
          const isExpanded = expandedProjects.has(proj.id);
          const isActiveProject = proj.id === selectedProjectId && !selectedSourceId;

          // Project row
          const projDiv = document.createElement("div");
          projDiv.className = `project-item${isActiveProject ? " active" : ""}`;
          projDiv.innerHTML = `
            <span class="arrow ${isExpanded ? "expanded" : ""}">&#9654;</span>
            <span>${proj.name}</span>
          `;
          projDiv.addEventListener("click", (e) => {
            if (e.target.classList.contains("arrow") || e.target.closest(".arrow")) {
              toggleProject(proj.id);
            } else {
              selectProject(proj.id);
            }
          });
          list.appendChild(projDiv);

          // Source rows (if expanded)
          if (isExpanded) {
            for (const src of proj.sources || []) {
              const key = `${proj.id}::${src.id}`;
              const isRunning = statuses[key]?.running;
              const isActiveSource = proj.id === selectedProjectId && src.id === selectedSourceId;

              const srcDiv = document.createElement("div");
              srcDiv.className = `source-item${isActiveSource ? " active" : ""}`;
              srcDiv.innerHTML = `
                <span class="dot ${isRunning ? "running" : "stopped"}"></span>
                <span class="src-name">${src.label || "Unnamed"}</span>
                <span class="src-type">${src.type || "slack"}</span>
              `;
              srcDiv.addEventListener("click", () => selectSource(proj.id, src.id));
              list.appendChild(srcDiv);
            }
          }
        }
      }

      function toggleProject(projectId) {
        if (expandedProjects.has(projectId)) {
          expandedProjects.delete(projectId);
        } else {
          expandedProjects.add(projectId);
        }
        renderSidebar();
      }

      function selectProject(projectId) {
        selectedProjectId = projectId;
        selectedSourceId = null;
        expandedProjects.add(projectId);
        renderSidebar();
        renderProjectPanel();
      }

      function selectSource(projectId, sourceId) {
        selectedProjectId = projectId;
        selectedSourceId = sourceId;
        renderSidebar();
        renderSourcePanel();
      }

      // --- Project Panel ---
      function renderProjectPanel() {
        const main = document.getElementById("main-content");
        const proj = projects.find((p) => p.id === selectedProjectId);
        if (!proj) {
          main.innerHTML = '<div class="empty-state">Select a project or source</div>';
          return;
        }

        main.innerHTML = `
          <div class="ws-header">
            <h2>${proj.name}</h2>
          </div>
          <div class="panel active" style="gap: 16px;">
            <div class="form-group">
              <label>Project Name</label>
              <input type="text" id="proj-name" value="${proj.name}" />
            </div>
            <div class="controls">
              <button class="btn-save" id="btn-save-project">Save</button>
              <div class="add-source-dropdown">
                <button class="btn-sync" id="btn-add-source">+ Add Source</button>
                <div class="add-source-menu" id="add-source-menu">
                  <div class="add-source-option" data-type="slack">Slack</div>
                  <div class="add-source-option" data-type="teams">Teams</div>
                </div>
              </div>
              <button class="btn-danger" id="btn-delete-project">Delete Project</button>
            </div>
            <div style="color: #666; font-size: 13px;">
              ${(proj.sources || []).length} source(s) configured.
              ${(proj.sources || []).length === 0 ? "Add a Slack or Teams source to get started." : "Click a source in the sidebar to configure it."}
            </div>
          </div>
        `;

        // Save project name
        document.getElementById("btn-save-project").addEventListener("click", async () => {
          proj.name = document.getElementById("proj-name").value;
          await window.api.saveProject(proj);
          projects = await window.api.getProjects();
          renderSidebar();
          renderProjectPanel();
        });

        // Add source dropdown
        const addBtn = document.getElementById("btn-add-source");
        const menu = document.getElementById("add-source-menu");
        addBtn.addEventListener("click", () => menu.classList.toggle("show"));
        document.addEventListener("click", (e) => {
          if (!e.target.closest(".add-source-dropdown")) menu.classList.remove("show");
        }, { once: true });

        menu.querySelectorAll(".add-source-option").forEach((opt) => {
          opt.addEventListener("click", async () => {
            const type = opt.dataset.type;
            const sourceId = "src-" + Date.now();
            const source = {
              id: sourceId,
              type,
              label: type === "slack" ? "New Slack" : "New Teams",
              url: type === "slack" ? "" : "https://teams.microsoft.com",
              vault: "",
              channels: "",
              intervalMinutes: 30,
              autoSync: false,
              syncDMs: true,
              syncGroups: true,
            };
            await window.api.addSource(proj.id, source);
            projects = await window.api.getProjects();
            expandedProjects.add(proj.id);
            selectSource(proj.id, sourceId);
          });
        });

        // Delete project
        document.getElementById("btn-delete-project").addEventListener("click", async () => {
          if (confirm(`Delete project "${proj.name}" and all its sources?`)) {
            await window.api.deleteProject(proj.id);
            projects = await window.api.getProjects();
            selectedProjectId = projects[0]?.id || null;
            selectedSourceId = null;
            renderSidebar();
            if (selectedProjectId) renderProjectPanel();
            else document.getElementById("main-content").innerHTML = '<div class="empty-state">Select a project or source, or add a new project</div>';
          }
        });
      }

      // --- Source Panel ---
      function renderSourcePanel() {
        const main = document.getElementById("main-content");
        const proj = projects.find((p) => p.id === selectedProjectId);
        const src = proj?.sources?.find((s) => s.id === selectedSourceId);
        if (!proj || !src) {
          main.innerHTML = '<div class="empty-state">Source not found</div>';
          return;
        }

        const key = `${proj.id}::${src.id}`;
        const isRunning = statuses[key]?.running;
        const typeLabel = src.type === "teams" ? "Teams" : "Slack";

        main.innerHTML = `
          <div class="ws-header">
            <h2>${typeLabel} — ${src.label}</h2>
            <span class="status-badge ${isRunning ? "running" : "stopped"}">
              ${isRunning ? "Running" : "Stopped"}
            </span>
          </div>

          <div class="inner-tabs">
            <div class="inner-tab active" data-panel="control">Control</div>
            <div class="inner-tab" data-panel="config">Config</div>
            <div class="inner-tab" data-panel="auth">Auth</div>
            <div class="inner-tab" data-panel="logs">Logs</div>
          </div>

          <!-- Control -->
          <div class="panel active" id="panel-control">
            <div class="controls">
              <button class="btn-start" id="btn-start">Start Auto-Sync</button>
              <button class="btn-stop" id="btn-stop">Stop</button>
              <button class="btn-sync" id="btn-sync-once">Sync Now</button>
            </div>
            <div class="log-container" id="control-logs"></div>
          </div>

          <!-- Config -->
          <div class="panel" id="panel-config">
            <div class="form-group">
              <label>Source Label</label>
              <input type="text" id="cfg-label" value="${src.label}" />
            </div>
            <div class="form-group">
              <label>${typeLabel} URL</label>
              <input type="text" id="cfg-url" value="${src.url}" placeholder="${src.type === "teams" ? "https://teams.microsoft.com" : "https://yourworkspace.slack.com"}" />
            </div>
            <div class="form-group">
              <label>Obsidian Vault Name</label>
              <input type="text" id="cfg-vault" value="${src.vault}" />
            </div>
            <div class="form-row">
              <div class="form-group">
                <label>Channels (comma-separated)</label>
                <input type="text" id="cfg-channels" value="${src.channels || ""}" placeholder="general, random" />
              </div>
              <div class="form-group">
                <label>Sync Interval (minutes)</label>
                <input type="number" id="cfg-interval" value="${src.intervalMinutes || 30}" min="1" max="1440" />
              </div>
            </div>
            <div class="toggle-row">
              <input type="checkbox" id="cfg-auto" ${src.autoSync ? "checked" : ""} />
              <label for="cfg-auto">Auto-sync on app launch</label>
            </div>
            <div class="toggle-row">
              <input type="checkbox" id="cfg-dms" ${src.syncDMs !== false ? "checked" : ""} />
              <label for="cfg-dms">Sync direct messages</label>
            </div>
            <div class="toggle-row">
              <input type="checkbox" id="cfg-groups" ${src.syncGroups !== false ? "checked" : ""} />
              <label for="cfg-groups">Sync group messages</label>
            </div>
            <div class="controls">
              <button class="btn-save" id="btn-save-source">Save Config</button>
              <button class="btn-danger" id="btn-delete-source">Remove Source</button>
            </div>
          </div>

          <!-- Auth -->
          <div class="panel" id="panel-auth">
            <div class="auth-box">
              <p>Authenticate with <strong>${src.label}</strong> (${typeLabel}):</p>
              <ol>
                <li>Click <strong>Open Login Browser</strong></li>
                <li>Log into ${typeLabel} in the browser that opens</li>
                <li>Once logged in, click <strong>Save Session</strong></li>
              </ol>
              <div class="controls">
                <button class="btn-auth" id="btn-auth">Open Login Browser</button>
                <button class="btn-secondary" id="btn-auth-save">Save Session</button>
              </div>
            </div>
          </div>

          <!-- Logs -->
          <div class="panel" id="panel-logs">
            <div class="log-container" id="full-logs"></div>
          </div>
        `;

        // Tab switching
        main.querySelectorAll(".inner-tab").forEach((tab) => {
          tab.addEventListener("click", () => {
            main.querySelectorAll(".inner-tab").forEach((t) => t.classList.remove("active"));
            main.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
            tab.classList.add("active");
            document.getElementById(`panel-${tab.dataset.panel}`).classList.add("active");
          });
        });

        // Control buttons
        document.getElementById("btn-start").addEventListener("click", () => window.api.startSync(proj.id, src.id));
        document.getElementById("btn-stop").addEventListener("click", () => window.api.stopSync(proj.id, src.id));
        document.getElementById("btn-sync-once").addEventListener("click", () => window.api.runOnce(proj.id, src.id));

        // Save source config
        document.getElementById("btn-save-source").addEventListener("click", async () => {
          const updated = {
            ...src,
            label: document.getElementById("cfg-label").value,
            url: document.getElementById("cfg-url").value,
            vault: document.getElementById("cfg-vault").value,
            channels: document.getElementById("cfg-channels").value,
            intervalMinutes: parseInt(document.getElementById("cfg-interval").value) || 30,
            autoSync: document.getElementById("cfg-auto").checked,
            syncDMs: document.getElementById("cfg-dms").checked,
            syncGroups: document.getElementById("cfg-groups").checked,
          };
          await window.api.saveSource(proj.id, updated);
          projects = await window.api.getProjects();
          renderSidebar();
          renderSourcePanel();
        });

        // Delete source
        document.getElementById("btn-delete-source").addEventListener("click", async () => {
          if (confirm(`Remove source "${src.label}" from project "${proj.name}"?`)) {
            await window.api.deleteSource(proj.id, src.id);
            projects = await window.api.getProjects();
            selectedSourceId = null;
            renderSidebar();
            renderProjectPanel();
          }
        });

        // Auth
        document.getElementById("btn-auth").addEventListener("click", () => window.api.runAuth(proj.id, src.id));
        document.getElementById("btn-auth-save").addEventListener("click", () => window.api.signalAuth(proj.id, src.id));

        // Load existing logs
        window.api.getLogs(proj.id, src.id).then((existingLogs) => {
          existingLogs.forEach((msg) => appendLogToPanel(msg));
        });
      }

      // --- Logs ---
      function appendLogToPanel(message) {
        const controlLogs = document.getElementById("control-logs");
        const fullLogs = document.getElementById("full-logs");
        if (!controlLogs || !fullLogs) return;

        const div = document.createElement("div");
        div.className = "log-entry" + (message.includes("ERROR") ? " error" : "");
        div.textContent = message;

        controlLogs.appendChild(div.cloneNode(true));
        fullLogs.appendChild(div);
        controlLogs.scrollTop = controlLogs.scrollHeight;
        fullLogs.scrollTop = fullLogs.scrollHeight;
      }

      // --- Events ---
      window.api.onLog((data) => {
        if (data.projectId === selectedProjectId && data.sourceId === selectedSourceId) {
          appendLogToPanel(data.message);
        }
      });

      window.api.onSyncStatus((status) => {
        const key = `${status.projectId}-${status.sourceId}`;
        statuses[key] = status;
        renderSidebar();
        if (status.projectId === selectedProjectId && status.sourceId === selectedSourceId) {
          const badge = document.querySelector(".status-badge");
          if (badge) {
            badge.textContent = status.running ? "Running" : "Stopped";
            badge.className = `status-badge ${status.running ? "running" : "stopped"}`;
          }
        }
      });

      // --- Add project ---
      document.getElementById("btn-add-project").addEventListener("click", async () => {
        const id = "proj-" + Date.now();
        const proj = {
          id,
          name: "New Project",
          sources: [],
        };
        await window.api.saveProject(proj);
        projects = await window.api.getProjects();
        selectProject(id);
      });

      // --- Startup checkbox ---
      document.getElementById("chk-startup").addEventListener("change", (e) => {
        window.api.setLoginAtStartup(e.target.checked);
      });

      // --- Init ---
      (async () => {
        projects = await window.api.getProjects();
        statuses = await window.api.getAllStatuses();
        const startupEnabled = await window.api.getLoginAtStartup();
        document.getElementById("chk-startup").checked = startupEnabled;

        renderSidebar();
        if (projects.length > 0) {
          selectProject(projects[0].id);
        }
      })();
    </script>
  </body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add slack_mirror_app/index.html
git commit -m "feat: update UI for tree sidebar with projects and sources"
```

---

## Task 12: Update README.md

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README**

Update the README to reflect the new project/source model:

1. Update the title/description to mention Teams support
2. Update the "How It Works" diagram to show multi-source
3. Update the Vault Structure example to show project/source namespacing with index files
4. Update the Features list to include Teams and Projects
5. Update the "First Run" instructions for the new UI flow (Add Project → Add Source)
6. Update the Roadmap to check off Teams
7. Keep installation and build instructions unchanged

Key sections to update:

**Opening paragraph:** Change "captures every message from your Slack workspaces" to "captures every message from your Slack workspaces and Microsoft Teams tenants"

**How It Works diagram:**
```
Your Slack/Teams (web) → Playwright (headless browser) → Python scraper → Obsidian CLI → Your vault
```

**Vault Structure:**
```
your-vault/
└── Client Alpha/
    ├── index.md
    ├── slack-acme/
    │   ├── index.md
    │   ├── channels/project-alpha.md
    │   ├── dms/Keanu Reeves.md
    │   └── groups/Snoop Dogg, Morgan Freeman.md
    └── teams-acme/
        ├── index.md
        ├── channels/General.md
        ├── chats/Dolly Parton.md
        └── groups/Arnold, Morgan Freeman.md
```

**Features:** Add "Multi-source projects", "Microsoft Teams support", update "Multi-workspace" to "Multi-project"

**First Run:** Change steps to Add Project → Add Source (Slack/Teams) → Configure → Auth → Sync

**Roadmap:** Check off Microsoft Teams

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update README for multi-source projects and Teams support"
```

---

## Task 13: Delete old `workspaces.json` sample

**Files:**
- Delete: `slack_mirror_app/workspaces.json`

- [ ] **Step 1: Check if sample workspaces.json exists in the app directory**

```bash
ls slack_mirror_app/workspaces.json
```

If it exists, remove it since it's a sample file for the old data model.

- [ ] **Step 2: Delete if present**

```bash
git rm slack_mirror_app/workspaces.json 2>/dev/null || echo "File not found, skipping"
```

- [ ] **Step 3: Commit if deleted**

```bash
git diff --cached --quiet || git commit -m "chore: remove legacy workspaces.json sample"
```

---

## Task 14: End-to-end verification

- [ ] **Step 1: Verify Python imports**

```bash
cd slack_mirror && python -c "
from config import SOURCE_TYPE, SOURCE_URL, PROJECT_NAME, SOURCE_LABEL, SYNC_DMS, SYNC_GROUPS
from main import main
from slack_scraper import scrape_all as slack_scrape
from teams_scraper import scrape_all as teams_scrape
from obsidian_writer import write_channel_messages, write_source_index, write_project_index
from utils import resolve_date
from sync_state import filter_new_messages
print('All Python imports OK')
"
```

Expected: `All Python imports OK`

- [ ] **Step 2: Verify Electron app launches**

```bash
cd slack_mirror_app && npm start
```

Expected: App window opens with tree sidebar showing "Projects" header and "+ Add Project" button. Close the app manually.

- [ ] **Step 3: Test migration (if old workspaces.json exists)**

If testing with existing data, verify that:
- `projects.json` was created from `workspaces.json`
- Each workspace became a project with one Slack source
- Source directories were created under `projects/{id}/{source-id}/`
- `workspaces.json` was renamed to `workspaces.json.backup`

- [ ] **Step 4: Final commit (if any fixes needed)**

```bash
git add -A && git commit -m "fix: end-to-end verification fixes"
```
