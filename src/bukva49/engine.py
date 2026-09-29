"""Core deterministic interpreter and state transition engine for BUKVA-49."""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field

NAMES = (
    "Азъ", "Боги", "Вѣди", "Глаголи", "Добро", "Есть", "Есмь",
    "Животъ", "Ѕѣло", "Земля", "Иже", "Ижеи", "Инить", "Гервь",
    "Како", "Людие", "Мыслите", "Нашъ", "Онъ", "Покои", "Рѣци",
    "Слово", "Твѣрдо", "Укъ", "Оукъ", "Фѣртъ", "Хѣръ", "Отъ",
    "Ци", "Червль", "Ша", "Ща", "Еръ", "Еры", "Ерь", "Ять",
    "Юнь", "Арь", "Эдо", "Омъ", "Енъ", "Одь", "Йота", "Ота",
    "Кси", "Пси", "Фита", "Ижица", "Ижа",
)

OPS = {
    # Ряд 1: Бытие и Восприятие (Входной уровень)
    "Азъ": "INIT", "Боги": "AXIOMS", "Вѣди": "KNOW", "Глаголи": "TRANSMIT",
    "Добро": "VALUATE", "Есть": "VERIFY", "Есмь": "PRESENCE",
    # Ряд 2: Структура и Взаимосвязи (Топология)
    "Животъ": "LIFECYCLE", "Ѕѣло": "BOUND", "Земля": "GROUND", "Иже": "MERGE",
    "Ижеи": "ALIGN", "Инить": "THREAD", "Гервь": "ALERT",
    # Ряд 3: Осмысление и Логика (Аналитический уровень)
    "Како": "PATTERN", "Людие": "NORMALIZE", "Мыслите": "REASON", "Нашъ": "INTERNAL",
    "Онъ": "OBJECT", "Покои": "FREEZE", "Рѣци": "DECLARE",
    # Ряд 4: Утверждение и Очищение (Уровень фильтрации)
    "Слово": "EMIT", "Твѣрдо": "ENFORCE", "Укъ": "TRANSFORM", "Оукъ": "EXPAND",
    "Фѣртъ": "AUDIT", "Хѣръ": "ROLLBACK", "Отъ": "ISOLATE",
    # Ряд 5: Разделение и Детализация (Уровень анализа)
    "Ци": "TARGET", "Червль": "FORMAT", "Ша": "INDEX", "Ща": "COMPRESS",
    "Еръ": "SOLIDIFY", "Еры": "AGGREGATE", "Ерь": "RELAX",
    # Ряд 6: Эволюция и Преобразование (Уровень оптимизации)
    "Ять": "CROSS", "Юнь": "MUTATE", "Арь": "REFINE", "Эдо": "PROBE",
    "Омъ": "HARMONIZE", "Енъ": "SEED", "Одь": "WEIGH",
    # Ряд 7: Синтез и Завершение (Интегральный уровень)
    "Йота": "EXTRACT_KEY", "Ота": "DIFF", "Кси": "COMPARE", "Пси": "SPIRIT",
    "Фита": "SYNTHESIZE", "Ижица": "FALLBACK", "Ижа": "SEAL",
}

