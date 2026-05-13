#!/usr/bin/env python3
"""Local E2E test with a fake Telegram Bot API server."""

from __future__ import annotations

import json
import subprocess
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "telegram_approval_gate.py"


class FakeTelegram(BaseHTTPRequestHandler):
    updates: list[dict] = []
    sent_payloads: list[dict] = []
    next_message_id = 100

    def log_message(self, *_args):  # keep test output clean
        return

    def _json(self, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        method = urlparse(self.path).path.strip("/")
        self.sent_payloads.append({"method": method, "payload": payload})
        if method == "sendMessage":
            mid = self.next_message_id
            FakeTelegram.next_message_id += 1
            if "reply_markup" in payload:
                FakeTelegram.updates.append(
                    {
                        "update_id": 1,
                        "callback_query": {
                            "id": "cb-1",
                            "data": "approval:send",
                            "message": {"message_id": mid, "chat": {"id": 12345}},
                        },
                    }
                )
            self._json({"ok": True, "result": {"message_id": mid}})
            return
        self._json({"ok": True, "result": True})

    def do_GET(self):
        method = urlparse(self.path).path.strip("/")
        if method == "getUpdates":
            updates, FakeTelegram.updates = FakeTelegram.updates, []
            self._json({"ok": True, "result": updates})
            return
        self._json({"ok": False, "description": "unknown"})


class TelegramApprovalGateTest(unittest.TestCase):
    def test_fake_telegram_approval_roundtrip(self):
        FakeTelegram.updates = []
        FakeTelegram.sent_payloads = []
        server = HTTPServer(("127.0.0.1", 0), FakeTelegram)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            proc = subprocess.run(
                [
                    "python3",
                    str(SCRIPT),
                    "--api-base",
                    f"http://127.0.0.1:{server.server_port}",
                    "--chat-id",
                    "12345",
                    "--draft",
                    "Bitte senden?",
                    "--timeout",
                    "2",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
        finally:
            server.shutdown()
            server.server_close()
        result = json.loads(proc.stdout)
        self.assertEqual(result["decision"], "send")
        send_payload = FakeTelegram.sent_payloads[0]["payload"]
        self.assertIn("inline_keyboard", send_payload["reply_markup"])
        self.assertEqual(send_payload["reply_markup"]["inline_keyboard"][0][0]["text"], "Senden")


if __name__ == "__main__":
    unittest.main()
