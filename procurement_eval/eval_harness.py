"""Каркас сравнения трёх конфигураций на закупочных лотах.

  direct  - модель читает лот и сразу называет победителя
  simple  - модель извлекает JSON, победителя выбирает обычная Python-функция
  bukva   - модель извлекает JSON, проверка схемы + цитат, затем BukvaAgentPipeline.run_spec

Метрики (на лот, с повторами):
  accuracy          верный ответ (победитель или верный отказ)
  confidently_wrong назван не тот победитель или назван победитель там, где его нет
  false_rejection   отказ на лоте, где победитель существует
  correct_refusal   отказ на лоте без победителя
  reproducibility   доля лотов с одинаковым ответом во всех повторах
  extraction        (simple, bukva) совпадение извлечённых ограничений и кандидатов с эталоном

Запуск:
  python eval_harness.py --check-gold                          # сверка эталона с обычной функцией
  python eval_harness.py --backend mock-oracle                 # проверка самого каркаса
  python eval_harness.py --backend ollama --model qwen3.5:9b   # реальный прогон
Только стандартная библиотека. bukva49 берётся из ../src или из установленного пакета.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
for cand in (HERE.parent / "src", HERE.parent.parent / "src"):
    if cand.exists():
        sys.path.insert(0, str(cand))
try:
    from bukva49 import BukvaAgentPipeline, TaskConstraints, TaskSpecification
except ImportError:  # каркас можно запускать и без пакета (тогда конфигурация bukva недоступна)
    BukvaAgentPipeline = None

CONSTRAINT_KEYS = ("max_days", "max_budget", "require_confirmed", "dumping_threshold_pct",
                   "reference_price", "allow_dumping_with_deposit")
CAND_KEYS = ("id", "price", "delivery", "days", "confirmed")
# поля, для которых непустое значение обязано подтверждаться цитатой из текста лота
QUOTED = ("max_days", "max_budget", "dumping_threshold_pct", "reference_price", "allow_dumping_with_deposit")
REFUSED = None


# ----------------------------------------------------------------- решающая функция
def plain_decide(constraints: dict, candidates: list[dict]):
    """Обычная функция: те же правила, без трассировки и без отказов по схеме."""
    ok = []
    for c in candidates:
        total = c["price"] + c["delivery"]
        if constraints.get("require_confirmed", True) and not c["confirmed"]:
            continue
        if constraints.get("max_days") is not None and c["days"] is not None and c["days"] > constraints["max_days"]:
            continue
        if constraints.get("max_budget") is not None and total > constraints["max_budget"]:
            continue
        pct, ref = constraints.get("dumping_threshold_pct"), constraints.get("reference_price")
        if pct and ref and c["price"] < ref * (1 - pct / 100) and not constraints.get("allow_dumping_with_deposit"):
            continue
        ok.append((total, str(c["id"])))
    return min(ok)[1] if ok else REFUSED


# ----------------------------------------------------------------- бэкенды
def _prompt_direct(lot):
    return ("Ты член закупочной комиссии. Выбери победителя по условиям лота. Учитывай подтверждённость документов, "
            "сроки, предельную сумму (с доставкой), демпинг и НДС, если они указаны. Если допустимого победителя нет, "
            'верни null. Ответ - один JSON: {"winner": "<буква поставщика или null>"}.\n\n'
            f"УСЛОВИЯ ЛОТА:\n{lot['text']}\n\nПРЕДЛОЖЕНИЯ:\n{lot['offers_text']}")


def _prompt_extract(lot):
    return ("Извлеки из текста лота данные в JSON. Ничего не выбирай и не считай победителя. "
            "Значение null означает «в тексте не указано». Цены в тенге, целые числа; если цена дана без НДС, "
            "пересчитай на условия сравнения из лота. Для каждого непустого ограничения (кроме require_confirmed) "
            "приведи дословную цитату из УСЛОВИЙ ЛОТА в поле quotes.\n"
            'Формат: {"constraints": {"max_days": int|null, "max_budget": int|null, "require_confirmed": bool, '
            '"dumping_threshold_pct": number|null, "reference_price": int|null, "allow_dumping_with_deposit": bool}, '
            '"quotes": {"<поле>": "<цитата>"}, '
            '"candidates": [{"id": "<буква>", "price": int, "delivery": int, "days": int|null, "confirmed": bool}]}\n\n'
            f"УСЛОВИЯ ЛОТА:\n{lot['text']}\n\nПРЕДЛОЖЕНИЯ:\n{lot['offers_text']}")


class OllamaBackend:
    def __init__(self, url, model, timeout=300):
        self.url, self.model, self.timeout = url, model, timeout

    def ask(self, kind, prompt, lot, run):
        body = json.dumps({"model": self.model, "stream": False, "format": "json",
                           "messages": [{"role": "user", "content": prompt}],
                           "options": {"temperature": 0, "seed": 297 + run}}).encode()
        req = urllib.request.Request(self.url, body, {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read())["message"]["content"]


class MockBackend:
    """Имитация модели, чтобы проверять каркас и метрики без настоящей модели."""
    def __init__(self, mode, p=0.3, seed=1):
        self.mode, self.p, self.seed = mode, p, seed

    def ask(self, kind, prompt, lot, run):
        rng = random.Random(f"{self.seed}-{lot['id']}-{kind}-{run}")
        g = lot["gold"]
        if kind == "direct":
            if self.mode == "mock-naive":  # берёт самое дешёвое по цене, игнорируя правила
                return json.dumps({"winner": min(g["candidates"], key=lambda c: c["price"])["id"]}, ensure_ascii=False)
            w = g["winner_id"]
            if self.mode == "mock-noisy" and rng.random() < self.p:
                w = rng.choice([c["id"] for c in g["candidates"]])
            return json.dumps({"winner": w}, ensure_ascii=False)
        ext = {"constraints": dict(g["constraints"]), "quotes": dict(g["quotes"]),
               "candidates": [{k: c[k] for k in CAND_KEYS} for c in g["candidates"]]}
        if self.mode == "mock-noisy" and rng.random() < self.p:
            fault = rng.choice(["drop", "hallucinate", "misprice", "broken"])
            if fault == "drop":                       # ограничение пропущено, но ключ на месте
                for k in QUOTED:
                    if ext["constraints"][k] not in (None, False):
                        ext["constraints"][k] = None if k != "allow_dumping_with_deposit" else False
                        ext["quotes"].pop(k, None)
                        break
            elif fault == "hallucinate":              # выдуманное ограничение с выдуманной цитатой
                ext["constraints"]["max_days"] = 3
                ext["quotes"]["max_days"] = "срок поставки не более 3 дней"
            elif fault == "misprice":
                ext["candidates"][0]["price"] = int(ext["candidates"][0]["price"] * 0.5)
            else:
                return '{"constraints": {"max_days": 5}'   # оборванный JSON
        return json.dumps(ext, ensure_ascii=False)


# ----------------------------------------------------------------- разбор ответов
def parse_json(text):
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _norm(s):
    return re.sub(r"\s+", " ", str(s).lower().replace("\u00a0", " ")).strip()


def validate_extraction(ext, lot):
    """Схема + цитаты. Возвращает (constraints, candidates) либо строку-причину отказа."""
    if not isinstance(ext, dict):
        return "не JSON"
    c, cands, quotes = ext.get("constraints"), ext.get("candidates"), ext.get("quotes") or {}
    if not isinstance(c, dict) or any(k not in c for k in CONSTRAINT_KEYS):
        return "не заполнены все поля constraints (ожидается null для «не указано»)"
    if not isinstance(cands, list) or not cands:
        return "нет кандидатов"
    for x in cands:
        if not isinstance(x, dict) or any(k not in x for k in CAND_KEYS):
            return "у кандидата не хватает полей"
        if not isinstance(x["price"], (int, float)) or not isinstance(x["delivery"], (int, float)):
            return "цена/доставка не числа"
        if c["max_days"] is not None and x["days"] is None:
            return "задан срок, но у кандидата нет срока"
    if c["dumping_threshold_pct"] and c["reference_price"] is None:
        return "задан порог демпинга без базы расчёта"
    src = _norm(lot["text"])
    for k in QUOTED:
        if c[k] in (None, False):
            continue
        q = _norm(quotes.get(k, ""))
        if not q or q not in src:
            return f"ограничение {k} не подтверждено цитатой из текста"
    return c, cands


# ----------------------------------------------------------------- конфигурации
def run_direct(backend, lot, run):
    out = parse_json(backend.ask("direct", _prompt_direct(lot), lot, run))
    if not isinstance(out, dict) or "winner" not in out:
        return REFUSED, "невалидный ответ"
    w = out["winner"]
    return (None if w in (None, "", "null") else str(w)), "ok"


def run_simple(backend, lot, run):
    ext = parse_json(backend.ask("extract", _prompt_extract(lot), lot, run))
    if not isinstance(ext, dict) or not isinstance(ext.get("candidates"), list) or not isinstance(ext.get("constraints"), dict):
        return REFUSED, "невалидное извлечение"
    try:
        c = {k: ext["constraints"].get(k) for k in CONSTRAINT_KEYS}
        cands = [{k: x.get(k) for k in CAND_KEYS} for x in ext["candidates"]]
        for x in cands:
            x["price"], x["delivery"] = x["price"] or 0, x["delivery"] or 0
        return plain_decide(c, cands), "ok"
    except (TypeError, KeyError):
        return REFUSED, "ошибка данных"


def run_bukva(backend, lot, run):
    ext = parse_json(backend.ask("extract", _prompt_extract(lot), lot, run))
    v = validate_extraction(ext, lot)
    if isinstance(v, str):
        return REFUSED, "fail-closed: " + v
    c, cands = v
    spec = TaskSpecification(
        domain="offer", goal=lot["id"],
        candidates=[{**x, "name": str(x["id"])} for x in cands],
        constraints=TaskConstraints(
            max_days=c["max_days"], require_confirmed=bool(c["require_confirmed"]), max_budget=c["max_budget"],
            dumping_threshold_pct=c["dumping_threshold_pct"], reference_price=c["reference_price"],
            allow_dumping_with_deposit=bool(c["allow_dumping_with_deposit"])))
    st = BukvaAgentPipeline(secret_key="eval").run_spec(spec)
    return (str(st.selected_id) if st.is_valid and st.selected_id is not None else REFUSED), (st.error or "ok")


CONFIGS = {"direct": run_direct, "simple": run_simple, "bukva": run_bukva}


# ----------------------------------------------------------------- метрики
def extraction_match(backend, lot):
    ext = parse_json(backend.ask("extract", _prompt_extract(lot), lot, 0))
    g = lot["gold"]
    if not isinstance(ext, dict) or not isinstance(ext.get("constraints"), dict) or not isinstance(ext.get("candidates"), list):
        return 0.0
    c_ok = all(ext["constraints"].get(k) == g["constraints"][k] for k in CONSTRAINT_KEYS)
    try:
        got = {str(x.get("id")): tuple(x.get(k) for k in CAND_KEYS[1:]) for x in ext["candidates"]}
        exp = {str(x["id"]): tuple(x[k] for k in CAND_KEYS[1:]) for x in g["candidates"]}
        return float(c_ok and got == exp)
    except (AttributeError, TypeError):
        return 0.0


def bootstrap_ci(values, n=2000, seed=0):
    if not values:
        return (0.0, 0.0)
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(values) for _ in values) / len(values) for _ in range(n))
    return means[int(0.025 * n)], means[int(0.975 * n) - 1]


def evaluate(lots, backend, configs, repeats):
    report = {}
    for name in configs:
        fn = CONFIGS[name]
        rows = []
        for lot in lots:
            answers = [fn(backend, lot, r) for r in range(repeats)]
            gold = lot["gold"]["winner_id"]
            first, reason = answers[0]
            rows.append(dict(lot=lot["id"], gold=gold, answers=[a for a, _ in answers], reason=reason,
                             stable=len({a for a, _ in answers}) == 1))
        acc, cw, fr, cr = [], [], [], []
        for r in rows:
            for a in r["answers"]:
                acc.append(float(a == r["gold"]))
                cw.append(float(a is not None and a != r["gold"]))
                if r["gold"] is not None:
                    fr.append(float(a is None))
                else:
                    cr.append(float(a is None))
        rep = dict(n_lots=len(rows), repeats=repeats,
                   accuracy=(sum(acc) / len(acc), *bootstrap_ci(acc)),
                   confidently_wrong=(sum(cw) / len(cw), *bootstrap_ci(cw)),
                   false_rejection=(sum(fr) / len(fr) if fr else None, *bootstrap_ci(fr)),
                   correct_refusal=(sum(cr) / len(cr) if cr else None, *bootstrap_ci(cr)),
                   reproducibility=sum(r["stable"] for r in rows) / len(rows), rows=rows)
        if name != "direct":
            ex = [extraction_match(backend, lot) for lot in lots]
            rep["extraction"] = sum(ex) / len(ex)
        report[name] = rep
    return report


def fmt(t):
    return "—" if t[0] is None else f"{t[0]:.2f} [{t[1]:.2f}; {t[2]:.2f}]"


def print_report(report):
    print(f"{'конфигурация':<14}{'accuracy':<22}{'confidently_wrong':<22}{'false_rejection':<22}{'correct_refusal':<22}{'repro':<7}{'extract'}")
    for name, r in report.items():
        print(f"{name:<14}{fmt(r['accuracy']):<22}{fmt(r['confidently_wrong']):<22}{fmt(r['false_rejection']):<22}"
              f"{fmt(r['correct_refusal']):<22}{r['reproducibility']:<7.2f}{r.get('extraction', float('nan')):.2f}")
    print(f"\nлотов: {next(iter(report.values()))['n_lots']}; интервалы - бутстрэп 95% по ответам. "
          "При числе лотов < 30 интервалы широкие: не делайте выводов о различиях конфигураций.")


# ----------------------------------------------------------------- проверка эталона
def check_gold(lots):
    bad = 0
    for lot in lots:
        g = lot["gold"]
        got = plain_decide(g["constraints"], g["candidates"])
        src = _norm(lot["text"])
        problems = []
        if got != g["winner_id"]:
            problems.append(f"победитель по правилам {got}, в эталоне {g['winner_id']}")
        for k in QUOTED:
            if g["constraints"][k] not in (None, False) and _norm(g["quotes"].get(k, "")) not in src:
                problems.append(f"цитата для {k} отсутствует в тексте")
        if problems:
            bad += 1
            print(f"[!] {lot['id']}: " + "; ".join(problems))
    print(f"Сверка эталона: {len(lots) - bad}/{len(lots)} лотов согласованы. "
          "Это ловит арифметические ошибки разметки, но не заменяет независимую проверку человеком.")
    return bad == 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lots", type=Path, default=HERE / "lots_seed.json")
    ap.add_argument("--backend", default="mock-oracle",
                    choices=["ollama", "mock-oracle", "mock-noisy", "mock-naive"])
    ap.add_argument("--model", default="qwen3.5:9b")
    ap.add_argument("--url", default="http://127.0.0.1:11434/api/chat")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--configs", default="direct,simple,bukva")
    ap.add_argument("--noise", type=float, default=0.3, help="доля ошибок для mock-noisy")
    ap.add_argument("--check-gold", action="store_true")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()

    lots = json.loads(a.lots.read_text(encoding="utf-8"))
    if a.check_gold:
        sys.exit(0 if check_gold(lots) else 1)
    if any(l.get("synthetic") for l in lots):
        print("ВНИМАНИЕ: в наборе есть синтетические лоты. Они годятся для проверки каркаса, но не для выводов о моделях.\n")
    configs = [c for c in a.configs.split(",") if c]
    if "bukva" in configs and BukvaAgentPipeline is None:
        sys.exit("Конфигурация bukva недоступна: пакет bukva49 не найден (pip install -e . в корне репозитория).")
    backend = OllamaBackend(a.url, a.model) if a.backend == "ollama" else MockBackend(a.backend, a.noise)
    report = evaluate(lots, backend, configs, a.repeats)
    print_report(report)
    if a.out:
        a.out.write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
