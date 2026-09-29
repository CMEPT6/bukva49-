"""Paired benchmark of instruction workflows on an actual local/chat model."""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path


MODES = {
    "direct": (
        "Реши задачу. Верни один JSON-объект с ключом answer и строковым значением."
    ),
    "cot": (
        "Порядок действий: "
        "1. Выдели факты и ограничения. "
        "2. Проверь достоверность условий и отфильтруй неподходящие данные. "
        "3. Рассчитай промежуточные величины. "
        "4. Сравни допустимые варианты. "
        "5. Выбери решение. "
        "6. Проверь итог. "
        "Верни один JSON-объект с ключом answer и строковым значением."
    ),
    "297": (
        "Вѣди: выдели факты из данного пакета. "
        "Фита: соедини их для решения. "
        "Земля: дай результат. "
        "Верни один JSON-объект с ключом answer и строковым значением."
    ),
    "full": (
        "Вѣди: выдели факты из пакета. "
        "Есть: проверь достоверность источников и условий, отбрось недопустимые. "
        "Мыслите: рассчитай нужные величины. "
        "Кси: сравни варианты. "
        "Фита: выбери решение. "
        "Земля: дай результат. "
        "Ещё раз Есть: проверь итог. "
        "Верни один JSON-объект с ключом answer и строковым значением."
    ),
}


@dataclass(frozen=True)
class Case:
    id: str
    family: str
    question: str
    answer: str


