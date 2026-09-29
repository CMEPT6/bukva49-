import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from bukva49.engine import EVOLVED, execute, make_tasks
from bukva49.pipeline import BukvaAgentPipeline


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


if __name__ == "__main__":
    unittest.main()
