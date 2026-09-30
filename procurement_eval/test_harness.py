import json
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import eval_harness as h

LOTS = json.loads((Path(__file__).parent / "lots_seed.json").read_text(encoding="utf-8"))
def lot(i): return next(l for l in LOTS if l["id"] == i)

class HarnessTests(unittest.TestCase):
    def test_gold_is_consistent(self):
        self.assertTrue(h.check_gold(LOTS))

    def test_oracle_extraction_passes_validation(self):
        b = h.MockBackend("mock-oracle")
        for l in LOTS:
            ext = h.parse_json(b.ask("extract", "", l, 0))
            self.assertNotIsInstance(h.validate_extraction(ext, l), str, l["id"])

    def test_hallucinated_constraint_is_rejected(self):
        l = lot("S001"); ext = h.parse_json(h.MockBackend("mock-oracle").ask("extract", "", l, 0))
        ext["constraints"]["max_budget"] = 1000; ext["quotes"]["max_budget"] = "бюджет 1000 тг"
        self.assertIn("цитатой", h.validate_extraction(ext, l))

    def test_missing_key_is_rejected(self):
        l = lot("S003"); ext = h.parse_json(h.MockBackend("mock-oracle").ask("extract", "", l, 0))
        del ext["constraints"]["max_budget"]
        self.assertIsInstance(h.validate_extraction(ext, l), str)

    def test_threshold_without_base_is_rejected(self):
        l = lot("S004"); ext = h.parse_json(h.MockBackend("mock-oracle").ask("extract", "", l, 0))
        ext["constraints"]["reference_price"] = None
        self.assertIn("демпинг", h.validate_extraction(ext, l))

    def test_broken_json_is_refused_not_guessed(self):
        class Broken:
            def ask(self, *a): return '{"constraints": {'
        for cfg in ("simple", "bukva"):
            self.assertIsNone(h.CONFIGS[cfg](Broken(), lot("S001"), 0)[0])

    def test_no_winner_lot_expects_refusal(self):
        self.assertIsNone(lot("S006")["gold"]["winner_id"])
        self.assertIsNone(h.plain_decide(lot("S006")["gold"]["constraints"], lot("S006")["gold"]["candidates"]))

if __name__ == "__main__":
    unittest.main()
