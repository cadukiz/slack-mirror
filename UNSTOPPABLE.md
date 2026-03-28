# Slack Mirror — Unstoppable Integration

## How it connects

Slack Mirror is an independent product that scrapes Slack/Teams web clients and writes messages to an Obsidian vault. Unstoppable Core orchestrates it via:

1. **Trigger:** Core's scheduler runs Slack Mirror on a cron schedule (default: every 30 minutes)
2. **Execution:** Core spawns `python3 src/main.py --project <id>` as a child process
3. **Output:** Messages are written to `Projects/<project>/context/slack/` in the vault
4. **Post-processing:** The frontmatter wrapper adds standardized YAML frontmatter
5. **Detection:** Core's vault watcher detects new files and triggers the intake pipeline

## Vault output structure

```
Projects/<project>/context/slack/
├── channels/
│   └── project-alpha.md
├── dms/
│   └── John Doe.md
└── groups/
    └── Team Chat.md
```

## Frontmatter contract

Every file gets this frontmatter (added by frontmatter_wrapper.py):

```yaml
---
source: slack-mirror
project: <project-id>
type: slack-message
subtype: channel | dm | group
name: <channel-or-person-name>
timestamp: <ISO 8601>
platform: slack | teams
---
```

## Running standalone

Slack Mirror works without Unstoppable Core. It has its own Electron UI for configuration and manual sync. The integration layer is additive.
