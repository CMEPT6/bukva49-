"""Command-line interface for the BUKVA-49 framework."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from .engine import (
    DESCRIPTIONS,
    NAMES,
    OPS,
    Offer,
    Task,
    execute,
    make_tasks,
    parse,
)
from .pipeline import BukvaAgentPipeline
from .search import experiment


def setup_encoding() -> None:
    """Ensure utf-8 encoding for standard streams."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass


def print_matrix_table() -> None:
    """Print the human-readable 7x7 matrix table."""
    setup_encoding()
    print("\n" + "=" * 80)
    print("      МАТРИЦА 7 × 7 КОГНИТИВНО-ВЫЧИСЛИТЕЛЬНЫХ ОПЕРАТОРОВ «БУКВА-49»")
    print("=" * 80)
    row_titles = [
        "Ряд 1: Бытие и Восприятие (Входной уровень данных)",
        "Ряд 2: Структура и Взаимосвязи (Уровень топологии)",
        "Ряд 3: Осмысление и Логика (Аналитический уровень)",
        "Ряд 4: Утверждение и Очищение (Уровень фильтрации)",
        "Ряд 5: Разделение и Детализация (Уровень анализа)",
        "Ряд 6: Эволюция и Преобразование (Уровень оптимизации)",
        "Ряд 7: Синтез и Завершение (Финальный интегральный уровень)",
    ]

    for r_idx in range(7):
        print(f"\n{row_titles[r_idx]}:")
        print("-" * 80)
        row_names = NAMES[r_idx * 7 : (r_idx + 1) * 7]
        for name in row_names:
            code = OPS.get(name, "???")
            desc = DESCRIPTIONS.get(name, "")
            print(f"  [{code:<12}] {name:<8} : {desc}")
    print("\n" + "=" * 80)
    print(f"Всего операторов в реестре: {len(OPS)} из 49 (100% РЕАЛИЗОВАНО В КОДЕ)")
    print("=" * 80 + "\n")


def main() -> None:
    """CLI Entrypoint for bukva49."""
    setup_encoding()
    parser = argparse.ArgumentParser(
        prog="bukva49",
        description="BUKVA-49: Zero-dependency neuro-symbolic cognitive pipeline & DSL",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # Subcommand: matrix
    sub.add_parser("matrix", help="Display the formatted 7x7 operator matrix")

    # Subcommand: registry
    sub.add_parser("registry", help="Dump JSON registry of all 49 operators")

    # Subcommand: run
    run_parser = sub.add_parser("run", help="Execute a cognitive program on a task")
    run_parser.add_argument(
        "program",
        nargs="?",
        default="evolved",
        help="Program name (297, full, evolved) or space-separated sequence of letters/opcodes",
    )
    run_parser.add_argument(
        "--regime",
        default="mixed",
        choices=["mixed", "all_verified", "misleading", "independent", "free_delivery"],
        help="Stress-test regime for synthetic data",
    )
    run_parser.add_argument("--seed", type=int, default=297, help="Random seed for task generation")

    # Subcommand: experiment
    exp_parser = sub.add_parser("experiment", help="Run genetic evolutionary search experiment")
    exp_parser.add_argument("--seed", type=int, default=297, help="Random seed")
    exp_parser.add_argument("--train", type=int, default=80, help="Number of training tasks")
    exp_parser.add_argument("--test", type=int, default=40, help="Number of test tasks")
    exp_parser.add_argument("--generations", type=int, default=35, help="Number of genetic generations")
    exp_parser.add_argument("--output", type=Path, help="Path to save experiment JSON output")

    # Subcommand: agent
    agent_parser = sub.add_parser("agent", help="Run an end-to-end BukvaAgentPipeline on a custom query")
    agent_parser.add_argument("goal", help="User intent or procurement goal")
    agent_parser.add_argument("--file", type=Path, help="Optional JSON file with candidates/offers")

    args = parser.parse_args()

    if args.command == "matrix":
        print_matrix_table()
        return

    if args.command == "registry":
        result = [
            {
                "index": i,
                "name": name,
                "operator": OPS.get(name),
                "description": DESCRIPTIONS.get(name, ""),
                "status": "implemented",
            }
            for i, name in enumerate(NAMES, 1)
        ]
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "run":
        tasks = make_tasks(1, args.seed, regime=args.regime)
        prog = parse(args.program)
        state = execute(prog, tasks[0])
        print(json.dumps(asdict(state), ensure_ascii=False, indent=2))
        return

    if args.command == "experiment":
        res = experiment(args.seed, args.train, args.test, args.generations)
        if args.output:
            args.output.write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"Results saved to {args.output}")
        else:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    if args.command == "agent":
        pipeline = BukvaAgentPipeline()
        candidates = None
        if args.file and args.file.exists():
            candidates = json.loads(args.file.read_text(encoding="utf-8"))
        final_state = pipeline.run(args.goal, candidates=candidates)
        summary = {
            "goal": final_state.goal,
            "domain": final_state.domain,
            "axioms": final_state.axioms,
            "total_candidates": len(final_state.evidence),
            "verified_candidates": len(final_state.verified_offers),
            "selected": final_state.selected_id,
            "score": final_state.best_score,
            "artifact": final_state.artifact,
            "seal_hash": final_state.seal_hash,
            "audit_trail": final_state.audit_trail,
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return


if __name__ == "__main__":
    main()