def cases(seed: int, per_family: int) -> list[Case]:
    rng = random.Random(seed)
    out: list[Case] = []
    for i in range(per_family):
        # 1. Offer with delivery deadline trap & verification
        # Rule: delivery must be <= max_days, must be confirmed, minimize price + delivery_cost
        max_days = rng.choice([3, 4, 5])
        offers = []
        for j in range(4):
            name = f"П{j + 1}"
            price = rng.randrange(7000, 15000, 100)
            delivery_cost = rng.randrange(500, 3000, 100)
            days = rng.randrange(1, 9)
            confirmed = True
            offers.append({
                "name": name,
                "price": price,
                "delivery_cost": delivery_cost,
                "days": days,
                "confirmed": confirmed,
            })
        # Introduce deliberate traps
        # j=0: cheapest base price, but delivery exceeds max_days (disqualified)
        offers[0]["price"] = min(o["price"] for o in offers) - 1500
        offers[0]["days"] = max_days + rng.randint(2, 4)
        offers[0]["confirmed"] = True
        # j=1: very low total, but not confirmed (disqualified)
        offers[1]["price"] = min(o["price"] for o in offers) - 500
        offers[1]["days"] = max_days - 1
        offers[1]["confirmed"] = False
        # j=2 and j=3: valid candidates
        offers[2]["days"] = min(max_days, offers[2]["days"])
        offers[2]["confirmed"] = True
        offers[3]["days"] = min(max_days, offers[3]["days"])
        offers[3]["confirmed"] = True

        valid_offers = [o for o in offers if o["confirmed"] and o["days"] <= max_days]
        if not valid_offers:
            offers[2]["confirmed"] = True
            offers[2]["days"] = max_days
            valid_offers = [offers[2]]
        best_offer = min(valid_offers, key=lambda o: (o["price"] + o["delivery_cost"], o["name"]))
        rng.shuffle(offers)

        q_offer = (
            f"Выбери поставщика для закупки. Обязательные условия: "
            f"1) статус подтверждён (confirmed = true); "
            f"2) срок доставки не более {max_days} дней (days <= {max_days}). "
            f"Среди подходящих выбери предложение с минимальной суммой цены и доставки (price + delivery_cost). "
            f"При равенстве выбери меньшее по алфавиту название. Ответ: только название (например П1). "
            f"Данные: {json.dumps(offers, ensure_ascii=False)}"
        )
        out.append(Case(f"offer-{i}", "offer", q_offer, best_offer["name"]))

        # 2. Inventory recount with cancelled transactions and reserves
        init_stock = rng.randrange(40, 120) * 10
        p1 = rng.randrange(10, 40) * 10
        o1 = rng.randrange(10, 30) * 10
        p2_cancelled = rng.randrange(15, 35) * 10
        o2_failed = rng.randrange(5, 20) * 10
        ret1 = rng.randrange(2, 10) * 10
        reserve = rng.randrange(5, 15) * 10

        txs = [
            {"тип": "поступление", "кол-во": p1, "статус": "проведено"},
            {"тип": "отгрузка", "кол-во": o1, "статус": "проведено"},
            {"тип": "поступление", "кол-во": p2_cancelled, "статус": "отменено"},
            {"тип": "отгрузка", "кол-во": o2_failed, "статус": "ошибка_ввода"},
            {"тип": "возврат_клиента", "кол-во": ret1, "статус": "проведено"},
            {"тип": "резерв_заказа", "кол-во": reserve, "статус": "в_резерве"},
        ]
        rng.shuffle(txs)
        # Physical stock: init + p1 - o1 + ret1
        expected_stock = init_stock + p1 - o1 + ret1

        q_inv = (
            f"Рассчитай фактический физический остаток товара на складе в штуках. "
            f"Начальный остаток: {init_stock} шт. "
            f"Правила: учитывай только транзакции со статусом «проведено» (поступление и возврат_клиента прибавляют товар, "
            f"отгрузка убавляет). Транзакции со статусами «отменено» и «ошибка_ввода» не состоялись — их не учитывать. "
            f"Резерв физический остаток на складе не уменьшает. "
            f"Ответ: только одно целое число. "
            f"Список операций: {json.dumps(txs, ensure_ascii=False)}"
        )
        out.append(Case(f"inventory-{i}", "inventory", q_inv, str(expected_stock)))

        # 3. Chess rating calculation with multi-tier rules and streak bonus
        start_rating = rng.randrange(1400, 1900, 20)
        rounds = []
        cur_rating = start_rating
        wins_streak = 0
        max_streak = 0
        results_pool = [
            ("победа", "сильный"),
            ("победа", "слабый"),
            ("ничья", "равный"),
            ("поражение", "равный"),
        ]
        for r_idx in range(4):
            res, opp = results_pool[(i + r_idx) % len(results_pool)]
            rounds.append({"тур": r_idx + 1, "результат": res, "соперник": opp})
            if res == "победа":
                cur_rating += 15 if opp == "сильный" else 10
                wins_streak += 1
                if wins_streak > max_streak:
                    max_streak = wins_streak
            elif res == "ничья":
                cur_rating += 0
                wins_streak = 0
            elif res == "поражение":
                cur_rating -= 12
                wins_streak = 0

        streak_bonus = 10 if max_streak >= 2 else 0
        final_rating = cur_rating + streak_bonus

        q_chess = (
            f"Посчитай итоговый рейтинг шахматиста после турнира из 4 туров. "
            f"Начальный рейтинг: {start_rating}. "
            f"Правила изменения рейтинга за партию: "
            f"победа над сильным соперником: +15; победа над слабым соперником: +10; "
            f"ничья: 0; поражение: -12. "
            f"Специальный бонус: если за турнир есть серия из 2 или более побед подряд, "
            f"в самом конце начисляется разовый бонус +10 к итоговому рейтингу. "
            f"Ответ: только целое число. "
            f"Результаты туров по порядку: {json.dumps(rounds, ensure_ascii=False)}"
        )
        out.append(Case(f"rating-{i}", "rating", q_chess, str(final_rating)))

        # 4. Source conflict with dates and draft status
        names = ["Орион", "Сириус", "Вега", "Арктур", "Альтаир"]
        rng.shuffle(names)
        candidates = [
            {"название": names[0], "дата": "2026-02-10", "статус": "утверждено"},
            {"название": names[1], "дата": "2026-05-18", "статус": "утверждено"},
            {"название": names[2], "дата": "2026-07-01", "статус": "черновик"},
            {"название": names[3], "дата": "2026-04-12", "статус": "отозвано"},
        ]
        # Valid approved items: names[0] (Feb) and names[1] (May). Latest approved is names[1].
        # names[2] has July date (newer!), but is draft.
        rng.shuffle(candidates)
        best_source = names[1]

        q_source = (
            f"Определи официальное утверждённое кодовое название проекта. "
            f"Правила выбора: использовать только записи со статусом «утверждено». "
            f"Записи со статусами «черновик» и «отозвано» не имеют силы независимо от даты. "
            f"Из утверждённых выбери запись с самой поздней датой. "
            f"Ответ: только название. "
            f"Записи: {json.dumps(candidates, ensure_ascii=False)}"
        )
        out.append(Case(f"source-{i}", "source", q_source, best_source))

    return out


