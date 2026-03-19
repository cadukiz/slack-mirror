# Multi-Source Projects Design

## Overview

Evolve Slack Mirror from a single-source Slack scraper into a multi-source messaging mirror. Introduce "Projects" as containers that hold N sources (Slack workspaces, Teams tenants). Each source syncs independently and writes to a namespaced vault path. Meeting transcription sources are on the roadmap but out of scope for this phase.

## Data Model

### Project

```json
{
  "id": "uuid",
  "name": "Client Alpha",
  "sources": [
    {
      "id": "uuid",
      "type": "slack",
      "label": "Acme Slack",
      "url": "https://acme.slack.com",
      "vault": "my-vault",
      "channels": "general, engineering",
      "syncDMs": true,
      "syncGroups": true,
      "intervalMinutes": 30,
      "autoSync": true
    },
    {
      "id": "uuid",
      "type": "teams",
      "label": "Acme Teams",
      "url": "https://teams.microsoft.com",
      "vault": "my-vault",
      "channels": "General, Engineering",
      "syncDMs": true,
      "syncGroups": true,
      "intervalMinutes": 30,
      "autoSync": true
    }
  ]
}
```

### On-Disk State

```
~/Library/Application Support/Slack Mirror/data/
├── projects.json
└── projects/
    └── {project-id}/
        └── {source-id}/
            ├── auth.json
            └── sync_state.json
```

### Vault Output

```
vault/
└── {project-name}/
    ├── index.md                          # Project index with links to sources
    ├── slack-{label}/
    │   ├── index.md                      # Source index with links to all conversations
    │   ├── channels/{channel-name}.md
    │   ├── dms/{person-name}.md
    │   └── groups/{group-name}.md
    └── teams-{label}/
        ├── index.md
        ├── channels/{channel-name}.md
        ├── chats/{person-name}.md
        └── groups/{group-name}.md
```

Source label defaults to the URL domain (e.g., `acme` from `acme.slack.com`) but can be overridden by the user.

### Index Files

**Project index** (`{project-name}/index.md`):
```markdown
# Client Alpha

## Sources

### [[Client Alpha/slack-acme/index|Slack - Acme]]
### [[Client Alpha/teams-acme/index|Teams - Acme]]
```

**Source index** (`{project-name}/{source-prefix}/index.md`):
```markdown
# Slack - Acme

## Channels
- [[Client Alpha/slack-acme/channels/general|#general]]
- [[Client Alpha/slack-acme/channels/engineering|#engineering]]

## Direct Messages
- [[Client Alpha/slack-acme/dms/John Doe|John Doe]]

## Groups
- [[Client Alpha/slack-acme/groups/John Doe, Jane Smith|John Doe, Jane Smith]]
```

Index files are regenerated on each sync to reflect newly discovered conversations.

## Python Backend

### File Structure

```
slack_mirror/
├── main.py              # Accepts --source-type slack|teams, --project-name, --source-label
├── config.py            # Source-type aware, project/source path management
├── auth.py              # Unchanged (open browser, manual login, save session)
├── slack_scraper.py     # Renamed from scraper.py, unchanged internals
├── teams_scraper.py     # NEW: same interface, Teams DOM selectors
├── obsidian_writer.py   # Updated paths: {project}/{source-prefix}/..., index generation
├── sync_state.py        # Unchanged (already generic)
├── utils.py             # NEW: shared date parsing extracted from scraper
```

### main.py Changes

- New CLI args: `--source-type slack|teams`, `--project-name`, `--source-label`
- Routes to `slack_scraper.scrape_all()` or `teams_scraper.scrape_all()` based on `--source-type`
- Passes `project_name` and `source_label` to `obsidian_writer` for vault path construction
- Sync flow remains identical: scrape -> filter new via sync_state -> write to Obsidian

### teams_scraper.py

Same contract as `slack_scraper.py`:

- `scrape_all(load_history)` returns `{"channels": {...}, "dms": {...}, "groups": {...}}`
- `scrape_channels(page, channel_names, load_history)` — navigate Teams sidebar "Teams" section
- `scrape_dms(page, load_history)` — navigate "Chat" section, separate 1:1 from group
- `_extract_messages(page)` — Teams-specific DOM selectors for messages
- Each message returns `{"author": str, "date": str, "time": str, "text": str}`

Teams navigation:
- Channels: "Teams" sidebar section -> expand team -> click channel
- Chats: "Chat" sidebar section -> iterate chat list (1:1 vs group distinguished by participant count)

