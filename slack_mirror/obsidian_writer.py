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
        header = f"# {title}\n\n{description}"
        _run_obsidian(f'create path="{path}" content="{header}" silent')


def format_messages(messages: list[dict]) -> str:
    """Format messages as markdown text for appending."""
    lines = []
    current_date = None

    for msg in messages:
        date = msg.get("date", "Unknown date")
        if date != current_date:
            lines.append(f"\n### {date}\n")
            current_date = date

        author = msg.get("author", "Unknown")
        time_str = msg.get("time", "")
        text = msg.get("text", "").replace('"', '\\"').replace("\n", "\\n")

        timestamp = f"{date} {time_str}".strip()
        lines.append(f"**{timestamp} - {author}** : {text}\n")

    return "\n".join(lines)


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

    content = "\n".join(lines).replace('"', '\\"')

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
    content = "\n".join(lines).replace('"', '\\"')

    if _file_exists(path):
        _run_obsidian(f'delete path="{path}" silent')
    _run_obsidian(f'create path="{path}" content="{content}" silent')
