"""Печатает таблицу статуса 49 операторов, вычисленную замером, а не написанную вручную.

Метод: каждый оператор вставляется в каждую позицию программы EVOLVED (или удаляется, если он там есть),
результат сравнивается на 60 задачах из make_tasks.
  decision  - меняется выбор, артефакт, набор кандидатов или расчёты, либо возникает ProgramError
  log_only  - меняются только журнал аудита, кэш и служебные поля
  noop      - состояние не меняется вообще
Оговорка: классификация относится к распределению задач make_tasks (цены 2000-16000, без дублей).

Запуск из корня репозитория:  python operator_table.py > operator_table.md
"""
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from bukva49.engine import EVOLVED, NAMES, OPS, ProgramError, execute, make_tasks  # noqa: E402


def count_noop_ops() -> dict:
    """Классификация 49 операторов по фактическому влиянию на решение.

    Для каждого оператора пробуем вставить его в каждую позицию EVOLVED и (если он там есть)
    удалить его. Затем сравниваем результат на 60 задачах:
      * decision  - меняется выбор/артефакт/набор кандидатов/расчёты либо возникает ProgramError;
      * log_only  - меняются только audit_trail / cache / служебные флаги (т.е. текст в логе);
      * noop      - состояние не меняется вообще.
    """
    tasks = make_tasks(60, seed=5, regime="mixed")

    def decision_sig(s):
        return (s.selected, tuple(s.evidence), tuple(sorted(s.computed.items())),
                tuple(s.compared), s.artifact)

    def full_sig(s):
        return decision_sig(s) + (
            s.budget_limit, tuple(sorted(s.cache.items())), s.frozen, len(s.snapshots),
            tuple(sorted(s.aggregates.items())), tuple(sorted(s.weights.items())), s.delta,
            tuple(s.audit_trail), tuple(sorted(s.axioms.items())), s.scope, s.sealed_hash)

    def variants(name):
        for pos in range(len(EVOLVED) + 1):
            yield EVOLVED[:pos] + (name,) + EVOLVED[pos:]
        for i, op in enumerate(EVOLVED):
            if op == name:
                yield EVOLVED[:i] + EVOLVED[i + 1:]

    cats = {"decision": [], "log_only": [], "noop": []}
    for name in NAMES:
        decision = logonly = False
        for prog in variants(name):
            for t in tasks:
                base = execute(EVOLVED, t)
                try:
                    s = execute(prog, t)
                except ProgramError:
                    decision = True
                    break
                if decision_sig(s) != decision_sig(base):
                    decision = True
                    break
                if full_sig(s) != full_sig(base):
                    logonly = True
            if decision:
                break
        cats["decision" if decision else "log_only" if logonly else "noop"].append(name)
    return cats



LABELS = {"decision": "Влияют на решение", "log_only": "Пишут только в журнал и служебные поля", "noop": "Без эффекта"}

if __name__ == "__main__":
    cats = count_noop_ops()
    print("| Категория | Кол-во | Операторы |")
    print("|---|---|---|")
    for key in ("decision", "log_only", "noop"):
        ops = ", ".join(f"`{n}`" for n in cats[key])
        print(f"| {LABELS[key]} | {len(cats[key])} | {ops} |")
    assert sum(len(v) for v in cats.values()) == len(NAMES)
