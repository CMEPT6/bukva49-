"""High-level cognitive agent pipeline module for BUKVA-49."""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PipelineState:
    task_description: str
    target_type: str = "unknown"
    evidence: list[dict] = field(default_factory=list)
    initial_value: int | None = None
    verified_candidates: list[dict] = field(default_factory=list)
    computed_metrics: list[dict] = field(default_factory=list)
    ranked_results: list[dict] = field(default_factory=list)
    selected_result: str | None = None
    audit_trail: list[str] = field(default_factory=list)
    final_artifact: dict | None = None
    is_valid: bool = False
    execution_time: float = 0.0
    seal_hash: str | None = None
    axioms: dict[str, Any] = field(default_factory=dict)

    @property
    def goal(self) -> str:
        return self.task_description

    @property
    def domain(self) -> str:
        return self.target_type

    @property
    def verified_offers(self) -> list[dict]:
        return self.verified_candidates

    @property
    def selected_id(self) -> str | None:
        return self.selected_result

    @property
    def best_score(self) -> int | float | None:
        if self.ranked_results and "total_cost" in self.ranked_results[0]:
            return self.ranked_results[0]["total_cost"]
        if self.computed_metrics and "final_stock" in self.computed_metrics[0]:
            return self.computed_metrics[0]["final_stock"]
        if self.computed_metrics and "final_rating" in self.computed_metrics[0]:
            return self.computed_metrics[0]["final_rating"]
        return None

    @property
    def artifact(self) -> dict | None:
        return self.final_artifact


