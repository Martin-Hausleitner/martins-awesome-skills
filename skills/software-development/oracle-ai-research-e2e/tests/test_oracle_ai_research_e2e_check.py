import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "oracle_ai_research_e2e_check.py"


def load_module():
    spec = importlib.util.spec_from_file_location("oracle_ai_research_e2e_check", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class OracleAiResearchE2ECheckTests(unittest.TestCase):
    def test_redacts_prompt_values(self):
        module = load_module()

        command = ["python3", "tool.py", "-p", "secret prompt", "--prompt", "another secret", "--mode", "agent"]

        self.assertEqual(
            module.redact_command(command),
            ["python3", "tool.py", "-p", "<redacted>", "--prompt", "<redacted>", "--mode", "agent"],
        )

    def test_parse_json_stdout_returns_dict_only(self):
        module = load_module()

        self.assertEqual(module.parse_json_stdout({"stdout": '{"ok": true}'}), {"ok": True})
        self.assertEqual(module.parse_json_stdout({"stdout": '["not", "dict"]'}), {})
        self.assertEqual(module.parse_json_stdout({"stdout": "not-json"}), {})

    def test_sanitizes_local_paths_from_public_json(self):
        module = load_module()

        text = '/Users/example/Documents/Playground/x --user-data-dir=/Users/example/Library/Application Support/BraveSoftware'
        sanitized = module.sanitize_text(text)

        self.assertNotIn("/Users/example", sanitized)
        self.assertIn("<user-path>", sanitized)
        self.assertIn("--user-data-dir=<redacted>", sanitized)

    def test_sanitizes_payload_recursively(self):
        module = load_module()

        payload = module.sanitize_payload({"repo_root": "/Users/example/private", "steps": [{"stdout": "/Users/example/log"}]})

        self.assertEqual(payload["repo_root"], "<user-path>")
        self.assertEqual(payload["steps"][0]["stdout"], "<user-path>")

    def test_repo_root_points_to_repository(self):
        module = load_module()

        root = module.repo_root_from_script()

        self.assertTrue((root / "skills/software-development/ai-research-browser/scripts/ai_research_browser.py").exists())

    def test_repo_root_can_be_supplied_by_environment(self):
        module = load_module()
        root = Path(tempfile.mkdtemp())
        marker = root / "skills/software-development/ai-research-browser/scripts"
        marker.mkdir(parents=True)
        (marker / "ai_research_browser.py").write_text("# marker\n", encoding="utf-8")
        old = os.environ.get("AI_RESEARCH_BROWSER_REPO_ROOT")
        os.environ["AI_RESEARCH_BROWSER_REPO_ROOT"] = str(root)
        try:
            self.assertEqual(module.repo_root_from_script(), root.resolve())
        finally:
            if old is None:
                os.environ.pop("AI_RESEARCH_BROWSER_REPO_ROOT", None)
            else:
                os.environ["AI_RESEARCH_BROWSER_REPO_ROOT"] = old


if __name__ == "__main__":
    unittest.main()
