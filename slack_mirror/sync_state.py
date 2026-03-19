"""
Tracks which messages have already been synced to avoid duplicates.
Stores the last message timestamp (YYYY-MM-DD HH:MM:SS) per conversation.
"""
import json
from datetime import datetime, timezone
from config import SYNC_STATE_PATH


def load_state() -> dict:
    if SYNC_STATE_PATH.exists():
        with open(SYNC_STATE_PATH) as f:
            return json.load(f)
    return {}


def save_state(state: dict):
    with open(SYNC_STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def get_last_message_ts(conversation_id: str) -> str | None:
    """Get the last synced message timestamp for a conversation."""
    state = load_state()
    return state.get(conversation_id, {}).get("last_message_ts")


def update_last_message_ts(conversation_id: str, timestamp: str):
    """Update the last synced message timestamp for a conversation."""
    state = load_state()
    if conversation_id not in state:
        state[conversation_id] = {}
    state[conversation_id]["last_message_ts"] = timestamp
    state[conversation_id]["last_sync"] = datetime.now(timezone.utc).isoformat()
    save_state(state)


def filter_new_messages(conversation_id: str, messages: list[dict]) -> list[dict]:
    """Return only messages newer than the last synced timestamp."""
    last_ts = get_last_message_ts(conversation_id)
    if not last_ts:
        return messages  # First sync — all messages are new

    new_messages = []
    for msg in messages:
        msg_ts = f"{msg.get('date', '')} {msg.get('time', '')}".strip()
        if msg_ts > last_ts:
            new_messages.append(msg)

    return new_messages


def get_latest_timestamp(messages: list[dict]) -> str | None:
    """Get the latest timestamp from a list of messages."""
    if not messages:
        return None
    latest = ""
    for msg in messages:
        msg_ts = f"{msg.get('date', '')} {msg.get('time', '')}".strip()
        if msg_ts > latest:
            latest = msg_ts
    return latest or None
