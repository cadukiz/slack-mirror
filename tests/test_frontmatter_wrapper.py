#!/usr/bin/env python3
"""Tests for the frontmatter wrapper."""
import os
import tempfile
import unittest
from pathlib import Path

# Add parent src to path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from frontmatter_wrapper import add_frontmatter_to_file, process_directory


class TestFrontmatterWrapper(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_adds_frontmatter_to_plain_file(self):
        filepath = os.path.join(self.tmpdir, "test.md")
        Path(filepath).write_text("Hello world", encoding="utf-8")

        result = add_frontmatter_to_file(filepath, "test-project")
        self.assertTrue(result)

        content = Path(filepath).read_text(encoding="utf-8")
        self.assertTrue(content.startswith("---"))
        self.assertIn("source: slack-mirror", content)
        self.assertIn("project: test-project", content)
        self.assertIn("Hello world", content)

    def test_skips_file_with_existing_frontmatter(self):
        filepath = os.path.join(self.tmpdir, "test.md")
        Path(filepath).write_text("---\nsource: existing\n---\nContent", encoding="utf-8")

        result = add_frontmatter_to_file(filepath, "test-project")
        self.assertFalse(result)

    def test_nonexistent_file_returns_false(self):
        result = add_frontmatter_to_file("/nonexistent/file.md", "test-project")
        self.assertFalse(result)

    def test_extracts_channel_type_from_path(self):
        channels_dir = os.path.join(self.tmpdir, "channels")
        os.makedirs(channels_dir)
        filepath = os.path.join(channels_dir, "general.md")
        Path(filepath).write_text("Messages here", encoding="utf-8")

        add_frontmatter_to_file(filepath, "test-project")

        content = Path(filepath).read_text(encoding="utf-8")
        self.assertIn("subtype: channel", content)
        self.assertIn("name: general", content)

    def test_extracts_dm_type_from_path(self):
        dms_dir = os.path.join(self.tmpdir, "dms")
        os.makedirs(dms_dir)
        filepath = os.path.join(dms_dir, "John Doe.md")
        Path(filepath).write_text("DM content", encoding="utf-8")

        add_frontmatter_to_file(filepath, "test-project")

        content = Path(filepath).read_text(encoding="utf-8")
        self.assertIn("subtype: dm", content)

    def test_process_directory(self):
        # Create test structure
        channels_dir = os.path.join(self.tmpdir, "channels")
        os.makedirs(channels_dir)
        Path(os.path.join(channels_dir, "general.md")).write_text("Msg 1", encoding="utf-8")
        Path(os.path.join(channels_dir, "random.md")).write_text("Msg 2", encoding="utf-8")
        Path(os.path.join(self.tmpdir, "index.md")).write_text("Index", encoding="utf-8")

        count = process_directory(self.tmpdir, "test-project")
        self.assertEqual(count, 2)  # index.md should be skipped

    def test_process_nonexistent_directory(self):
        count = process_directory("/nonexistent/dir", "test-project")
        self.assertEqual(count, 0)

    def test_teams_source_type(self):
        filepath = os.path.join(self.tmpdir, "test.md")
        Path(filepath).write_text("Teams message", encoding="utf-8")

        add_frontmatter_to_file(filepath, "test-project", "teams")

        content = Path(filepath).read_text(encoding="utf-8")
        self.assertIn("platform: teams", content)


if __name__ == "__main__":
    unittest.main()
