"""Genetic evolutionary search and benchmarking for BUKVA-49 programs."""
from __future__ import annotations

import random
from typing import Sequence

from .engine import FULL, NAMES, P297, Task, evaluate


SEARCH_OPS: tuple[str, ...] = tuple(NAMES)


def mutate(parent: tuple[str, ...], rng: random.Random) -> tuple[str, ...]:
    """Mutate a cognitive pipeline formula using genetic operators."""
    candidate = list(parent)
    action = rng.choice(("insert", "replace", "delete", "swap"))
    if action == "insert" and len(candidate) < 9:
        candidate.insert(rng.randrange(len(candidate) + 1), rng.choice(SEARCH_OPS))
    elif action == "replace":
        candidate[rng.randrange(len(candidate))] = rng.choice(SEARCH_OPS)
    elif action == "delete" and len(candidate) > 2:
        del candidate[rng.randrange(len(candidate))]
    elif action == "swap" and len(candidate) > 1:
        j = rng.randrange(len(candidate) - 1)
        candidate[j], candidate[j + 1] = candidate[j + 1], candidate[j]
    return tuple(candidate)


def search(train: list[Task], seed: int, generations: int) -> tuple[tuple[str, ...], int]:
    """Search for the most resilient and minimal cognitive program using genetic algorithm."""
    rng = random.Random(seed)
    population = [P297, FULL] + [mutate(FULL if j % 2 else P297, rng) for j in range(48)]
    cache: dict[tuple[str, ...], float] = {}

    def fitness(program: tuple[str, ...]) -> float:
        if program not in cache:
            cache[program] = evaluate(program, train)["score"]
        return cache[program]

    for _ in range(generations):
        ranked = sorted(set(population), key=lambda p: (-fitness(p), len(p), p))
        elite = ranked[:10]
        population = elite + [mutate(rng.choice(elite), rng) for _ in range(40)]
    best = min(set(population) | {P297, FULL}, key=lambda p: (-fitness(p), len(p), p))
    return best, len(cache)


def experiment(seed: int, train_count: int, test_count: int, generations: int) -> dict:
    """Run an empirical evolutionary benchmark comparing baseline, full, and evolved pipelines."""
    from .engine import make_tasks

    if min(train_count, test_count) < 1 or generations < 0:
        raise ValueError("train, test must be positive; generations cannot be negative")

    train = make_tasks(train_count, seed)
    test = make_tasks(test_count, seed + 1_000_003)
    best, evaluated = search(train, seed + 71, generations)

    def direct(tasks: list[Task]) -> dict:
        return {
            "accuracy": round(
                sum(
                    min((o for o in t.offers if o.source_verified),
                        key=lambda o: (o.price + o.delivery, o.id)).id == t.answer
                    for t in tasks
                ) / len(tasks),
                4,
            )
        }

    stress = {
        kind: make_tasks(test_count, seed + 2_000_003 + j, kind)
        for j, kind in enumerate(("all_verified", "misleading", "independent", "free_delivery"))
    }

    return {
        "seed": seed,
        "train_tasks": train_count,
        "test_tasks": test_count,
        "generations": generations,
        "unique_programs_evaluated": evaluated,
        "scoring": "0.70 accuracy + 0.20 verified source + 0.10 artifact - 0.002 cost",
        "plain_python_control": {
            "train": direct(train),
            "test": direct(test),
            "stress": {kind: direct(cases) for kind, cases in stress.items()},
        },
        "programs": {
            label: {
                "steps": list(program),
                "train": evaluate(program, train),
                "test": evaluate(program, test),
                "stress": {kind: evaluate(program, cases) for kind, cases in stress.items()},
            }
            for label, program in (("297", P297), ("full_baseline", FULL), ("evolved", best))
        },
    }
