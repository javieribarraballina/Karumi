"""
Unit and integration tests for eval module (Andrés: Eval, Deploy, Pitch)
Compatible with both pytest and standard unittest
"""

import unittest
from pathlib import Path
from eval.run_eval import load_ground_truths, get_mock_or_sample_map, evaluate_site, format_results_markdown


class TestEvalModule(unittest.TestCase):
    def test_load_ground_truths(self):
        gt_dir = Path(__file__).resolve().parent.parent / "eval" / "ground_truth"
        gts = load_ground_truths(gt_dir)
        self.assertGreaterEqual(len(gts), 2, "Should load at least books.toscrape and the-internet")
        self.assertIn("https://books.toscrape.com", gts)

    def test_evaluate_site_metrics(self):
        app_url = "https://books.toscrape.com"
        gt = {
            "screens": ["Home", "Travel", "Mystery", "Basket"],
            "url_to_screen": {
                "^https?://books\\.toscrape\\.com/?$": "Home",
                ".*travel.*": "Travel"
            },
            "paths": [{"from": "Home", "to": "Travel"}]
        }
        site_map = get_mock_or_sample_map(app_url)
        metrics = evaluate_site(app_url, gt, site_map)

        self.assertGreater(metrics["coverage_pct"], 0)
        self.assertGreater(metrics["dedupe_ratio"], 0)
        self.assertGreater(metrics["top1_acc"], 50)
        self.assertEqual(metrics["path_success_pct"], 100.0)
        self.assertGreater(metrics["estimated_cost_usd"], 0)

    def test_format_results_markdown(self):
        sample_metrics = [{
            "app": "https://books.toscrape.com",
            "gt_screens_count": 8,
            "found_screens_count": 7,
            "coverage_pct": 87.5,
            "dedupe_ratio": 0.88,
            "top1_acc": 87.5,
            "top3_acc": 100.0,
            "path_success_pct": 100.0,
            "crawl_seconds": 12.4,
            "llm_calls": 7,
            "estimated_cost_usd": 0.0084
        }]
        md = format_results_markdown(sample_metrics)
        self.assertIn("# Atlas Evaluation Results", md)
        self.assertIn("books.toscrape.com", md)
        self.assertIn("87.5%", md)


if __name__ == "__main__":
    unittest.main()
