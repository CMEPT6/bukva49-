import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from bukva49 import NAMES, OPS, P297, ProgramError, evaluate, execute, make_tasks, parse, search


class EngineTest(unittest.TestCase):
    def test_registry_and_alias(self):
        self.assertEqual(len(NAMES), 49)
        self.assertEqual(len(set(NAMES)), 49)
        self.assertEqual(len(OPS), 49)
        self.assertEqual(parse("297"), P297)
        with self.assertRaises(ProgramError):
            parse("НесуществующаяБуква")

    def test_all_49_operators_defined_and_executable(self):
        task = make_tasks(1, 42)[0]
        for name in NAMES:
            prog = parse(name)
            self.assertEqual(prog, (name,))
            # Each operator should execute on task without throwing Not implemented
            try:
                state = execute(prog, task)
                self.assertIn(name, state.trace)
            except ProgramError as e:
                # Precondition errors (like Земля without selection) are normal for partial functions
                self.assertNotIn("Not implemented", str(e))

    def test_extended_pipeline_execution(self):
        task = make_tasks(1, 297)[0]
        # Full chain from Init to Seal
        extended_prog = parse("Азъ Боги Вѣди Добро Есть Мыслите Кси Фита Земля Ижа")
        state = execute(extended_prog, task)
        self.assertIsNotNone(state.selected)
        self.assertIsNotNone(state.artifact)
        self.assertIsNotNone(state.sealed_hash)
        self.assertTrue(state.axioms.get("require_verified"))

    def test_verified_selection(self):
        tasks = make_tasks(30, 9)
        program = parse("Вѣди Есть Мыслите Кси Фита Земля")
        self.assertEqual(evaluate(program, tasks)["accuracy"], 1.0)
        self.assertLess(evaluate(P297, tasks)["accuracy"], 1.0)
        self.assertGreater(evaluate(P297, make_tasks(20, 9, "free_delivery"))["accuracy"], 0.0)

    def test_preconditions_and_reproducibility(self):
        task = make_tasks(1, 25)[0]
        with self.assertRaises(ProgramError):
            execute(parse("Земля"), task)
        self.assertEqual(search(make_tasks(20, 3), 5, 12), search(make_tasks(20, 3), 5, 12))


if __name__ == "__main__":
    unittest.main()