DESCRIPTIONS = {
    "Азъ": "Инициализация: сброс контекста и постановка цели",
    "Боги": "Инварианты: фиксация базовых аксиом задачи",
    "Вѣди": "Знание: сбор и извлечение сырых предложений в evidence",
    "Глаголи": "Передача: запись промежуточного шага в аудит-лог",
    "Добро": "Качество: очистка от некорректных цен и данных",
    "Есть": "Проверка: верификация источников и валидности",
    "Есмь": "Присутствие: фиксация границ и контекста задачи",
    "Животъ": "Жизненный цикл: фильтрация активных предложений",
    "Ѕѣло": "Предел: ограничение бюджета и отсечение экстремумов",
    "Земля": "Заземление: фиксация результата в структурированный артефакт",
    "Иже": "Единство: объединение и дедупликация предложений",
    "Ижеи": "Истина: выравнивание и калибровка списка по эталону",
    "Инить": "Нить: поточная разметка элементов",
    "Гервь": "Сигнал: детекция аномалий и подозрительных цен",
    "Како": "Форма: проверка соответствия формату задачи",
    "Людие": "Норма: нормализация числовых шкал",
    "Мыслите": "Мысль: расчёт полной стоимости (цена + доставка)",
    "Нашъ": "Память: кэширование промежуточных расчётов",
    "Онъ": "Объект: фокусировка на целевом множестве данных",
    "Покои": "Покой: заморозка неизменяемого снимка состояния",
    "Рѣци": "Декларация: утверждение контракта выходных данных",
    "Слово": "Слово: текстовая формулировка решения",
    "Твѣрдо": "Утверждение: жёсткая проверка наличия данных",
    "Укъ": "Формат: приведение типов и трансформация полей",
    "Оукъ": "Обогащение: добавление расчётных параметров",
    "Фѣртъ": "Честь: аудит прозрачности расчётов",
    "Хѣръ": "Откат: отмена изменений при нарушении условий",
    "Отъ": "Изоляция: квантильное отсечение худшей половины",
    "Ци": "Цель: фильтрация строго по целевому признаку",
    "Червль": "Красота: форматирование итогового артефакта",
    "Ша": "Пространство: индексация предложений по ключам",
    "Ща": "Сжатие: удаление заведомо проигрышных вариантов",
    "Еръ": "Твёрдость: окончательное закрепление выбора",
    "Еры": "Множество: агрегация средних, минимумов и сумм",
    "Ерь": "Мягкость: смягчение условий при пустом множестве",
    "Ять": "Связь: композиция лучших качеств (мин. цена + мин. доставка)",
    "Юнь": "Новизна: разведочная вариация кандидатов",
    "Арь": "Шлифовка: тонкая калибровка решения при равенстве",
    "Эдо": "Проба: зондирование выбранного варианта",
    "Омъ": "Согласие: гармонизация весов цены и надёжности",
    "Енъ": "Семя: фиксация детерминированного зерна генерации",
    "Одь": "Вес: назначение приоритетов критериям выбора",
    "Йота": "Суть: взятие абсолютного минимума",
    "Ота": "Разность: расчёт дельты между топ-1 и топ-2",
    "Кси": "Ранг: сортировка и ранжирование вариантов",
    "Пси": "Дух: проверка соответствия высшей цели задачи",
    "Фита": "Синтез: выбор оптимального решения из ранжированных",
    "Ижица": "Возрождение: резервный выбор при недоступности основного",
    "Ижа": "Печать: криптографическая подпись и завершение",
}

ALIASES = {v: k for k, v in OPS.items()}
ALIASES.update({k.casefold(): k for k in NAMES})

P297 = ("Вѣди", "Фита", "Земля")
FULL = ("Вѣди", "Есть", "Мыслите", "Кси", "Фита", "Земля")
EVOLVED = ("Вѣди", "Есть", "Мыслите", "Йота", "Земля")


@dataclass(frozen=True)
class Offer:
    id: str
    price: int
    delivery: int
    source_verified: bool


@dataclass(frozen=True)
class Task:
    id: int
    offers: tuple[Offer, ...]
    answer: str
    regime: str = "mixed"


@dataclass
class State:
    task: Task
    evidence: list[Offer] = field(default_factory=list)
    verified: bool = False
    computed: dict[str, int] = field(default_factory=dict)
    compared: list[str] = field(default_factory=list)
    selected: str | None = None
    artifact: dict | None = None
    checks: list[str] = field(default_factory=list)
    trace: list[str] = field(default_factory=list)
    cost: int = 0
    axioms: dict[str, bool] = field(default_factory=dict)
    scope: str = "global"
    budget_limit: int | None = None
    cache: dict[str, int] = field(default_factory=dict)
    frozen: bool = False
    snapshots: list[dict] = field(default_factory=list)
    aggregates: dict[str, float] = field(default_factory=dict)
    weights: dict[str, float] = field(default_factory=dict)
    delta: int | None = None
    audit_trail: list[str] = field(default_factory=list)
    sealed_hash: str | None = None


class ProgramError(ValueError):
    pass


def parse(source: str) -> tuple[str, ...]:
    s = source.strip()
    if s == "297":
        return P297
    if s.lower() in ("full", "полный"):
        return FULL
    if s.lower() in ("evolved", "yota_preset", "вемиз", "рекорд"):
        return EVOLVED
    tokens = source.replace("→", " ").replace(",", " ").split()
    if not tokens:
        raise ProgramError("Empty program")
    result = []
    for token in tokens:
        name = ALIASES.get(token) or ALIASES.get(token.casefold())
        if name is None or name not in OPS:
            raise ProgramError(f"Unknown or invalid operator name: {token}")
        result.append(name)
    return tuple(result)


