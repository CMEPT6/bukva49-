"""Example 02: Baseline vs Evolved Formula Comparison.

Demonstrates why the genetic algorithm evolved the formula 'В-Е-М-Й-З'
(Вѣди -> Есть -> Мыслите -> Йота -> Земля) to outperform the human baseline '297'.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bukva49 import EVOLVED, FULL, P297, evaluate, make_tasks


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 70)
    print("  BUKVA-49: Genetic Search Verification Benchmark")
    print("=" * 70)

    # 50 tasks with adversarial traps (fake cheap prices, missing verification)
    tasks = make_tasks(count=50, seed=42, regime="misleading")

    print(f"\nEvaluating on {len(tasks)} adversarial/misleading tasks...\n")

    benchmarks = [
        ("Human Baseline (297)", P297, "Вѣди -> Фита -> Земля"),
        ("Classic Full Pipeline", FULL, "Вѣди -> Есть -> Мыслите -> Кси -> Фита -> Земля"),
        ("Evolved Pipeline (Record)", EVOLVED, "Вѣди -> Есть -> Мыслите -> Йота -> Земля"),
    ]

    for name, prog, desc in benchmarks:
        metrics = evaluate(prog, tasks)
        print(f"[{name}]")
        print(f"  Steps: {desc}")
        print(f"  Score:    {metrics['score']}")
        print(f"  Accuracy: {metrics['accuracy'] * 100:.1f}%")
        print(f"  Artifact: {metrics['artifact_rate'] * 100:.1f}%")
        print(f"  Mean Cost: {metrics['mean_cost']} steps")
        print("-" * 70)

    print("\nConclusion:")
    print("  Formula '297' fails because it lacks the 'Есть' (VERIFY) gate and gets")
    print("  trapped by unverified cheap offers.")
    print("  'EVOLVED' achieves 100% accuracy while cutting unnecessary steps by replacing")
    print("  'Кси' (sort) + 'Фита' (select) with a single atomic operator 'Йота' (minimum).")


if __name__ == "__main__":
    main()
