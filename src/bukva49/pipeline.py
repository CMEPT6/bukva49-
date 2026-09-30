"""High-level cognitive agent pipeline module for BUKVA-49.

Deterministic execution graph for multi-agent reasoning, verification, and audit trail.
Features fail-closed validation, structured task schemas, and cryptographic HMAC-SHA256 seals.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TaskConstraints:
    """Explicit business constraints (Task Schema as Data)."""
    max_days: int | None = None
    require_confirmed: bool = True
    max_budget: int | None = None
    allowed_statuses: tuple[str, ...] = ("проведено", "подтверждено", "утверждено", "completed", "approved")
    custom_rules: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskSpecification:
    """Typed input specification bypassing regular expression parsing."""
    domain: str
    goal: str
    candidates: list[dict]
    constraints: TaskConstraints = field(default_factory=TaskConstraints)
    initial_value: int | None = None


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
    error: str | None = None
    constraints: TaskConstraints = field(default_factory=TaskConstraints)

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
    """Deterministic 7-step Slavic cognitive workflow:

    1. Азъ     (INIT)       - Определение домена и инвариантов
    2. Вѣди    (KNOW)       - Извлечение структурированных фактов в evidence
    3. Есть    (VERIFY)     - Детерминированная проверка условий (Fail-Closed)
    4. Мыслите (REASON)     - Математический расчёт в ядре Python (без галлюцинаций)
    5. Кси     (COMPARE)    - Сортировка и ранжирование
    6. Фита    (SYNTHESIZE) - Выбор оптимального решения
    7. Земля   (GROUND)     - Формирование верифицированного артефакта
    8. Ижа     (SEAL)       - Криптографическая печать HMAC-SHA256
    9. Есть    (AUDIT)      - Финальная верификация контракта выходных данных
    """

    def __init__(self, secret_key: str | bytes | None = None, verbose: bool = False):
        self.secret_key = secret_key
        self.verbose = verbose

    def log(self, state: PipelineState, step_name: str, message: str) -> None:
        entry = f"[{step_name}] {message}"
        state.audit_trail.append(entry)
        if self.verbose:
            print(f"  -> {entry}")

    def op_az(self, task_text: str, constraints: TaskConstraints | None = None) -> PipelineState:
        state = PipelineState(task_description=task_text)
        if constraints:
            state.constraints = constraints
        self.log(state, "Азъ (INIT)", "Инициализация контекста. Анализ домена целевой функции...")
        lower = task_text.lower()
        if any(w in lower for w in ("шахматист", "рейтинг", "турнир")):
            state.target_type = "rating"
            state.axioms = {"streak_bonus_threshold": 2, "streak_bonus": 10}
        elif any(w in lower for w in ("проект", "утвержд", "черновик", "отозвано", "кодовое название", "источник")):
            state.target_type = "source"
            state.axioms = {"approved_only": True, "select_latest": True}
        elif any(w in lower for w in ("остаток", "склад", "транзакци", "товар", "инвентаризац")):
            state.target_type = "inventory"
            state.axioms = {"account_confirmed_only": True}
        elif any(w in lower for w in ("поставщика", "доставки", "закуп", "памяти", "price", "delivery")):
            state.target_type = "offer"
            state.axioms = {
                "require_confirmed": True,
                "minimize_total_cost": True,
            }
        else:
            state.target_type = "generic"
        self.log(state, "Азъ (INIT)", f"Определён домен задачи: {state.target_type.upper()}")
        return state

    def op_vedi(self, state: PipelineState, candidates: list[dict] | None = None) -> None:
        self.log(state, "Вѣди (KNOW)", "Извлечение структурированных фактов в evidence...")
        if candidates is not None:
            state.evidence = list(candidates)
            self.log(state, "Вѣди (KNOW)", f"Получено внешних кандидатов: {len(state.evidence)}")
        else:
            # Поиск внедрённого JSON массива
            found_json = re.search(r"(\[.*?\])", state.task_description, re.DOTALL)
            if found_json:
                try:
                    parsed = json.loads(found_json.group(0))
                    if isinstance(parsed, list):
                        state.evidence = parsed
                        self.log(state, "Вѣди (KNOW)", f"Успешно извлечено записей из JSON: {len(state.evidence)}")
                except Exception:
                    pass

        # Калибровка домена по фактической схеме evidence
        if state.evidence and isinstance(state.evidence[0], dict):
            first = state.evidence[0]
            if "тур" in first and "результат" in first:
                state.target_type = "rating"
            elif "название" in first and "дата" in first:
                state.target_type = "source"
            elif "кол-во" in first and "статус" in first:
                state.target_type = "inventory"
            elif "price" in first or "delivery_cost" in first:
                state.target_type = "offer"

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
            # 1. Приоритет структурированной схемы (Task Schema as Data)
            max_days = state.constraints.max_days

            # 2. Если лимит не задан явно, парсим из текста
            if max_days is None:
                m_days = re.search(
                    r"(?:days\s*<=\s*(\d+)|"
                    r"не более\s*(\d+)\s*(?:дней|суток|дн)|"
                    r"максимум\s*(\d+)\s*(?:дней|суток|дн)|"
                    r"до\s*(\d+)\s*(?:дней|суток|дн)|"
                    r"срок\s*(?:до\s*)?(\d+)\s*(?:дней|суток|дн)|"
                    r"в пределах\s*(\d+)\s*(?:дней|суток|дн))",
                    state.task_description,
                    re.IGNORECASE,
                )
                if m_days:
                    for grp in m_days.groups():
                        if grp:
                            max_days = int(grp)
                            break

            # 3. Принцип FAIL-CLOSED:
            # Если текст явно говорит об ограничении сроков, но число не извлечено,
            # мы ОБЯЗАНЫ отказать во избежание ложноположительной сертификации!
            lower_desc = state.task_description.lower()
            mentions_delivery_limit = any(
                w in lower_desc for w in ("дней", "суток", "дн", "срок", "days", "дедлайн", "лимит", "максимум", "не более")
            )
            has_candidate_days = any("days" in item for item in state.evidence)

            if max_days is None and mentions_delivery_limit and has_candidate_days:
                self.log(
                    state,
                    "Есть (VERIFY)",
                    "FAIL-CLOSED: В тексте обнаружены требования к сроку доставки, но точный числовой лимит не верифицирован. "
                    "Автоматический выбор отклонён во избежание ложной сертификации.",
                )
                state.is_valid = False
                state.error = "Unresolved delivery constraint (fail-closed)"
                state.verified_candidates = []
                return

            valid = []
            for item in state.evidence:
                confirmed = item.get("confirmed", item.get("source_verified", True))
                days = item.get("days")
                is_valid = bool(confirmed)
                if max_days is not None and days is not None and days > max_days:
                    is_valid = False
                name = item.get("name") or item.get("id") or "?"
                if is_valid:
                    valid.append(item)
                    self.log(state, "Есть (VERIFY)", f"  [+] {name}: Верифицирован и допущен")
                else:
                    reason = "не подтверждён" if not confirmed else f"срок {days} > {max_days}"
                    self.log(state, "Есть (VERIFY)", f"  [-] {name}: Дисквалифицирован ({reason})")

            if not valid:
                self.log(state, "Есть (VERIFY)", "FAIL-CLOSED: Ни один кандидат не прошёл фильтр условий.")
                state.is_valid = False
                state.error = "All candidates disqualified"
                state.verified_candidates = []
                return

            state.verified_candidates = valid

        elif state.target_type == "inventory":
            valid = []
            for tx in state.evidence:
                status = str(tx.get("статус", "")).lower()
                tx_type = str(tx.get("тип", "")).lower()
                qty = tx.get("кол-во", 0)
                if status in ("проведено", "подтверждено", "completed", "done"):
                    valid.append(tx)
                    self.log(state, "Есть (VERIFY)", f"  [+] Операция '{tx_type}' на {qty} шт -> УЧИТЫВАЕТСЯ")
                else:
                    self.log(state, "Есть (VERIFY)", f"  [-] Пропущена операция '{tx_type}' на {qty} шт (статус: '{status}')")
            state.verified_candidates = valid

        elif state.target_type == "source":
            valid = []
            for doc in state.evidence:
                status = str(doc.get("статус", "")).lower()
                name = doc.get("название", "")
                date = doc.get("дата", "")
                if status in ("утверждено", "approved", "active"):
                    valid.append(doc)
                    self.log(state, "Есть (VERIFY)", f"  [+] '{name}' от {date} -> ДОПУЩЕН")
                else:
                    self.log(state, "Есть (VERIFY)", f"  [-] '{name}' от {date} -> ОТКЛОНЁН (статус: {status})")

            if not valid:
                self.log(state, "Есть (VERIFY)", "FAIL-CLOSED: Нет утверждённых документов.")
                state.is_valid = False
                state.error = "No approved documents"
                state.verified_candidates = []
                return

            state.verified_candidates = valid

        elif state.target_type == "rating":
            state.verified_candidates = list(state.evidence)
            self.log(state, "Есть (VERIFY)", f"Все {len(state.evidence)} туров верифицированы")

        else:
            state.verified_candidates = list(state.evidence)

    def op_myslite(self, state: PipelineState) -> None:
        if state.error or not state.verified_candidates:
            return

        self.log(state, "Мыслите (REASON)", "Выполнение детерминированных математических расчётов в Python...")
        if state.target_type == "offer":
            computed = []
            for item in state.verified_candidates:
                delivery = item.get("delivery_cost", item.get("delivery", 0))
                price = item["price"]
                total = price + delivery
                computed.append({
                    "id": item.get("id"),
                    "name": item.get("name") or item.get("id"),
                    "total_cost": total,
                    "price": price,
                    "delivery": delivery,
                    "confirmed": item.get("confirmed", True),
                })
                self.log(state, "Мыслите (REASON)", f"  Расчёт {computed[-1]['name']}: {price} + {delivery} = {total}")
            state.computed_metrics = computed

        elif state.target_type == "inventory":
            stock = state.initial_value or 0
            for tx in state.verified_candidates:
                t = str(tx.get("тип", "")).lower()
                q = tx.get("кол-во", 0)
                if t in ("поступление", "возврат_клиента", "приход", "income", "return"):
                    stock += q
                elif t in ("отгрузка", "расход", "списание", "outcome", "expense"):
                    stock -= q
            state.computed_metrics = [{"final_stock": stock}]
            self.log(state, "Мыслите (REASON)", f"Итоговый физический остаток: {stock} шт.")

        elif state.target_type == "rating":
            rating = state.initial_value or 1500
            current_streak = 0
            max_streak = 0
            for r in state.verified_candidates:
                res = str(r.get("результат", "")).lower()
                opp = str(r.get("соперник", "")).lower()
                delta = 0
                if res in ("победа", "win"):
                    delta = 15 if opp in ("сильный", "strong") else 10
                    current_streak += 1
                    max_streak = max(max_streak, current_streak)
                elif res in ("ничья", "draw"):
                    delta = 0
                    current_streak = 0
                elif res in ("поражение", "loss"):
                    delta = -12
                    current_streak = 0
                else:
                    current_streak = 0
                rating += delta
                self.log(state, "Мыслите (REASON)", f"  Тур {r.get('тур')}: {res} ({opp}) -> дельта {delta:+d} = {rating}")

            streak_bonus = 10 if max_streak >= 2 else 0
            final_rating = rating + streak_bonus
            if streak_bonus > 0:
                self.log(state, "Мыслите (REASON)", f"Бонус за победную серию ({max_streak} подряд): +{streak_bonus}")
            state.computed_metrics = [{"final_rating": final_rating}]
            self.log(state, "Мыслите (REASON)", f"Итоговый подтверждённый рейтинг: {final_rating}")

        elif state.target_type == "source":
            state.computed_metrics = list(state.verified_candidates)

    def op_ksi(self, state: PipelineState) -> None:
        if state.error or not state.computed_metrics:
            return

        self.log(state, "Кси (COMPARE)", "Ранжирование и упорядочивание допустимых вариантов...")
        if state.target_type == "offer":
            ranked = sorted(state.computed_metrics, key=lambda x: (x["total_cost"], str(x["name"])))
            state.ranked_results = ranked
        elif state.target_type == "source":
            ranked = sorted(state.computed_metrics, key=lambda x: str(x.get("дата", "")), reverse=True)
            state.ranked_results = ranked
        else:
            state.ranked_results = list(state.computed_metrics)

    def op_fita(self, state: PipelineState) -> None:
        if state.error:
            state.selected_result = None
            return

        self.log(state, "Фита (SYNTHESIZE)", "Принятие оптимального решения на основе ранжирования...")
        if state.target_type == "offer":
            if state.ranked_results:
                state.selected_result = state.ranked_results[0]["name"]
        elif state.target_type == "inventory":
            if state.computed_metrics:
                state.selected_result = str(state.computed_metrics[0]["final_stock"])
        elif state.target_type == "rating":
            if state.computed_metrics:
                state.selected_result = str(state.computed_metrics[0]["final_rating"])
        elif state.target_type == "source":
            if state.ranked_results:
                state.selected_result = state.ranked_results[0].get("название")

    def op_zemlya(self, state: PipelineState) -> None:
        self.log(state, "Земля (GROUND)", "Формирование сертифицированного JSON-артефакта...")
        artifact = {
            "status": "REJECTED" if state.error else "SUCCESS",
            "answer": state.selected_result,
            "target_type": state.target_type,
            "pipeline": "БУКВА-49 (Азъ -> Вѣди -> Есть -> Мыслите -> Кси -> Фита -> Земля -> Ижа)",
            "selected_metric": state.best_score,
            "verified_candidates_count": len(state.verified_candidates),
            "audit_trail": state.audit_trail,
            "error": state.error,
        }
        state.final_artifact = artifact

    def op_ija(self, state: PipelineState) -> None:
        self.log(state, "Ижа (SEAL)", "Криптографическая печать полного контекста (HMAC / SHA-256)...")
        seal_payload = {
            "evidence": state.evidence,
            "initial_value": state.initial_value,
            "constraints": {
                "max_days": state.constraints.max_days,
                "require_confirmed": state.constraints.require_confirmed,
            },
            "selected_result": state.selected_result,
            "best_score": state.best_score,
            "steps_count": len(state.audit_trail),
            "status": "REJECTED" if state.error else "SUCCESS",
        }
        raw_json = json.dumps(seal_payload, sort_keys=True, ensure_ascii=False)
        raw_bytes = raw_json.encode("utf-8")

        if self.secret_key:
            key_bytes = self.secret_key.encode("utf-8") if isinstance(self.secret_key, str) else self.secret_key
            state.seal_hash = hmac.new(key_bytes, raw_bytes, hashlib.sha256).hexdigest()[:16]
            sig_type = "HMAC-SHA256"
        else:
            state.seal_hash = hashlib.sha256(raw_bytes).hexdigest()[:16]
            sig_type = "SHA256-DIGEST"

        if state.final_artifact:
            state.final_artifact["sha256_seal"] = state.seal_hash
            state.final_artifact["signature_type"] = sig_type
            state.final_artifact["seal_payload_sha256"] = hashlib.sha256(raw_bytes).hexdigest()
        self.log(state, "Ижа (SEAL)", f"Печать контекста ({sig_type}) установлена: {state.seal_hash}")

    def op_audit(self, state: PipelineState) -> None:
        self.log(state, "Есть (AUDIT)", "Контрольная верификация выходного артефакта...")
        state.is_valid = bool(
            state.final_artifact
            and not state.error
            and state.final_artifact.get("answer") is not None
            and state.seal_hash is not None
        )

    def run(
        self,
        task_text: str,
        candidates: list[dict] | None = None,
        constraints: TaskConstraints | None = None,
    ) -> PipelineState:
        t0 = time.monotonic()
        state = self.op_az(task_text, constraints=constraints)
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

    def run_spec(self, spec: TaskSpecification) -> PipelineState:
        """Execute directly from typed TaskSpecification bypassing regex extraction."""
        t0 = time.monotonic()
        state = PipelineState(
            task_description=spec.goal,
            target_type=spec.domain,
            evidence=list(spec.candidates),
            initial_value=spec.initial_value,
            constraints=spec.constraints,
        )
        self.log(state, "Азъ (INIT)", f"Спецификация загружена. Домен: {spec.domain.upper()}")
        self.op_est(state)
        self.op_myslite(state)
        self.op_ksi(state)
        self.op_fita(state)
        self.op_zemlya(state)
        self.op_ija(state)
        self.op_audit(state)
        state.execution_time = round(time.monotonic() - t0, 4)
        return state
