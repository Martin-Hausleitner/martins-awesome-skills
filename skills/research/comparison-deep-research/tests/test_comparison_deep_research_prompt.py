import contextlib
import io
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.comparison_deep_research_prompt import build_prompt, main


class ComparisonDeepResearchPromptTests(unittest.TestCase):
    def test_prompt_enforces_scorecard_links_categories_and_counts(self):
        prompt = build_prompt(
            topic="Best Discord voice agents",
            use_case="private assistant that can speak live in Discord and run research tasks",
            candidate_count=50,
            minimum_candidates=10,
            language="de",
        )

        self.assertIn("50 relevante Kandidaten", prompt)
        self.assertIn("mindestens 10", prompt)
        self.assertIn("GitHub: Markdown-Link", prompt)
        self.assertIn("Website/Docs: Markdown-Link", prompt)
        self.assertIn("genau fünf große Bewertungskategorien", prompt)
        self.assertIn("exakt 100 Punkte", prompt)
        self.assertIn("Total /100", prompt)
        self.assertIn("Mermaid-Diagramm", prompt)
        self.assertIn("Best by Scenario", prompt)

    def test_candidate_count_never_drops_below_minimum(self):
        prompt = build_prompt(
            topic="Small ecosystem",
            use_case="choose a library",
            candidate_count=3,
            minimum_candidates=10,
            language="en",
        )

        self.assertIn("10 relevant candidates", prompt)
        self.assertIn("Final report language: English", prompt)
        self.assertIn("No invented GitHub links", prompt)
        self.assertNotIn("Führe ein Deep Research", prompt)

    def test_cli_writes_prompt_file(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "prompt.md"
            with contextlib.redirect_stdout(io.StringIO()):
                code = main([
                    "--topic",
                    "Obsidian AI plugins",
                    "--use-case",
                    "rebuild Notion-like team knowledge workflows",
                    "--candidate-count",
                    "50",
                    "--output",
                    str(output),
                ])

            self.assertEqual(code, 0)
            text = output.read_text(encoding="utf-8")
            self.assertIn("Obsidian AI plugins", text)
            self.assertIn("rebuild Notion-like team knowledge workflows", text)
            self.assertIn("Keine erfundenen GitHub-Links", text)


if __name__ == "__main__":
    unittest.main()