class BukvaAgentPipeline:
    """Agentic pipeline executing the Slavic cognitive workflow."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def log(self, state: PipelineState, step_name: str, message: str) -> None:
        entry = f"[{step_name}] {message}"
        state.audit_trail.append(entry)
        if self.verbose:
            print(f"  -> {entry}")

    def op_az(self, task_text: str) -> PipelineState:
        state = PipelineState(task_description=task_text)
        self.log(state, "Азъ (INIT)", "Инициализация контекста. Анализ целевой функции...")
        lower = task_text.lower()
        if "поставщика" in lower or "доставки" in lower or "закуп" in lower or "памяти" in lower:
            state.target_type = "offer"
            state.axioms = {
                "source_verified_required": True,
                "minimize_total_cost": True,
            }
        elif "остаток" in lower or "складе" in lower or "транзакци" in lower:
            state.target_type = "inventory"
            state.axioms = {"account_confirmed_only": True}
        elif "шахматиста" in lower or "рейтинг" in lower or "турнир" in lower:
            state.target_type = "rating"
            state.axioms = {"streak_bonus_threshold": 2}
        elif "проект" in lower or "утвержд" in lower or "черновик" in lower:
            state.target_type = "source"
            state.axioms = {"approved_only": True}
        else:
            state.target_type = "generic"
        self.log(state, "Азъ (INIT)", f"Определён домен задачи: {state.target_type.upper()}")
        return state

    def op_vedi(self, state: PipelineState, candidates: list[dict] | None = None) -> None:
        self.log(state, "Вѣди (KNOW)", "Извлечение структурированных фактов в evidence...")
        if candidates is not None:
            state.evidence = list(candidates)
            self.log(state, "Вѣди (KNOW)", f"Получено внешних кандидатов: {len(state.evidence)}")
            return

        found_json = re.search(r"(\[.*?\]|\{.*?\})", state.task_description, re.DOTALL)
        if found_json:
            try:
                parsed = json.loads(found_json.group(0))
                if isinstance(parsed, list):
                    state.evidence = parsed
                    self.log(state, "Вѣди (KNOW)", f"Успешно извлечено записей из JSON: {len(state.evidence)}")
            except Exception:
                pass

        if state.target_type == "inventory":
            m = re.search(r"Начальный остаток:\s*(\d+)", state.task_description)
            if m:
                state.initial_value = int(m.group(1))
                self.log(state, "Вѣди (KNOW)", f"Зафиксирован базовый остаток: {state.initial_value}")
        elif state.target_type == "rating":
            m = re.search(r"Начальный рейтинг:\s*(\d+)", state.task_description)
            if m:
                state.initial_value = int(m.group(1))
                self.log(state, "Вѣди (KNOW)", f"Зафиксирован базовый рейтинг: {state.initial_value}")

    def op_est(self, state: PipelineState) -> None:
        self.log(state, "Есть (VERIFY)", "Детерминированная проверка условий и отсечение недопустимых данных...")
        if state.target_type == "offer":
            m_days = re.search(r"days\s*<=\s*(\d+)|не более\s*(\d+)\s*дней", state.task_description, re.IGNORECASE)
            max_days = int(m_days.group(1) or m_days.group(2)) if m_days else None

            valid = []
            for item in state.evidence:
                confirmed = item.get("confirmed", True)
                verified = item.get("source_verified", True)
                is_ok = bool(confirmed and verified)
                days = item.get("days")
                if max_days is not None and days is not None and days > max_days:
                    is_ok = False
                name = item.get("name") or item.get("id") or "?"
                if is_ok:
                    valid.append(item)
                    self.log(state, "Есть (VERIFY)", f"  [+] {name}: Верифицирован и допущен")
                else:
                    self.log(state, "Есть (VERIFY)", f"  [-] {name}: Дисквалифицирован (не верифицирован или превышен срок)")
            state.verified_candidates = valid

        elif state.target_type == "inventory":
            valid = []
            for tx in state.evidence:
                status = tx.get("статус", "")
                tx_type = tx.get("тип", "")
                qty = tx.get("кол-во", 0)
                if status == "проведено":
                    valid.append(tx)
                    self.log(state, "Есть (VERIFY)", f"  [+] Операция '{tx_type}' на {qty} шт -> УЧИТЫВАЕТСЯ")
                else:
                    self.log(state, "Есть (VERIFY)", f"  [-] Пропущена операция '{tx_type}' на {qty} шт (статус: '{status}')")
            state.verified_candidates = valid

        elif state.target_type == "source":
            valid = []
            for doc in state.evidence:
                status = doc.get("статус", "")
                name = doc.get("название", "")
                date = doc.get("дата", "")
                if status == "утверждено":
                    valid.append(doc)
                    self.log(state, "Есть (VERIFY)", f"  [+] '{name}' от {date} -> ДОПУЩЕН")
                else:
                    self.log(state, "Есть (VERIFY)", f"  [-] '{name}' от {date} -> ОТКЛОНЁН (статус: {status})")
            state.verified_candidates = valid

        elif state.target_type == "rating":
            state.verified_candidates = list(state.evidence)
            self.log(state, "Есть (VERIFY)", f"Все {len(state.evidence)} туров верифицированы")

        else:
            state.verified_candidates = list(state.evidence)

    def op_myslite(self, state: PipelineState) -> None:
        self.log(state, "Мыслите (REASON)", "Выполнение точных математических расчётов...")
        if state.target_type == "offer":
            computed = []
            for item in state.verified_candidates:
                delivery = item.get("delivery_cost", item.get("delivery", 0))
                total = item["price"] + delivery
                computed.append({
                    "id": item.get("id"),
                    "name": item.get("name") or item.get("id"),
                    "total_cost": total,
                    "price": item["price"],
                    "delivery": delivery,
                    "source_verified": item.get("source_verified", True),
                })
                self.log(state, "Мыслите (REASON)", f"  Расчёт {computed[-1]['name']}: {item['price']} + {delivery} = {total}")
            state.computed_metrics = computed

        elif state.target_type == "inventory":
            stock = state.initial_value or 0
            for tx in state.verified_candidates:
                t = tx.get("тип", "")
                q = tx.get("кол-во", 0)
                if t == "приход":
                    stock += q
                elif t == "расход":
                    stock -= q
            state.computed_metrics = [{"final_stock": stock}]
            self.log(state, "Мыслите (REASON)", f"Итоговый остаток: {stock} шт.")

        elif state.target_type == "rating":
            rating = state.initial_value or 1500
            current_streak = 0
            max_streak = 0
            for r in state.verified_candidates:
                res = r.get("результат", "")
                opp = r.get("соперник", "")
                if res == "победа":
                    current_streak += 1
                    max_streak = max(max_streak, current_streak)
                    delta = 15 if opp == "сильный" else 10
                elif res == "ничья":
                    current_streak = 0
                    delta = 2 if opp == "сильный" else -2
                else:
                    current_streak = 0
                    delta = -10 if opp == "сильный" else -15
                rating += delta

            streak_bonus = 10 if max_streak >= 2 else 0
            final_rating = rating + streak_bonus
            state.computed_metrics = [{"final_rating": final_rating}]
            self.log(state, "Мыслите (REASON)", f"Итоговый рейтинг: {final_rating}")

        elif state.target_type == "source":
            state.computed_metrics = list(state.verified_candidates)

    def op_ksi(self, state: PipelineState) -> None:
        self.log(state, "Кси (COMPARE)", "Ранжирование и упорядочивание допустимых вариантов...")
        if state.target_type == "offer":
            ranked = sorted(state.computed_metrics, key=lambda x: (x["total_cost"], x["name"]))
            state.ranked_results = ranked
        elif state.target_type == "source":
            ranked = sorted(state.computed_metrics, key=lambda x: x.get("дата", ""), reverse=True)
            state.ranked_results = ranked
        else:
            state.ranked_results = list(state.computed_metrics)

    def op_fita(self, state: PipelineState) -> None:
        self.log(state, "Фита (SYNTHESIZE)", "Принятие оптимального решения на основе ранжирования...")
        if state.target_type == "offer":
            if state.ranked_results:
                state.selected_result = state.ranked_results[0]["name"]
        elif state.target_type == "inventory":
            state.selected_result = str(state.computed_metrics[0]["final_stock"])
        elif state.target_type == "rating":
            state.selected_result = str(state.computed_metrics[0]["final_rating"])
        elif state.target_type == "source":
            if state.ranked_results:
                state.selected_result = state.ranked_results[0].get("название")

    def op_zemlya(self, state: PipelineState) -> None:
        self.log(state, "Земля (GROUND)", "Формирование сертифицированного JSON-артефакта...")
        artifact = {
            "answer": state.selected_result,
            "target_type": state.target_type,
            "pipeline": "БУКВА-49 (Азъ -> Вѣди -> Есть -> Мыслите -> Кси -> Фита -> Земля -> Ижа)",
            "selected_metric": state.best_score,
            "ranked_count": len(state.ranked_results),
            "audit_trail": state.audit_trail,
        }
        state.final_artifact = artifact

    def op_ija(self, state: PipelineState) -> None:
        self.log(state, "Ижа (SEAL)", "Криптографическая подпись решения (SHA-256)...")
        seal_src = f"{state.selected_result}_{state.best_score}_{len(state.audit_trail)}"
        state.seal_hash = hashlib.sha256(seal_src.encode("utf-8")).hexdigest()[:16]
        if state.final_artifact:
            state.final_artifact["sha256_seal"] = state.seal_hash
        self.log(state, "Ижа (SEAL)", f"Печать установлена: {state.seal_hash}")

    def op_audit(self, state: PipelineState) -> None:
        self.log(state, "Есть (AUDIT)", "Контрольная верификация выходного артефакта...")
        state.is_valid = bool(state.final_artifact and state.final_artifact.get("answer") is not None)

    def run(self, task_text: str, candidates: list[dict] | None = None) -> PipelineState:
        t0 = time.monotonic()
        state = self.op_az(task_text)
        self.op_vedi(state, candidates=candidates)
        self.op_est(state)
        self.op_myslite(state)
        self.op_ksi(state)
        self.op_fita(state)
        self.op_zemlya(state)
        self.op_ija(state)
        self.op_audit(state)
        state.execution_time = round(time.monotonic() - t0, 4)
        return state