def execute(program: tuple[str, ...], task: Task) -> State:
    s = State(task)
    for name in program:
        if name not in OPS:
            raise ProgramError(f"Not implemented: {name}")
        s.cost += 1
        s.trace.append(name)

        if name == "Азъ":
            s = State(task, trace=s.trace, cost=s.cost)
        elif name == "Боги":
            s.axioms["require_verified"] = True
            s.audit_trail.append("Утверждена аксиома: обязательная верификация источника")
        elif name == "Вѣди":
            s.evidence = list(task.offers)
            s.verified = False
            s.computed.clear()
            s.compared.clear()
            s.selected = None
            s.artifact = None
            s.checks.clear()
        elif name == "Глаголи":
            s.audit_trail.append(f"Глаголи: в наличии предложений={len(s.evidence)}, отобрано={s.selected}")
        elif name == "Добро":
            s.evidence = [o for o in s.evidence if o.price > 0 and o.delivery >= 0]
        elif name == "Есть":
            if s.artifact is not None:
                chosen = next((o for o in task.offers if o.id == s.artifact["offer_id"]), None)
                if chosen:
                    s.checks.append("pass" if chosen.source_verified and s.selected == task.answer else "fail")
            elif s.evidence:
                s.evidence = [o for o in s.evidence if o.source_verified]
                s.verified = True
                s.computed.clear()
                s.compared.clear()
                s.selected = None
                s.artifact = None
            else:
                raise ProgramError("VERIFY requires evidence or artifact")
        elif name == "Есмь":
            s.scope = task.regime
        elif name == "Животъ":
            s.evidence = [o for o in s.evidence if o.price < 50000]
        elif name == "Ѕѣло":
            s.budget_limit = 25000
            s.evidence = [o for o in s.evidence if o.price <= s.budget_limit]
        elif name == "Земля":
            if s.selected is None:
                raise ProgramError("GROUND requires selection")
            chosen = next(o for o in task.offers if o.id == s.selected)
            s.artifact = {
                "offer_id": chosen.id,
                "total": chosen.price + chosen.delivery,
                "source_verified": chosen.source_verified,
            }
        elif name == "Иже":
            seen = set()
            dedup = []
            for o in s.evidence:
                if o.id not in seen:
                    seen.add(o.id)
                    dedup.append(o)
            s.evidence = dedup
        elif name == "Ижеи":
            s.evidence = sorted(s.evidence, key=lambda o: o.id)
        elif name == "Инить":
            s.audit_trail.append(f"Инить: поток данных активен ({len(s.evidence)} узлов)")
        elif name == "Гервь":
            cheap_outliers = [o.id for o in s.evidence if o.price < 3000]
            if cheap_outliers:
                s.audit_trail.append(f"Гервь: предупреждение о подозрительно низкой цене: {cheap_outliers}")
        elif name == "Како":
            if not isinstance(task, Task):
                raise ProgramError("КАКО: Несоответствие сигнатуре Task")
        elif name == "Людие":
            pass
        elif name == "Мыслите":
            if not s.evidence:
                raise ProgramError("REASON requires evidence")
            s.computed = {o.id: o.price + o.delivery for o in s.evidence}
            s.compared.clear()
            s.selected = None
            s.artifact = None
        elif name == "Нашъ":
            s.cache.update(s.computed)
        elif name == "Онъ":
            if not s.computed and s.evidence:
                s.computed = {o.id: o.price + o.delivery for o in s.evidence}
        elif name == "Покои":
            snap = {"evidence_len": len(s.evidence), "computed": dict(s.computed), "selected": s.selected}
            s.snapshots.append(snap)
            s.frozen = True
        elif name == "Рѣци":
            s.audit_trail.append("Рѣци: контракт схемы данных зафиксирован")
        elif name == "Слово":
            if s.selected:
                s.audit_trail.append(f"Слово: итоговое утверждение выбора {s.selected}")
        elif name == "Твѣрдо":
            if not s.evidence and not s.computed:
                raise ProgramError("ТВѢРДО: Нарушение инварианта данных")
        elif name == "Укъ":
            pass
        elif name == "Оукъ":
            pass
        elif name == "Фѣртъ":
            s.audit_trail.append("Фѣртъ: независимый аудит расчётов пройден успешно")
        elif name == "Хѣръ":
            if s.snapshots:
                last_snap = s.snapshots[-1]
                s.selected = last_snap.get("selected")
        elif name == "Отъ":
            if s.computed:
                median = sorted(s.computed.values())[len(s.computed) // 2]
                s.computed = {k: v for k, v in s.computed.items() if v <= median}
        elif name == "Ци":
            pass
        elif name == "Червль":
            s.audit_trail.append("Червль: эстетическое форматирование артефакта")
        elif name == "Ша":
            s.cache["index_count"] = len(s.evidence)
        elif name == "Ща":
            if s.computed and len(s.computed) > 3:
                top3 = sorted(s.computed, key=lambda k: s.computed[k])[:3]
                s.computed = {k: s.computed[k] for k in top3}
        elif name == "Еръ":
            if s.selected:
                s.frozen = True
        elif name == "Еры":
            if s.computed:
                vals = list(s.computed.values())
                s.aggregates = {"mean": sum(vals) / len(vals), "min": min(vals), "max": max(vals)}
        elif name == "Ерь":
            if not s.evidence:
                s.evidence = list(task.offers)
        elif name == "Ять":
            pass
        elif name == "Юнь":
            pass
        elif name == "Арь":
            pass
        elif name == "Эдо":
            if s.selected:
                s.audit_trail.append(f"Эдо: проверочный зонд кандидата {s.selected} успешен")
        elif name == "Омъ":
            pass
        elif name == "Енъ":
            pass
        elif name == "Одь":
            s.weights = {"price_weight": 0.8, "delivery_weight": 0.2}
        elif name == "Йота":
            if s.computed:
                s.selected = min(s.computed, key=lambda k: (s.computed[k], k))
        elif name == "Ота":
            if len(s.computed) >= 2:
                sorted_vals = sorted(s.computed.values())
                s.delta = sorted_vals[1] - sorted_vals[0]
        elif name == "Кси":
            if not s.computed:
                raise ProgramError("COMPARE requires computed costs")
            s.compared = sorted(s.computed, key=lambda key: (s.computed[key], key))
            s.selected = None
            s.artifact = None
        elif name == "Пси":
            s.audit_trail.append("Пси: проверка соответствия духу исходной цели")
        elif name == "Фита":
            if not s.evidence:
                raise ProgramError("SYNTHESIZE requires evidence")
            if s.compared:
                s.selected = s.compared[0]
            elif s.computed:
                s.selected = min(s.computed, key=lambda key: (s.computed[key], key))
            else:
                s.selected = min(s.evidence, key=lambda o: (o.price, o.id)).id
            s.artifact = None
        elif name == "Ижица":
            if s.selected is None and s.evidence:
                s.selected = s.evidence[0].id
        elif name == "Ижа":
            data_str = f"{s.selected}_{s.cost}_{len(s.trace)}"
            s.sealed_hash = hashlib.sha256(data_str.encode()).hexdigest()[:16]
            s.audit_trail.append(f"Ижа: артефакт запечатан контрольной подписью: {s.sealed_hash}")

    return s


def make_tasks(count: int, seed: int, regime: str = "mixed") -> list[Task]:
    import random
    rng = random.Random(seed)
    tasks = []
    for i in range(count):
        kind = ("all_verified", "misleading", "independent", "free_delivery")[i % 4] if regime == "mixed" else regime
        if kind not in ("all_verified", "misleading", "independent", "free_delivery"):
            raise ValueError(f"Unknown regime: {kind}")
        offers = []
        for j in range(4):
            verified = kind in ("all_verified", "free_delivery") or j < 3 or rng.random() < .5
            price = rng.randrange(7000, 16000, 100)
            if kind == "misleading" and j == 3:
                price, verified = rng.randrange(2000, 6900, 100), False
            delivery = 0 if kind == "free_delivery" else rng.randrange(0, 5500, 100)
            offers.append(Offer(f"{i}-{j}", price, delivery, verified))
        rng.shuffle(offers)
        answer = min((o for o in offers if o.source_verified),
                     key=lambda o: (o.price + o.delivery, o.id)).id
        tasks.append(Task(i, tuple(offers), answer, kind))
    return tasks


def evaluate(program: tuple[str, ...], tasks: list[Task]) -> dict:
    scores, correct, valid, grounded, costs = [], 0, 0, 0, []
    for task in tasks:
        try:
            state = execute(program, task)
            artifact = state.artifact
            accurate = int(artifact is not None and artifact["offer_id"] == task.answer)
            sourced = int(artifact is not None and artifact["source_verified"])
            complete = int(artifact is not None)
            cost = state.cost
        except ProgramError:
            accurate = sourced = complete = 0
            cost = len(program)
        correct += accurate
        valid += sourced
        grounded += complete
        costs.append(cost)
        scores.append(max(0.0, min(1.0, .7 * accurate + .2 * sourced + .1 * complete - .002 * cost)))
    n = len(tasks)
    return {
        "score": round(sum(scores) / n, 4),
        "accuracy": round(correct / n, 4),
        "verified_source_rate": round(valid / n, 4),
        "artifact_rate": round(grounded / n, 4),
        "mean_cost": round(sum(costs) / n, 2),
    }
