# Slack Mirror

**Your work conversations shouldn't live in a black box.** Slack Mirror automatically captures every message from your Slack workspaces — channels, DMs, and group chats — and mirrors them into your Obsidian vault in real time.

> Stop losing context. Start building your second brain.

---

## The Problem

You're juggling multiple clients, projects, and conversations across Slack workspaces. Critical decisions get buried in threads. Action items disappear in DMs. When you need to recall *what was said, by whom, and when* — you're scrolling through months of chat history.

**Your conversations are your most valuable work artifact, and they're trapped inside Slack.**

## The Solution

Slack Mirror runs quietly in your menu bar, syncing every message into Obsidian — the tool built for connecting knowledge. Every conversation becomes a searchable, linkable, permanent note.

```
2026-03-18 09:15:30 - Keanu Reeves : I know kung fu. But do we know the deploy schedule?
2026-03-18 09:17:42 - Snoop Dogg : Fo shizzle, shipping to prod Friday. The pipeline is clean.
2026-03-18 09:22:01 - Morgan Freeman : I can explain this architecture. But first, let me narrate the PR.
2026-03-18 09:25:18 - Dolly Parton : Working 9 to 5 on this migration. Schema changes are done.
2026-03-18 09:31:55 - Arnold Schwarzenegger : I'll be back... after code review.
```

### Why Obsidian?

- **You own your data** — plain markdown files on your machine, no cloud lock-in
- **Link everything** — connect a Slack message to a meeting note, a project doc, or a client brief
- **Search across all sources** — once your conversations live in Obsidian, they become part of your full knowledge graph
- **Works offline** — your notes are always available, even without internet
- **Plugin ecosystem** — extend with Dataview, Canvas, Graph View, and hundreds more

The goal is simple: **full context about your work, projects, and clients — all in one place.**

## Features

- **Multi-workspace** — monitor unlimited Slack workspaces, each synced to its own Obsidian vault
- **Auto-sync** — configurable intervals (default: every 30 minutes)
- **Channels, DMs, and groups** — captures everything, organized by conversation type
- **Smart deduplication** — only syncs new messages, never duplicates
- **Bilingual** — works with any language (Portuguese, English, Spanish, etc.)
- **Launch at startup** — set it and forget it
- **Menu bar app** — runs silently in the background
- **Zero cost** — no subscriptions, no API keys, no cloud services

## How It Works

```
Your Slack (web) → Playwright (headless browser) → Python scraper → Obsidian CLI → Your vault
```

Slack Mirror uses browser automation to read your Slack messages — no Slack API or admin permissions required. If you can see it in Slack, Slack Mirror can capture it.

### Vault Structure

```
your-vault/
├── slack/
│   ├── channels/
│   │   └── project-alpha.md
│   ├── dms/
│   │   ├── Keanu Reeves.md
│   │   └── Dolly Parton.md
│   └── groups/
│       └── Snoop Dogg, Morgan Freeman, Arnold.md
```

## Installation

### Download

> **[Download Slack Mirror v1.0.0 for macOS (Apple Silicon)](https://github.com/cadukiz/slack-mirror/releases/download/v1.0.0/Slack.Mirror-1.0.0-arm64.dmg)**

Open the DMG and drag Slack Mirror to your Applications folder.

### Requirements

- **macOS** (Apple Silicon or Intel)
- **Python 3.8+** — if not installed: `xcode-select --install`
- **Obsidian** — [download here](https://obsidian.md) with the [Obsidian CLI](https://github.com/Obsidian-CLI/obsidian-cli) plugin enabled

### First Run

1. Open **Slack Mirror** from Applications
2. Click **+ Add Workspace** in the sidebar
3. Configure:
   - **Name**: anything you want (e.g., "My Company")
   - **Slack URL**: your workspace URL (e.g., `https://mycompany.slack.com`)
   - **Obsidian Vault**: the vault name where messages should go
   - **Channels**: comma-separated channel names to monitor
4. Go to the **Auth** tab → click **Open Login Browser** → log into Slack → click **Save Session**
5. Click **Start Auto-Sync**

That's it. Your messages will start flowing into Obsidian.

### Build from Source

```bash
# Clone
git clone https://github.com/cadukiz/slack-mirror.git
cd slack-mirror

# Set up Python scraper
cd slack_mirror
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# Set up Electron app
cd ../slack_mirror_app
npm install

# Run in dev mode
npm start

# Build installer
npm run build
```

## Roadmap

Slack is just the beginning. The vision is **complete work context in Obsidian**:

- [x] **Slack** — channels, DMs, groups
- [ ] **Email** — Gmail, Outlook inbox mirrored to vault
- [ ] **Meeting recordings** — transcripts from Zoom, Google Meet, Teams
- [ ] **WhatsApp** — personal and business chats
- [ ] **Microsoft Teams** — channels and chats
- [ ] **Calendar** — meeting notes auto-linked to events
- [ ] **AI summaries** — daily digest of key decisions and action items

**The end goal:** open Obsidian and have *everything* — every conversation, every decision, every action item — searchable, linked, and permanent.

## Contributing

PRs welcome. If you want to add a new source (email, Teams, WhatsApp), open an issue first to discuss the approach.

## License

MIT
