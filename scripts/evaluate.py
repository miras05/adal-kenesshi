"""Оценка качества бота на контрольном наборе вопросов (tests/eval/questions.json).

Каждый вопрос прогоняется через полный конвейер (поиск + LLM), считаются метрики:
- Поиск: нужный документ среди найденных фрагментов;
- Цитирование: бот сослался на нужный документ;
- Ловушки: на посторонние вопросы бот не отвечает «по документам» (нет ссылок);
- Проверка фактов: вердикт совпал с ожидаемым;
- Язык: ответ на языке вопроса.

Запуск:  python -m scripts.evaluate        (≈ $0.05 на Claude Haiku)
Отчёт:   docs/EVALUATION.md
"""
import asyncio
import json
import os
import time
from collections import defaultdict
from pathlib import Path

# Оценка не должна портить аналитику и дневной лимит: отдельная БД, без лимита
os.environ.setdefault("DB_PATH", str(Path(__file__).resolve().parent.parent / "data" / "eval.db"))
os.environ.setdefault("DAILY_LLM_LIMIT", "100000")

from app import config  # noqa: E402
from app.rag.retriever import KK_LETTERS  # noqa: E402


def answer_lang(text: str) -> str:
    """Язык ответа по доле специфических казахских букв (одно слово «шаңырақ» не делает текст казахским)."""
    letters = [ch for ch in text.lower() if ch.isalpha()]
    kk = sum(ch in KK_LETTERS for ch in letters)
    return "kk" if letters and kk / len(letters) > 0.015 else "ru"

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS = ROOT / "tests" / "eval" / "questions.json"
REPORT = ROOT / "docs" / "EVALUATION.md"

CATEGORY_NAMES = {
    "constitution": "Конституция 2026", "values": "Ценности и принципы (Указ № 1081)",
    "addresses": "Послания Президента", "laws": "Законы и антикоррупция",
    "situation": "Режим «Моя ситуация»", "factcheck": "Режим «Проверка факта»", "trap": "Вопросы-ловушки",
}


def doc_match(doc_id: str, expected: list[str]) -> bool:
    return any(doc_id.startswith(e) for e in expected)


async def run_one(item: dict) -> dict:
    from app import service
    t0 = time.monotonic()
    r = await service.answer_text(item["question"], lang=item["lang"], mode=item["mode"], channel="eval")
    src_docs = [s.get("doc_id", "") for s in r["sources"]]
    cited_docs = [r["sources"][n - 1].get("doc_id", "") for n in r["cited"]]
    exp = item["expect_docs"]
    res = {
        **item,
        "answer": r["text"],
        "latency_s": round(time.monotonic() - t0, 1),
        "verdict": r.get("verdict"),
        "retrieval_ok": bool(exp) and any(doc_match(d, exp) for d in src_docs),
        "citation_ok": bool(exp) and any(doc_match(d, exp) for d in cited_docs),
        "refused": not r["cited"],
        "lang_ok": answer_lang(r["text"]) == item["lang"] if r["text"] else False,
        "error": r.get("error"),
    }
    if item["category"] == "trap":
        res["pass"] = res["refused"]
    elif item["mode"] == "factcheck":
        res["pass"] = (r.get("verdict") or "UNKNOWN") in item["expect_verdict"].split("|") and \
            (not exp or res["citation_ok"])
    else:
        res["pass"] = res["citation_ok"]
    return res


def pct(a: int, b: int) -> str:
    return f"{(100 * a / b):.0f}% ({a}/{b})" if b else "—"


def write_report(results: list[dict]) -> str:
    by_cat = defaultdict(list)
    for r in results:
        by_cat[r["category"]].append(r)
    answerable = [r for r in results if r["category"] != "trap" and r["expect_docs"]]
    traps = by_cat["trap"]
    facts = by_cat["factcheck"]
    kk = [r for r in results if r["lang"] == "kk"]
    lines = [
        "# Оценка качества «Адал Кеңесші»", "",
        f"Дата: {time.strftime('%Y-%m-%d %H:%M')} · модель: `{config.LLM_MODEL}` · вопросов: {len(results)}  ",
        "Набор: `tests/eval/questions.json` · запуск: `python -m scripts.evaluate`", "",
        "## Главные цифры", "",
        "| Метрика | Результат |", "|---|---|",
        f"| **Итог: вопросов пройдено** | **{pct(sum(r['pass'] for r in results), len(results))}** |",
        f"| Поиск нашёл нужный документ | {pct(sum(r['retrieval_ok'] for r in answerable), len(answerable))} |",
        f"| Бот сослался на нужный документ | {pct(sum(r['citation_ok'] for r in answerable), len(answerable))} |",
        f"| Отказ на вопросы-ловушки (без выдумок) | {pct(sum(r['refused'] for r in traps), len(traps))} |",
        f"| Верный вердикт проверки фактов | {pct(sum(r['pass'] for r in facts), len(facts))} |",
        f"| Ответ на языке вопроса | {pct(sum(r['lang_ok'] for r in results if r['category'] != 'trap'), len([r for r in results if r['category'] != 'trap']))} |",
        f"| Казахский язык: вопросов пройдено | {pct(sum(r['pass'] for r in kk), len(kk))} |",
        f"| Среднее время ответа | {sum(r['latency_s'] for r in results) / len(results):.1f} с |",
        "", "## По категориям", "", "| Категория | Пройдено |", "|---|---|",
    ]
    for cat, rs in by_cat.items():
        lines.append(f"| {CATEGORY_NAMES.get(cat, cat)} | {pct(sum(r['pass'] for r in rs), len(rs))} |")
    lines += ["", "## Все вопросы", "", "| # | Вопрос | Режим | Язык | Результат | Вердикт | Время |", "|---|---|---|---|---|---|---|"]
    for i, r in enumerate(results, 1):
        q = r["question"].replace("|", "/")
        lines.append(f"| {i} | {q} | {r['mode']} | {r['lang']} | {'✅' if r['pass'] else '❌'} | {r.get('verdict') or ''} | {r['latency_s']} с |")
    failed = [r for r in results if not r["pass"]]
    if failed:
        lines += ["", "## Разбор непройденных", ""]
        for r in failed:
            lines += [f"**{r['question']}** — ожидались документы `{', '.join(r['expect_docs']) or '—'}`"
                      f"{', вердикт ' + r['expect_verdict'] if r.get('expect_verdict') else ''}; "
                      f"получено: вердикт `{r.get('verdict')}`, ссылки на нужный документ: {r['citation_ok']}.", "",
                      "> " + r["answer"][:500].replace("\n", " "), ""]
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    return "\n".join(lines[:22])


async def main() -> None:
    items = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    results = []
    for i, item in enumerate(items, 1):
        r = await run_one(item)
        results.append(r)
        print(f"{i:>2}/{len(items)} {'✅' if r['pass'] else '❌'} [{r['category']}] {r['question'][:70]}", flush=True)
    (ROOT / "tests" / "eval" / "last_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n" + write_report(results))


if __name__ == "__main__":
    asyncio.run(main())
    os._exit(0)  # не ждём фоновые потоки ONNX
