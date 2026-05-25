import unittest

from scripts.deep_research_prompt_budget import classify_prompt


class DeepResearchPromptBudgetTests(unittest.TestCase):
    def test_short_prompt_is_ideal(self):
        result = classify_prompt("Compare the best Obsidian AI plugins.")
        self.assertEqual(result["level"], "ideal")
        self.assertTrue(result["allowed"])

    def test_standard_prompt_is_allowed(self):
        result = classify_prompt("x" * 10_000)
        self.assertEqual(result["level"], "standard_max")
        self.assertTrue(result["allowed"])

    def test_large_prompt_requires_review(self):
        result = classify_prompt("x" * 18_000)
        self.assertEqual(result["level"], "review")
        self.assertFalse(result["allowed"])

    def test_huge_prompt_blocks(self):
        result = classify_prompt("x" * 30_000)
        self.assertEqual(result["level"], "block")
        self.assertFalse(result["allowed"])


if __name__ == "__main__":
    unittest.main()

