"""
Writes scraped messages to Obsidian vault via the obsidian CLI.
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


def _ensure_file(path: str, title: str):
    if not _file_exists(path):
        header = f"# {title}\\n\\nAuto-synced from Slack."
        _run_obsidian(f'create path="{path}" content="{header}" silent')


def format_messages(messages: list[dict]) -> str:
    """Format messages as markdown text for appending.
    Format: YYYY-MM-DD HH:MM:SS - Name : message
    """
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

        # Build timestamp: "Date Time - Author : message"
        timestamp = f"{date} {time_str}".strip()
        lines.append(f"**{timestamp} - {author}** : {text}\\n")

    return "\\n".join(lines)


def write_channel_messages(channel_name: str, messages: list[dict]):
    if not messages:
        return
    path = f"slack/channels/{channel_name}.md"
    _ensure_file(path, f"#{channel_name}")
    content = format_messages(messages)
    _run_obsidian(f'append path="{path}" content="{content}"')


def write_dm_messages(person_name: str, messages: list[dict]):
    if not messages:
        return
    safe_name = person_name.replace("/", "-")
    path = f"slack/dms/{safe_name}.md"
    _ensure_file(path, f"DM — {person_name}")
    content = format_messages(messages)
    _run_obsidian(f'append path="{path}" content="{content}"')


def write_group_messages(group_name: str, messages: list[dict]):
    if not messages:
        return
    safe_name = group_name.replace("/", "-")
    path = f"slack/groups/{safe_name}.md"
    _ensure_file(path, f"Group — {group_name}")
    content = format_messages(messages)
    _run_obsidian(f'append path="{path}" content="{content}"')