DOM selectors will be determined during implementation by inspecting the live Teams DOM.

### obsidian_writer.py Changes

- All write functions gain `project_name` and `source_prefix` params
- Paths change from `slack/channels/{name}.md` to `{project_name}/{source_prefix}/channels/{name}.md`
- New functions: `write_project_index(project_name, sources)` and `write_source_index(project_name, source_prefix, source_label, channels, dms, groups)`
- Headers updated to include source context

### config.py Changes

- New env vars: `SOURCE_TYPE`, `SOURCE_ID`, `PROJECT_NAME`, `SOURCE_LABEL`
- `WORKSPACE_DIR` renamed to `SOURCE_DIR`, points to `projects/{project-id}/{source-id}/`
- Path construction updated for project/source hierarchy

### utils.py (New)

- `resolve_date(date_str)` — extracted from current `scraper.py._resolve_date()`
- Shared by both `slack_scraper.py` and `teams_scraper.py`

## Electron App

### UI Changes

**Sidebar — tree view:**
```
▼ Client Alpha          (project)
    ◉ Slack - Acme       (source, green = syncing)
    ○ Teams - Acme       (source, gray = idle)
▶ Internal              (project, collapsed)
  + Add Source
+ Add Project
```

**Main panel — project selected:**
- Project name (editable)
- "Add Source" button (dropdown: Slack / Teams)
- Delete project button

**Main panel — source selected:**
- Same tabs as today: Config, Auth, Logs
- Config tab: source label, URL, vault, channels, sync interval, toggles (syncDMs, syncGroups, autoSync)
- Auth tab: same flow (open browser, manual login, save session)
- Logs tab: per-source log stream with real-time updates

### IPC Changes

Renamed:
- `get-workspaces` -> `get-projects`
- `save-workspace` -> `save-project`
- `delete-workspace` -> `delete-project`

New:
- `add-source` — adds a source to a project
- `delete-source` — removes a source from a project

Updated:
- `startSync(projectId, sourceId)` — start sync for a specific source
- `stopSync(projectId, sourceId)` — stop sync for a specific source
- `runOnce(projectId, sourceId)` — run single sync for a specific source
- `runAuth(projectId, sourceId)` — trigger auth for a specific source
- `getLogs(projectId, sourceId)` — get logs for a specific source

### Process Management

- `workspaceState` becomes `sourceState` keyed by `{projectId}-{sourceId}`
- Each source syncs independently with its own interval and child process
- Python spawn env vars include: `SOURCE_TYPE`, `SOURCE_ID`, `PROJECT_NAME`, `SOURCE_LABEL`, `SLACK_WORKSPACE_URL` or equivalent

### preload.js Changes

- API methods updated to match new IPC channels
- Source CRUD methods added
- All sync/auth/log methods take `projectId` + `sourceId`

## Authentication

Same approach for both platforms:
1. User clicks "Open Login Browser" for a source
2. Electron spawns `python auth.py --signal` with source-specific env vars
3. Browser opens to the source URL (Slack or Teams)
4. User manually logs in
5. User clicks "Save Session" in the Electron UI
6. Signal file created, auth.py saves session to `projects/{project-id}/{source-id}/auth.json`
7. Subsequent syncs load this session automatically

## Migration

On first launch after update, if `workspaces.json` exists and `projects.json` does not:

1. Read all workspaces from `workspaces.json`
2. For each workspace, create a project with one Slack source:
   - Project name = workspace name
   - Source inherits all workspace config (url, vault, channels, intervals, toggles)
   - Source label auto-derived from URL domain
3. Move `data/workspaces/{workspace-id}/` -> `data/projects/{project-id}/{source-id}/`
4. Write `projects.json`
5. Rename `workspaces.json` to `workspaces.backup.json`
6. Log migration details

Existing vault files under `vault/slack/` are left untouched. New syncs write to `vault/{project-name}/{source-prefix}/`. User can manually reorganize old files if desired.

## Post-Implementation

- Update `README.md` to reflect the new project/source model, updated installation steps, and Teams support
- Update any other `.md` files that reference the old workspace model

## Out of Scope (Roadmap)

- Meeting transcription sources (Slack Huddles, Teams Meetings)
- Microsoft Graph API authentication as an alternative to browser sessions
- Cross-source linking (same person across Slack and Teams)
