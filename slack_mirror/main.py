"""
Slack → Obsidian Mirror
Scrapes Slack messages and writes them to an Obsidian vault.

Usage:
    python main.py              # Sync new messages only
    python main.py --history    # First run: load all historical messages
"""
import argparse
import sys
from config import AUTH_STATE_PATH
from scraper import scrape_all
from obsidian_writer import write_channel_messages, write_dm_messages, write_group_messages
from sync_state import filter_new_messages, get_latest_timestamp, update_last_message_ts


def sync_messages(category_name: str, conv_name: str, all_messages: list[dict], writer_fn):
    """Filter new messages and write them. Returns count of new messages."""
    conv_id = f"{category_name}:{conv_name}"
    new_messages = filter_new_messages(conv_id, all_messages)

    if new_messages:
        writer_fn(conv_name, new_messages)
        latest_ts = get_latest_timestamp(new_messages)
        if latest_ts:
            update_last_message_ts(conv_id, latest_ts)
        print(f"  {conv_id}: {len(new_messages)} new messages (of {len(all_messages)} total)")
    else:
        print(f"  {conv_id}: no new messages")

    return len(new_messages)


def main():
    parser = argparse.ArgumentParser(description="Slack → Obsidian mirror")
    parser.add_argument("--history", action="store_true", help="Load historical messages (first run)")
    args = parser.parse_args()

    if not AUTH_STATE_PATH.exists():
        print("No saved session found. Run 'python auth.py' first to log in.")
        sys.exit(1)

    print("Scraping Slack...")
    data = scrape_all(load_history=args.history)

    total_new = 0

    # Write channels
    for name, messages in data["channels"].items():
        total_new += sync_messages("channel", name, messages, write_channel_messages)

    # Write DMs
    for name, messages in data["dms"].items():
        total_new += sync_messages("dm", name, messages, write_dm_messages)

    # Write group DMs
    for name, messages in data["groups"].items():
        total_new += sync_messages("group", name, messages, write_group_messages)

    total_scraped = sum(
        len(msgs)
        for category in data.values()
        for msgs in category.values()
    )
    print(f"\nDone! {total_new} new messages synced (of {total_scraped} scraped).")


if __name__ == "__main__":
    main()
