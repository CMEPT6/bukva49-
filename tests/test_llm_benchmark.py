import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from llm_benchmark import (
    MODES,
    cases,
    extract_answer,
    grade,
    load_checkpoint,
    save_checkpoint,
    summarize,
)


class BenchmarkTest(unittest.TestCase):
    def test_modes_defined(self):
        self.assertIn("direct", MODES)
        self.assertIn("cot", MODES)
        self.assertIn("297", MODES)
        self.assertIn("full", MODES)

    def test_cases_reproducible_and_independently_graded(self):
        sample1 = cases(297, 3)
        sample2 = cases(297, 3)
        self.assertEqual(sample1, sample2)
        # 4 families: offer, inventory, rating, source -> 4 * 3 = 12 cases
        self.assertEqual(len(sample1), 12)
        families = {c.family for c in sample1}
        self.assertEqual(families, {"offer", "inventory", "rating", "source"})

        for case in sample1:
            # Check grading of exact expected answer
            res = grade(case, {
                "content": f'{{"answer": "{case.answer}"}}',
                "seconds": 0.5,
                "input_tokens": 100,
                "output_tokens": 20,
            })
            self.assertTrue(res["correct"], f"Failed for {case.id}: {case.answer}")
            self.assertTrue(res["valid_json"])

    def test_strict_answer_parsing(self):
        self.assertIsNone(extract_answer("Ответ: 123"))
        self.assertEqual(extract_answer('```json\n{"answer":"123"}\n```'), "123")
        self.assertEqual(extract_answer('```\n{"answer": 456}\n```'), "456")
        self.assertEqual(extract_answer('<think>Some deep thought</think>\n{"answer": "П3"}'), "П3")
        self.assertEqual(extract_answer('Текст до {"answer": "Вега"} текст после'), "Вега")

    def test_checkpointing(self):
        tmp_file = Path(__file__).parent / "test_cp.json"
        try:
            data = {
                "model": "test-model",
                "seed": 297,
                "cases_per_family": 1,
                "modes": {"direct": {"rows": [{"case_id": "test-0", "correct": True}]}},
            }
            save_checkpoint(tmp_file, data)
            loaded = load_checkpoint(tmp_file)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded["model"], "test-model")
        finally:
            if tmp_file.exists():
                tmp_file.unlink()
            tmp_temp = tmp_file.with_suffix(".tmp")
            if tmp_temp.exists():
                tmp_temp.unlink()


if __name__ == "__main__":
    unittest.main()
