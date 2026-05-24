import json
import contextlib
import io
import tempfile
import threading
import unittest
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.ai_research_output_publisher import main


class FakeNotionHandler(BaseHTTPRequestHandler):
    received = None

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("content-length", "0"))
        FakeNotionHandler.received = {
            "path": self.path,
            "authorization": self.headers.get("authorization"),
            "body": json.loads(self.rfile.read(length).decode("utf-8")),
        }
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"id": "page_123", "url": "https://notion.example/page_123"}).encode("utf-8"))

    def log_message(self, *_args):
        return


class ResearchOutputPublisherTests(unittest.TestCase):
    def test_render_multiple_results_with_links_metrics_and_copy_button(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_path = root / "results.json"
            message_path = root / "message.md"
            status_path = root / "status.json"
            payload_path = root / "payload.json"
            input_path.write_text(json.dumps(sample_batch()), encoding="utf-8")

            code = run_cli([
                "render",
                "--input",
                str(input_path),
                "--message-output",
                str(message_path),
                "--status-output",
                str(status_path),
                "--payload-output",
                str(payload_path),
                "--json",
            ])

            self.assertEqual(code, 0)
            message = message_path.read_text(encoding="utf-8")
            self.assertIn("✅ **Research fertig: Agent skill research**", message)
            self.assertIn("[Deep Research](https://research.example/obsidian)", message)
            self.assertIn("[PSPin](https://pspin.example/obsidian)", message)
            self.assertIn("Ø Recherche: 11m 0s", message)
            self.assertIn("Copy-Text", message)

            status = json.loads(status_path.read_text(encoding="utf-8"))
            self.assertEqual(status["metrics"]["result_count"], 2)
            self.assertEqual(status["metrics"]["average_total_human"], "14m 0s")
            self.assertTrue(any(button["type"] == "copy_to_clipboard" for button in status["buttons"]))

            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            first_heading = payload["children"][0]
            self.assertEqual(first_heading["type"], "heading_2")
            self.assertEqual(first_heading["heading_2"]["rich_text"][0]["text"]["content"], "Summary")
            self.assertIn("Full Text", json.dumps(payload))

    def test_publish_notion_dry_run_does_not_call_external_endpoint(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_path = root / "results.json"
            status_path = root / "status.json"
            input_path.write_text(json.dumps(sample_batch()), encoding="utf-8")

            code = run_cli([
                "publish-notion",
                "--input",
                str(input_path),
                "--parent-page-id",
                "parent_123",
                "--notion-api-url",
                "http://127.0.0.1:9/v1/pages",
                "--status-output",
                str(status_path),
                "--json",
            ])

            self.assertEqual(code, 0)
            status = json.loads(status_path.read_text(encoding="utf-8"))
            self.assertEqual(status["notion"]["status"], "planned")
            self.assertFalse(status["notion"]["external_write"])

    def test_publish_notion_live_against_fake_endpoint(self):
        server = HTTPServer(("127.0.0.1", 0), FakeNotionHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                input_path = root / "results.json"
                status_path = root / "status.json"
                input_path.write_text(json.dumps(sample_batch()), encoding="utf-8")

                code = run_cli([
                    "publish-notion",
                    "--input",
                    str(input_path),
                    "--parent-page-id",
                    "parent_123",
                    "--notion-api-url",
                    f"http://127.0.0.1:{server.server_port}/v1/pages",
                    "--notion-token",
                    "test-token",
                    "--allow-external-write",
                    "--status-output",
                    str(status_path),
                    "--json",
                ])

                self.assertEqual(code, 0)
                self.assertEqual(FakeNotionHandler.received["path"], "/v1/pages")
                self.assertEqual(FakeNotionHandler.received["authorization"], "Bearer test-token")
                self.assertEqual(FakeNotionHandler.received["body"]["parent"]["page_id"], "parent_123")
                status = json.loads(status_path.read_text(encoding="utf-8"))
                self.assertEqual(status["notion"]["status"], "created")
                self.assertEqual(status["notion"]["url"], "https://notion.example/page_123")
                self.assertIn("Open Notion", json.dumps(status["buttons"]))
        finally:
            server.shutdown()
            server.server_close()


def sample_batch():
    return {
        "job_id": "batch-1",
        "title": "Agent skill research",
        "results": [
            {
                "title": "Obsidian AI Plugins",
                "provider": "gemini",
                "mode": "deep-research",
                "status": "completed",
                "deep_research_url": "https://research.example/obsidian",
                "pspin_url": "https://pspin.example/obsidian",
                "summary": "The best plugins combine local indexing, team workflows, and clean markdown export.",
                "text": "Full report about Obsidian AI plugins.",
                "research_duration_seconds": 600,
                "total_duration_seconds": 780,
            },
            {
                "title": "Agent Skill Sync",
                "provider": "chatgpt",
                "mode": "deep-research",
                "status": "completed",
                "deep_research_url": "https://research.example/skills",
                "pspin_url": "https://pspin.example/skills",
                "summary": "Use a shared manifest, local adapters, and public-safe sync reports.",
                "text": "Full report about syncing skills between agents.",
                "research_duration_seconds": 720,
                "total_duration_seconds": 900,
            },
        ],
    }


def run_cli(argv):
    with contextlib.redirect_stdout(io.StringIO()):
        return main(argv)


if __name__ == "__main__":
    unittest.main()
