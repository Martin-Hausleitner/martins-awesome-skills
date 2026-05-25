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

    def test_exhaustive_market_mode_and_context_files(self):
        prompt = build_prompt(
            topic="Best AI coding agents",
            use_case="team dashboard for many agents",
            candidate_count=100,
            minimum_candidates=10,
            language="de",
            market_depth="exhaustive",
            context_files=["/tmp/known-candidates.csv", "/tmp/requirements.md"],
        )

        self.assertIn("Reize den Markt", prompt)
        self.assertIn("Ziel mindestens 100", prompt)
        self.assertIn("Market Map", prompt)
        self.assertIn("known-candidates.csv", prompt)
        self.assertIn("requirements.md", prompt)
        self.assertIn("Kontextpaket", prompt)

    def test_standard_mode_does_not_force_exhaustive_language(self):
        prompt = build_prompt(
            topic="Best small libraries",
            use_case="choose a package",
            candidate_count=20,
            minimum_candidates=10,
            language="en",
        )

        self.assertIn("Find and compare ideally 20 relevant candidates", prompt)
        self.assertNotIn("Exhaust the market as far as reasonable", prompt)


if __name__ == "__main__":
    unittest.main()
