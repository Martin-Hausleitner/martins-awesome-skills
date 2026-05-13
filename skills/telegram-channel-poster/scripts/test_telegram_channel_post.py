#!/usr/bin/env python3
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("telegram_channel_post.sh")


class TelegramChannelPostTests(unittest.TestCase):
    def run_script(self, *args, env=None):
        merged = os.environ.copy()
        merged.update(env or {})
        return subprocess.run(
            [str(SCRIPT), *args],
            text=True,
            capture_output=True,
            env=merged,
            check=False,
        )

    def test_dry_run_builds_payload_without_leaking_token(self):
        result = self.run_script(
            "--dry-run",
            "--text",
            "hello channel",
            env={
                "TELEGRAM_BOT_TOKEN": "123456:SECRET_TOKEN",
                "TELEGRAM_CHANNEL_ID": "@demo_channel",
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["method"], "sendMessage")
        self.assertEqual(payload["payload"]["chat_id"], "@demo_channel")
        self.assertEqual(payload["payload"]["text"], "hello channel")
        self.assertNotIn("SECRET_TOKEN", result.stdout)

    def test_reads_text_from_file(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as tmp:
            tmp.write("from file")
            tmp_path = tmp.name
        try:
            result = self.run_script(
                "--dry-run",
                "--file",
                tmp_path,
                env={
                    "TELEGRAM_BOT_TOKEN": "123456:SECRET_TOKEN",
                    "TELEGRAM_CHANNEL_ID": "-1001234567890",
                },
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["payload"]["text"], "from file")

    def test_requires_credentials_even_for_dry_run(self):
        result = self.run_script(
            "--dry-run",
            "--text",
            "missing token",
            env={"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHANNEL_ID": "@demo"},
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("TELEGRAM_BOT_TOKEN", result.stderr)

    def test_dry_run_shows_optional_notion_log_without_token(self):
        result = self.run_script(
            "--dry-run",
            "--text",
            "hello notion",
            env={
                "TELEGRAM_BOT_TOKEN": "123456:SECRET_TOKEN",
                "TELEGRAM_CHANNEL_ID": "@demo_channel",
                "TELEGRAM_NOTION_LOG": "true",
                "NOTION_PARENT_PAGE_ID": "page-id",
                "NOTION_TOKEN": "placeholder-notion-token",
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["notion_log"]["title"], "Telegram channel post")
        self.assertNotIn("SECRET_TOKEN", result.stdout)
        self.assertNotIn("placeholder-notion-token", result.stdout)


if __name__ == "__main__":
    unittest.main()
