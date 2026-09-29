"""Example 03: Autonomous Verifiable Procurement Agent.

Uses BukvaAgentPipeline to process raw multi-vendor quotes, verify sources,
calculate exact total costs, select the best candidate, and sign the result
with a cryptographic SHA-256 seal and an explainable audit trail.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bukva49 import BukvaAgentPipeline


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    pipeline = BukvaAgentPipeline()

    goal = "Закупить серверные модули памяти DDR5 ECC для кластера с надёжной верификацией поставщика"

    # Real-world candidate offers from 4 suppliers
    candidates = [
        {
            "id": "supp-omega-grey",
            "name": "Omega Store (Неофициальный импорт)",
            "price": 42000,
            "delivery": 12000,
            "warranty_months": 0,
            "source_verified": False,  # Suspicious / grey supplier!
            "notes": "Подозрительно низкая цена, без официальной гарантии",
        },
        {
            "id": "supp-serverpro",
            "name": "ServerPro Direct (Авторизованный дистрибьютор)",
            "price": 54000,
            "delivery": 2500,
            "warranty_months": 36,
            "source_verified": True,
            "notes": "Официальный партнёр вендора",
        },
        {
            "id": "supp-fastrack",
            "name": "FastRack Solutions",
            "price": 52000,
            "delivery": 6000,
            "warranty_months": 24,
            "source_verified": True,
            "notes": "Склад в Москве, быстрая доставка",
        },
        {
            "id": "supp-techhub",
            "name": "TechHub Enterprise",
            "price": 59000,
            "delivery": 0,
            "warranty_months": 36,
            "source_verified": True,
            "notes": "Бесплатная доставка курьером",
        },
    ]

    print("=" * 75)
    print("   BUKVA-49 AUTONOMOUS PROCUREMENT ROBOT")
    print("=" * 75)
    print(f"Goal: {goal}")
    print(f"Incoming Quotes: {len(candidates)}")

    state = pipeline.run(goal, candidates=candidates)

    print("\n[Cognitive Pipeline Audit Trail]")
    for step in state.audit_trail:
        print(f"  • {step}")

    print("\n[Final Decision]")
    print(f"  Selected Vendor: {state.selected_id}")
    print(f"  Total Cost:      {state.best_score} руб.")
    print(f"  Cryptographic Seal: SHA256[{state.seal_hash}]")

    print("\n[Verifiable Audit Artifact]")
    print(json.dumps(state.artifact, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
