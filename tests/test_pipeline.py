import unittest
import sys
from pathlib import Path

# Insert src at head of sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bukva49.engine import EVOLVED, execute, make_tasks
from bukva49.pipeline import BukvaAgentPipeline
from llm_benchmark import cases


class PipelinePackageTest(unittest.TestCase):
    def test_evolved_execution(self):
        task = make_tasks(1, 297, regime="misleading")[0]
        state = execute(EVOLVED, task)
        self.assertEqual(state.selected, task.answer)
        self.assertIsNotNone(state.artifact)
        self.assertTrue(state.artifact["source_verified"])

    def test_agent_pipeline_procurement(self):
        pipeline = BukvaAgentPipeline()
        candidates = [
            {"id": "c1", "name": "Fake Cheap", "price": 1000, "delivery": 100, "source_verified": False},
            {"id": "c2", "name": "Genuine Supplier", "price": 5000, "delivery": 500, "source_verified": True},
        ]
        result = pipeline.run("Закупка серверного оборудования", candidates=candidates)
        self.assertEqual(result.selected_id, "Genuine Supplier")
        self.assertEqual(result.best_score, 5500)
        self.assertIsNotNone(result.seal_hash)
        self.assertTrue(result.is_valid)

    def test_all_benchmark_families(self):
        """Test BukvaAgentPipeline against all 4 task families (40 cases total)."""
        pipeline = BukvaAgentPipeline()
        sample_cases = cases(seed=297, per_family=10)
        self.assertEqual(len(sample_cases), 40)

        for case in sample_cases:
            res = pipeline.run(case.question)
            self.assertEqual(
                res.selected_result,
                case.answer,
                f"Failed on case {case.id} (family={case.family}): expected {case.answer}, got {res.selected_result}",
            )
            self.assertTrue(res.is_valid)
            self.assertIsNotNone(res.seal_hash)

    def test_cryptographic_seal_tamper_detection(self):
        """Test that altering a single value in evidence changes the SHA-256 seal."""
        pipeline = BukvaAgentPipeline()
        candidates = [
            {"id": "c1", "name": "Vendor A", "price": 5000, "delivery": 500, "confirmed": True},
            {"id": "c2", "name": "Vendor B", "price": 6000, "delivery": 200, "confirmed": True},
        ]
        state1 = pipeline.run("Закупка серверов", candidates=candidates)
        seal1 = state1.seal_hash

        # Tamper: change price of Vendor B by 1 unit
        tampered_candidates = [
            {"id": "c1", "name": "Vendor A", "price": 5000, "delivery": 500, "confirmed": True},
            {"id": "c2", "name": "Vendor B", "price": 6001, "delivery": 200, "confirmed": True},
        ]
        state2 = pipeline.run("Закупка серверов", candidates=tampered_candidates)
        seal2 = state2.seal_hash

        self.assertNotEqual(seal1, seal2, "SHA-256 seal must detect tampering with raw candidate price!")


if __name__ == "__main__":
    unittest.main()