def extract_answer(content: str) -> str | None:
    if not content:
        return None

    # Strip reasoning tags like <think>...</think> if present
    cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    target_str = cleaned if cleaned else content

    # 1. Try direct JSON parse
    try:
        parsed = json.loads(target_str)
        if isinstance(parsed, dict) and "answer" in parsed:
            val = parsed["answer"]
            if isinstance(val, (str, int, float)):
                return str(val).strip()
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass

    # 2. Try markdown fence ```json ... ```
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", target_str, flags=re.DOTALL)
    if fence:
        try:
            parsed = json.loads(fence.group(1))
            if isinstance(parsed, dict) and "answer" in parsed:
                val = parsed["answer"]
                if isinstance(val, (str, int, float)):
                    return str(val).strip()
        except (ValueError, AttributeError):
            pass

    # 3. Match any outermost or inner JSON object with "answer" key
    matches = re.findall(r"\{[^{}]*\"answer\"\s*:[^{}]*\}", target_str, flags=re.DOTALL)
    for m in reversed(matches):
        try:
            parsed = json.loads(m)
            if isinstance(parsed, dict) and "answer" in parsed:
                val = parsed["answer"]
                if isinstance(val, (str, int, float)):
                    return str(val).strip()
        except (ValueError, AttributeError):
            pass

    # 4. Fallback search for any { ... }
    found = re.search(r"\{[^{}]*\}", target_str, flags=re.DOTALL)
    if found:
        try:
            parsed = json.loads(found.group(0))
            if isinstance(parsed, dict) and "answer" in parsed:
                val = parsed["answer"]
                if isinstance(val, (str, int, float)):
                    return str(val).strip()
        except (ValueError, AttributeError):
            pass

    return None


