import unittest
import sys
from pathlib import Path

# Insert src at head of sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bukva49.engine import EVOLVED, execute, make_tasks
from bukva49.pipeline import BukvaAgentPipeline, TaskConstraints, TaskSpecification
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

    def test_max_budget_enforcement(self):
        """Test that candidates exceeding max_budget are disqualified, failing closed if all exceed."""
        pipeline = BukvaAgentPipeline()
        candidates = [
            {"id": "c1", "name": "Vendor Cheap", "price": 40000, "delivery": 2000, "confirmed": True},
            {"id": "c2", "name": "Vendor Expensive", "price": 70000, "delivery": 5000, "confirmed": True},
        ]
        # 1. Budget of 50,000 allows Vendor Cheap (42,000) and disqualifies Vendor Expensive (75,000)
        spec = TaskSpecification(
            domain="offer",
            goal="Закупка оборудования",
            candidates=candidates,
            constraints=TaskConstraints(max_budget=50000),
        )
        res1 = pipeline.run_spec(spec)
        self.assertTrue(res1.is_valid)
        self.assertEqual(res1.selected_id, "Vendor Cheap")
        self.assertEqual(res1.best_score, 42000)

        # 2. Strict budget of 30,000 disqualifies both -> FAIL-CLOSED
        spec_strict = TaskSpecification(
            domain="offer",
            goal="Закупка оборудования",
            candidates=candidates,
            constraints=TaskConstraints(max_budget=30000),
        )
        res2 = pipeline.run_spec(spec_strict)
        self.assertFalse(res2.is_valid)
        self.assertIsNone(res2.selected_id)
        self.assertEqual(res2.error, "All candidates disqualified")
        self.assertEqual(res2.artifact["status"], "REJECTED")

    def test_fail_closed_on_unresolved_constraints(self):
        """Test that pipeline refuses to certify when delivery constraint text is ambiguous."""
        pipeline = BukvaAgentPipeline()
        candidates = [
            {"id": "c1", "name": "Vendor Late", "price": 10000, "delivery": 500, "days": 9, "confirmed": True}
        ]
        # Ambiguous prompt mentions delivery restriction without specific extractable number
        res = pipeline.run("Срочная закупка, дедлайн критичен, поставка в минимальный срок", candidates=candidates)
        self.assertFalse(res.is_valid)
        self.assertIsNone(res.selected_id)
        self.assertEqual(res.error, "Unresolved delivery constraint (fail-closed)")

    def test_negative_delivery_phrasing_does_not_fail(self):
        """Test that explicit negation 'условий по срокам нет' does not trigger fail-closed."""
        pipeline = BukvaAgentPipeline()
        candidates = [
            {"id": "c1", "name": "Vendor Normal", "price": 10000, "delivery": 500, "days": 30, "confirmed": True}
        ]
        res = pipeline.run("Закупка материалов. Условий по срокам нет.", candidates=candidates)
        self.assertTrue(res.is_valid)
        self.assertEqual(res.selected_id, "Vendor Normal")

    def test_full_256bit_hmac_signature(self):
        """Test that HMAC signature produces full 64-hex (256-bit) tamper-proof signature."""
        pipeline = BukvaAgentPipeline(secret_key="my-audit-secret-key-2026")
        candidates = [
            {"id": "c1", "name": "Approved Vendor", "price": 25000, "delivery": 1000, "confirmed": True}
        ]
        res = pipeline.run("Закупка техники", candidates=candidates)
        self.assertTrue(res.is_valid)
        self.assertEqual(len(res.seal_hash), 64, "HMAC-SHA256 must be full 64 hex characters (256-bit)!")
        self.assertEqual(res.artifact["signature_type"], "HMAC-SHA256")

    def test_strict_negation_and_boundary_phrase(self):
        """Test that 'Любой срок свыше 5 дней недопустим' correctly enforces max_days=5."""
        pipeline = BukvaAgentPipeline()
        candidates = [
            {"id": "A", "name": "Vendor Fast", "price": 2000, "delivery": 100, "days": 3, "confirmed": True},
            {"id": "B", "name": "Vendor Slow", "price": 1000, "delivery": 50, "days": 9, "confirmed": True},
        ]
        res = pipeline.run("Закупка серверов. Любой срок свыше 5 дней недопустим.", candidates=candidates)
        self.assertTrue(res.is_valid)
        self.assertEqual(res.selected_id, "Vendor Fast")
        self.assertEqual(res.best_score, 2100)

    def test_dumping_threshold_without_reference_price_fails_closed(self):
        """Test that providing dumping_threshold_pct without reference_price fails closed."""
        pipeline = BukvaAgentPipeline()
        spec = TaskSpecification(
            domain="offer",
            goal="Закупка оборудования",
            candidates=[{"id": "c1", "name": "Vendor", "price": 1000, "delivery": 0, "confirmed": True}],
            constraints=TaskConstraints(dumping_threshold_pct=20.0, reference_price=None),
        )
        res = pipeline.run_spec(spec)
        self.assertFalse(res.is_valid)
        self.assertEqual(res.error, "Dumping threshold specified without reference_price")
        self.assertEqual(res.artifact["status"], "REJECTED")

    def test_dumping_disqualification_and_anti_dumping_deposit(self):
        """Test dumping disqualification vs admission with calculated anti-dumping deposit."""
        pipeline = BukvaAgentPipeline()
        # Reference price 100,000, dumping threshold 20% -> floor = 80,000
        # Vendor Cheap is 60,000 (< 80,000)
        # Vendor Normal is 90,000
        candidates = [
            {"id": "c1", "name": "Vendor Cheap", "price": 60000, "delivery": 0, "confirmed": True},
            {"id": "c2", "name": "Vendor Normal", "price": 90000, "delivery": 0, "confirmed": True},
        ]

        # Case 1: allow_dumping_with_deposit=False -> Vendor Cheap is disqualified, Vendor Normal wins
        spec_no_deposit = TaskSpecification(
            domain="offer",
            goal="Закупка",
            candidates=candidates,
            constraints=TaskConstraints(dumping_threshold_pct=20.0, reference_price=100000, allow_dumping_with_deposit=False),
        )
        res1 = pipeline.run_spec(spec_no_deposit)
        self.assertTrue(res1.is_valid)
        self.assertEqual(res1.selected_id, "Vendor Normal")
        self.assertIsNone(res1.anti_dumping_deposit)

        # Case 2: allow_dumping_with_deposit=True -> Vendor Cheap admitted with deposit = 80000 - 60000 = 20000
        spec_with_deposit = TaskSpecification(
            domain="offer",
            goal="Закупка",
            candidates=candidates,
            constraints=TaskConstraints(dumping_threshold_pct=20.0, reference_price=100000, allow_dumping_with_deposit=True),
        )
        res2 = pipeline.run_spec(spec_with_deposit)
        self.assertTrue(res2.is_valid)
        self.assertEqual(res2.selected_id, "Vendor Cheap")
        self.assertEqual(res2.anti_dumping_deposit, 20000.0)
        self.assertEqual(res2.artifact["required_anti_dumping_deposit"], 20000.0)

    def test_task_constraints_schema_all_fields(self):
        """Test TaskConstraints dataclass with all 6 documented fields."""
        c = TaskConstraints(
            max_days=10,
            require_confirmed=True,
            max_budget=500000,
            dumping_threshold_pct=15.0,
            reference_price=400000,
            allow_dumping_with_deposit=True,
        )
        self.assertEqual(c.max_days, 10)
        self.assertTrue(c.require_confirmed)
        self.assertEqual(c.max_budget, 500000)
        self.assertEqual(c.dumping_threshold_pct, 15.0)
        self.assertEqual(c.reference_price, 400000)
        self.assertTrue(c.allow_dumping_with_deposit)


if __name__ == "__main__":
    unittest.main()
