#!/usr/bin/env python3
"""
Frontmatter wrapper for Slack Mirror output.
Adds standardized YAML frontmatter to messages written to the vault
so Unstoppable Core can classify and route them.
"""
import os
import re
import sys
from datetime import datetime
from pathlib import Path


def add_frontmatter_to_file(filepath: str, project: str, source_type: str = "slack") -> bool:
    """Add YAML frontmatter to a vault file if it doesn't already have it."""
    path = Path(filepath)
    if not path.exists():
        return False

    content = path.read_text(encoding="utf-8")

    # Skip if already has frontmatter
    if content.startswith("---"):
        return False

    # Extract channel/DM/group name from path
    parts = path.parts
    context_type = "channel"
    context_name = path.stem
    for i, part in enumerate(parts):
        if part in ("channels", "dms", "groups"):
            context_type = part.rstrip("s")  # channel, dm, group
            if i + 1 < len(parts):
                context_name = parts[i + 1].replace(".md", "")
            break

    timestamp = datetime.now().isoformat()

    frontmatter = f"""---
source: slack-mirror
project: {project}
type: slack-message
subtype: {context_type}
name: {context_name}
timestamp: {timestamp}
platform: {source_type}
---

"""

    path.write_text(frontmatter + content, encoding="utf-8")
    return True


def process_directory(vault_dir: str, project: str, source_type: str = "slack") -> int:
    """Process all markdown files in a directory, adding frontmatter where missing."""
    count = 0
    vault_path = Path(vault_dir)

    if not vault_path.exists():
        print(f"Directory not found: {vault_dir}", file=sys.stderr)
        return 0

    for md_file in vault_path.rglob("*.md"):
        if md_file.name == "index.md":
            continue
        if add_frontmatter_to_file(str(md_file), project, source_type):
            count += 1
            print(f"  Added frontmatter: {md_file.name}")

    return count


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Add YAML frontmatter to Slack Mirror output files")
    parser.add_argument("--vault-dir", required=True, help="Path to the vault project context directory")
    parser.add_argument("--project", required=True, help="Project ID")
    parser.add_argument("--source", default="slack", choices=["slack", "teams"], help="Source platform")

    args = parser.parse_args()

    count = process_directory(args.vault_dir, args.project, args.source)
    print(f"Processed {count} files")


if __name__ == "__main__":
    main()
