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
import json
import os
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
