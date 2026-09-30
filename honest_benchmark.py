"""Честный научный бенчмарк для BUKVA-49 (Honest Benchmark & Audit).

Сравнивает FSM-конвейер BUKVA-49 с эталонной функцией Python,
анализирует активность операторов и измеряет устойчивость к искажениям данных.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from bukva49 import EVOLVED, NAMES, OPS, Task, evaluate, execute, make_tasks
from bukva49.pipeline import BukvaAgentPipeline
from llm_benchmark import cases
from operator_table import LABELS, count_noop_ops


def setup_encoding() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass


def direct_reference(task: Task) -> str:
    """Эталонная 3-строчная функция Python (Ground Truth)."""
    valid = [o for o in task.offers if o.source_verified]
    if not valid:
        return task.offers[0].id
    return min(valid, key=lambda o: (o.price + o.delivery, o.id)).id


def run_control_comparison(count: int = 4000, seed: int = 42) -> dict:
    print(f"\n[1/4] Сравнение EVOLVED с эталонной функцией Python ({count} задач)...")
    tasks = make_tasks(count, seed, regime="mixed")

    # Pure Python reference
    t0 = time.perf_counter()
    ref_answers = [direct_reference(t) for t in tasks]
    t_ref = time.perf_counter() - t0

    # BUKVA-49 EVOLVED FSM
    t0 = time.perf_counter()
    fsm_answers = [execute(EVOLVED, t).selected for t in tasks]
    t_fsm = time.perf_counter() - t0

    matches = sum(r == f for r, f in zip(ref_answers, fsm_answers))
    accuracy = matches / count

    print(f"  • Совпадение решений: {matches}/{count} ({accuracy * 100:.2f}%)")
    print(f"  • Время чистой функции Python: {t_ref * 1000:.2f} мс ({t_ref / count * 1e6:.1f} мкс/задача)")
    print(f"  • Время FSM-интерпретатора:     {t_fsm * 1000:.2f} мс ({t_fsm / count * 1e6:.1f} мкс/задача)")
    speedup = t_fsm / t_ref if t_ref > 0 else 1.0
    print(f"  • Честный вывод: Чистая функция в {speedup:.1f}x быстрее FSM-интерпретатора.")
    print("    Ценность BUKVA-49 — не в скорости, а в аудируемом конечном автомате и неизменяемом следе.")

    return {
        "tasks_count": count,
        "agreement_rate": accuracy,
        "ref_time_ms": round(t_ref * 1000, 2),
        "fsm_time_ms": round(t_fsm * 1000, 2),
        "slowdown_ratio": round(speedup, 2),
    }


def analyze_operators(exhaustive: bool = False) -> dict:
    print("\n[2/4] Инспекция активности 49 операторов матрицы (динамический замер)...")
    cats = count_noop_ops()
    n_decision = len(cats["decision"])
    n_log = len(cats["log_only"])
    n_noop = len(cats["noop"])

    print(f"  • {LABELS['decision']}: {n_decision}/49")
    print(f"  • {LABELS['log_only']}: {n_log}/49")
    print(f"  • {LABELS['noop']}: {n_noop}/49")
    print(f"    Честный вывод: {n_decision} влияют на решение, {n_log} только пишут в журнал.")
    print(f"    Остальные {n_noop} не влияют на состояние при текущем распределении задач make_tasks.")

    return {
        "decision_drivers": n_decision,
        "audit_guardrails": n_log,
        "reserved_stubs": n_noop,
    }


def evaluate_agent_pipeline(cases_per_family: int = 25) -> dict:
    print(f"\n[3/4] Тестирование BukvaAgentPipeline на {cases_per_family * 4} разнородных задачах...")
    pipeline = BukvaAgentPipeline()
    bench_cases = cases(seed=297, per_family=cases_per_family)

    by_family = {}
    for c in bench_cases:
        by_family.setdefault(c.family, []).append(c)

    results = {}
    total_passed = 0
    total_cases = len(bench_cases)

    t0 = time.perf_counter()
    for fam, f_cases in by_family.items():
        fam_passed = 0
        for case in f_cases:
            res = pipeline.run(case.question)
            if res.selected_result == case.answer and res.is_valid:
                fam_passed += 1
                total_passed += 1
        results[fam] = {
            "passed": fam_passed,
            "total": len(f_cases),
            "accuracy": round(fam_passed / len(f_cases), 4),
        }
        print(f"  • Семейство '{fam}': {fam_passed}/{len(f_cases)} ({fam_passed / len(f_cases) * 100:.1f}%)")

    total_time = time.perf_counter() - t0
    print(f"  • Общий результат: {total_passed}/{total_cases} ({total_passed / total_cases * 100:.1f}%)")
    print(f"  • Общее время: {total_time:.3f} с ({total_time / total_cases * 1000:.2f} мс/задача)")

    return {
        "families": results,
        "total_passed": total_passed,
        "total_cases": total_cases,
        "accuracy": round(total_passed / total_cases, 4),
        "total_time_s": round(total_time, 3),
    }


def verify_sha256_integrity() -> bool:
    print("\n[4/4] Тестирование криптографической защиты SHA-256 от подделки...")
    pipeline = BukvaAgentPipeline()

    candidates_orig = [
        {"id": "v1", "name": "Поставщик А", "price": 10000, "delivery": 1000, "confirmed": True},
        {"id": "v2", "name": "Поставщик Б", "price": 12000, "delivery": 500, "confirmed": True},
    ]
    st1 = pipeline.run("Тендерная закупка", candidates=candidates_orig)
    seal_orig = st1.seal_hash

    # Модификация одного символа / 1 рубля в исходных данных
    candidates_tampered = [
        {"id": "v1", "name": "Поставщик А", "price": 9999, "delivery": 1000, "confirmed": True},
        {"id": "v2", "name": "Поставщик Б", "price": 12000, "delivery": 500, "confirmed": True},
    ]
    st2 = pipeline.run("Тендерная закупка", candidates=candidates_tampered)
    seal_tampered = st2.seal_hash

    is_tamper_proof = seal_orig != seal_tampered
    print(f"  • Исходная печать:   {seal_orig}")
    print(f"  • Печать при +1 руб: {seal_tampered}")
    print(f"  • Статус защиты:     {'УСПЕШНО (подделка гарантированно ломает хеш)' if is_tamper_proof else 'ОШИБКА'}")
    return is_tamper_proof


def main() -> None:
    setup_encoding()
    parser = argparse.ArgumentParser(description="BUKVA-49 Honest Scientific Benchmark")
    parser.add_argument("--tasks", type=int, default=4000, help="Number of tasks for reference comparison")
    parser.add_argument("--per-family", type=int, default=25, help="Cases per task family")
    parser.add_argument("--output", type=Path, help="Save benchmark results to JSON")
    args = parser.parse_args()

    print("=" * 75)
    print("      BUKVA-49: ЧЕСТНЫЙ ЭМПИРИЧЕСКИЙ БЕНЧМАРК (HONEST BENCHMARK)")
    print("=" * 75)

    res_ctrl = run_control_comparison(args.tasks)
    res_ops = analyze_operators()
    res_pipe = evaluate_agent_pipeline(args.per_family)
    seal_ok = verify_sha256_integrity()

    summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "control_comparison": res_ctrl,
        "operator_distribution": res_ops,
        "pipeline_benchmark": res_pipe,
        "cryptographic_seal_verified": seal_ok,
    }

    if args.output:
        args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\nРезультаты сохранены в: {args.output}")

    print("\n" + "=" * 75)
    print("БЕНЧМАРК ЗАВЕРШЁН.")
    print("=" * 75)


if __name__ == "__main__":
    main()
