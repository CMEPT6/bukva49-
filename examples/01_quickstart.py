"""Example 01: Quickstart with BUKVA-49.

Demonstrates minimal usage of the deterministic cognitive pipeline.
"""
import json
import sys
from pathlib import Path

# Add src to path for local running without prior installation
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bukva49 import EVOLVED, execute, make_tasks


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    # 1. Generate a test procurement task with misleading trap offers
    task = make_tasks(count=1, seed=297, regime="misleading")[0]
    print(f"Task #{task.id} (Regime: {task.regime})")
    print(f"Number of candidates: {len(task.offers)}")
    for o in task.offers:
        print(f"  - Offer {o.id}: price={o.price}, delivery={o.delivery}, verified={o.source_verified}")

    # 2. Execute the evolved cognitive formula: Вѣди -> Есть -> Мыслите -> Йота -> Земля
    print(f"\nExecuting pipeline: {' -> '.join(EVOLVED)}")
    state = execute(EVOLVED, task)

    # 3. Inspect final state and grounded artifact
    print(f"Result selected: {state.selected}")
    print(f"Ground truth answer: {task.answer}")
    print(f"Verification passed: {state.selected == task.answer}")
    print("\nGrounded Artifact:")
    print(json.dumps(state.artifact, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