def request_model(url: str, model: str, mode: str, case: Case, timeout: float) -> dict:
    messages = [
        {"role": "system", "content": MODES[mode]},
        {"role": "user", "content": case.question},
    ]
    openai = url.rstrip("/").endswith("/v1/chat/completions")
    payload = (
        {"model": model, "messages": messages, "temperature": 0, "stream": False}
        if openai
        else {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0, "seed": 297},
        }
    )
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    last_err = None
    for attempt in range(2):
        try:
            start = time.monotonic()
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw_body = response.read().decode("utf-8", errors="replace")
                data = json.loads(raw_body)
            seconds = round(time.monotonic() - start, 3)
            break
        except Exception as e:
            last_err = e
            if attempt == 0:
                time.sleep(3)
                continue
            raise last_err
    if openai:
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens")
        output_tokens = usage.get("completion_tokens")
    else:
        content = data.get("message", {}).get("content", "")
        input_tokens = data.get("prompt_eval_count")
        output_tokens = data.get("eval_count")
    return {
        "content": content,
        "seconds": seconds,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


def grade(case: Case, result: dict) -> dict:
    answer = extract_answer(result["content"])
    is_correct = answer is not None and answer.strip().lower() == case.answer.strip().lower()
    return {
        "case_id": case.id,
        "family": case.family,
        "expected": case.answer,
        "answer": answer,
        "valid_json": answer is not None,
        "correct": is_correct,
        **result,
    }


def summarize(rows: list[dict]) -> dict:
    if not rows:
        return {"n": 0, "accuracy": 0.0, "json_rate": 0.0, "mean_seconds": 0.0,
                "mean_input_tokens": None, "mean_output_tokens": None}
    families = sorted({row["family"] for row in rows})

    def metrics(group: list[dict]) -> dict:
        n = len(group)
        if n == 0:
            return {"n": 0, "accuracy": 0.0, "json_rate": 0.0, "mean_seconds": 0.0,
                    "mean_input_tokens": None, "mean_output_tokens": None}
        return {
            "n": n,
            "accuracy": round(sum(r["correct"] for r in group) / n, 4),
            "json_rate": round(sum(r["valid_json"] for r in group) / n, 4),
            "mean_seconds": round(sum(r["seconds"] for r in group) / n, 3),
            "mean_input_tokens": (
                round(sum(r["input_tokens"] for r in group if r["input_tokens"] is not None) / n, 1)
                if any(r["input_tokens"] is not None for r in group)
                else None
            ),
            "mean_output_tokens": (
                round(sum(r["output_tokens"] for r in group if r["output_tokens"] is not None) / n, 1)
                if any(r["output_tokens"] is not None for r in group)
                else None
            ),
        }

    return {
        "overall": metrics(rows),
        "by_family": {f: metrics([r for r in rows if r["family"] == f]) for f in families},
    }


def save_checkpoint(path: Path, result_dict: dict) -> None:
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(result_dict, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(path)


def load_checkpoint(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "modes" in data:
            return data
    except Exception:
        pass
    return None


def benchmark(args: argparse.Namespace) -> dict:
    if args.per_family < 1:
        raise ValueError("per-family must be positive")

    all_cases = cases(args.seed, args.per_family)
    total_tasks = len(all_cases) * len(MODES)

    existing_rows: dict[str, list[dict]] = {mode: [] for mode in MODES}
    completed_keys: set[tuple[str, str]] = set()

    if not args.no_resume:
        loaded = load_checkpoint(args.output)
        if loaded and loaded.get("model") == args.model and loaded.get("seed") == args.seed and loaded.get("cases_per_family") == args.per_family:
            print(f"[*] Найден предыдущий контрольный файл {args.output}. Восстанавливаем прогресс...", flush=True)
            for mode, m_data in loaded.get("modes", {}).items():
                if mode in existing_rows:
                    for row in m_data.get("rows", []):
                        existing_rows[mode].append(row)
                        completed_keys.add((row["case_id"], mode))
            print(f"[*] Уже выполнено: {len(completed_keys)} из {total_tasks} запросов.", flush=True)

    rng = random.Random(args.seed + 99)
    work = [(case, mode) for case in all_cases for mode in MODES]
    rng.shuffle(work)

    def current_state_payload() -> dict:
        return {
            "model": args.model,
            "url": args.url,
            "seed": args.seed,
            "cases_per_family": args.per_family,
            "case_set": [asdict(c) for c in all_cases],
            "modes": {
                mode: {"metrics": summarize(data), "rows": data}
                for mode, data in existing_rows.items()
            },
        }

    done_counter = len(completed_keys)
    for case, mode in work:
        if (case.id, mode) in completed_keys:
            continue

        done_counter += 1
        print(f"[{done_counter}/{total_tasks}] Запрос: {case.id} ({case.family}) | Режим: {mode} ...", end=" ", flush=True)

        try:
            result = request_model(args.url, args.model, mode, case, args.timeout)
            graded = grade(case, result)
            existing_rows[mode].append(graded)
            completed_keys.add((case.id, mode))
            status = "OK" if graded["correct"] else f"FAIL (ожидали {graded['expected']}, получили {graded['answer']})"
            print(f"{status} [{graded['seconds']}s, tok: {graded['output_tokens']}]", flush=True)
        except Exception as e:
            print(f"ОШИБКА: {e}", flush=True)
            raise

        # Checkpoint immediately after each call
        save_checkpoint(args.output, current_state_payload())

    final_result = current_state_payload()
    save_checkpoint(args.output, final_result)
    return final_result


def print_comparison_table(result: dict) -> None:
    print("\n" + "=" * 78)
    print("ИТОГОВОЕ СРАВНЕНИЕ РЕЖИМОВ (BUKVA-49 Benchmark v0.6)")
    print("=" * 78)
    header = f"{'Режим':<14} | {'Верно':<10} | {'Точность':<10} | {'JSON Валидн':<12} | {'Ср. время':<10} | {'Ср. токенов':<12}"
    print(header)
    print("-" * 78)
    for mode, data in result["modes"].items():
        m = data["metrics"]["overall"]
        n = m["n"]
        acc = f"{m['accuracy'] * 100:.1f}%"
        correct_cnt = f"{int(round(m['accuracy'] * n))}/{n}"
        json_rate = f"{m['json_rate'] * 100:.1f}%"
        mean_sec = f"{m['mean_seconds']:.1f} c"
        mean_tok = f"{m['mean_output_tokens']:.0f}" if m.get("mean_output_tokens") is not None else "-"
        print(f"{mode:<14} | {correct_cnt:<10} | {acc:<10} | {json_rate:<12} | {mean_sec:<10} | {mean_tok:<12}")
    print("=" * 78)

    print("\nРазбивка точности по категориям задач:")
    all_families = sorted({f for m in result["modes"].values() for f in m["metrics"]["by_family"]})
    fam_header = f"{'Категория':<16} | " + " | ".join(f"{m:<12}" for m in result["modes"])
    print(fam_header)
    print("-" * len(fam_header))
    for fam in all_families:
        row_str = f"{fam:<16} | "
        vals = []
        for mode in result["modes"]:
            fm = result["modes"][mode]["metrics"]["by_family"].get(fam)
            if fm:
                vals.append(f"{fm['accuracy']*100:.0f}% ({int(round(fm['accuracy']*fm['n']))}/{fm['n']})")
            else:
                vals.append("-")
        row_str += " | ".join(f"{v:<12}" for v in vals)
        print(row_str)
    print("=" * 78 + "\n")


def main() -> None:
    # Ensure stdout handles UTF-8 on Windows terminal
    if sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            pass

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="qwen3.5:9b", help="Имя модели Ollama (по умолч.: qwen3.5:9b)")
    parser.add_argument("--url", default="http://127.0.0.1:11434/api/chat", help="URL API")
    parser.add_argument("--seed", type=int, default=297, help="Случайное зерно генерации (по умолч.: 297)")
    parser.add_argument("--per-family", type=int, default=2, help="Количество задач в каждой категории")
    parser.add_argument("--timeout", type=float, default=300, help="Таймаут запроса в секундах (по умолч.: 300)")
    parser.add_argument("--output", type=Path, default=Path("llm_result.json"), help="Путь для сохранения отчета")
    parser.add_argument("--no-resume", action="store_true", help="Не загружать предыдущий прогресс, начать заново")
    args = parser.parse_args()

    try:
        result = benchmark(args)
    except (urllib.error.URLError, TimeoutError) as error:
        parser.exit(2, f"Сервер модели недоступен: {error}\n")

    print_comparison_table(result)


if __name__ == "__main__":
    main()
