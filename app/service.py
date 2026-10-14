"""Конвейер ответа на вопрос (общий для Web и Telegram).

  вопрос → валидация → (переформулировка с учётом истории) → гибридный поиск
        → порог релевантности → LLM с цитированием → журнал в БД

Отдаёт поток событий:
  {"type": "sources", ...}  найденные источники (до начала генерации)
  {"type": "delta", "text"} очередной кусочек ответа
  {"type": "done", ...}     итог: id запроса, процитированные источники, время
  {"type": "error", ...}    понятное сообщение об ошибке
"""
import asyncio
import logging
import re
import time
from collections.abc import AsyncIterator
from urllib.parse import quote

from app import config, db, llm, prompts
from app.rag import index as rag_index
from app.rag.retriever import Retriever, detect_lang
from app.security import ValidationError, clean_question, looks_like_injection

log = logging.getLogger("service")

_retriever: Retriever | None = None

ERRORS = {
    "ru": {
        "empty": "Пожалуйста, введите вопрос.",
        "too_long": f"Вопрос слишком длинный (максимум {config.MAX_QUESTION_LEN} символов). Сформулируйте короче.",
        "rate_limit": "Слишком много запросов. Подождите минуту и попробуйте снова.",
        "network": "Нет связи с AI-сервисом. Попробуйте ещё раз через несколько секунд.",
        "auth": "AI-сервис не настроен (неверный API-ключ). Сообщите администратору.",
        "no_key": "AI-сервис не настроен (нет API-ключа). Сообщите администратору.",
        "credit": "Закончился лимит AI-сервиса. Сообщите администратору.",
        "api": "AI-сервис временно недоступен. Попробуйте позже.",
        "refusal": "Не могу ответить на этот запрос. Попробуйте сформулировать вопрос иначе.",
        "daily_limit": "Демо-версия исчерпала дневной лимит вопросов. Приходите завтра — или попробуйте вкладки «Ценности» и «Квиз».",
    },
    "kk": {
        "empty": "Сұрағыңызды жазыңыз.",
        "too_long": f"Сұрақ тым ұзын (ең көбі {config.MAX_QUESTION_LEN} таңба). Қысқарақ жазыңыз.",
        "rate_limit": "Сұраулар тым көп. Бір минут күтіп, қайталап көріңіз.",
        "network": "AI-сервиспен байланыс жоқ. Бірнеше секундтан соң қайталап көріңіз.",
        "auth": "AI-сервис бапталмаған (API-кілт қате). Әкімшіге хабарлаңыз.",
        "no_key": "AI-сервис бапталмаған (API-кілт жоқ). Әкімшіге хабарлаңыз.",
        "credit": "AI-сервис лимиті бітті. Әкімшіге хабарлаңыз.",
        "api": "AI-сервис уақытша қолжетімсіз. Кейінірек қайталап көріңіз.",
        "refusal": "Бұл сұраққа жауап бере алмаймын. Сұрақты басқаша қойып көріңіз.",
        "daily_limit": "Демо-нұсқаның бүгінгі сұрақ лимиті бітті. Ертең келіңіз — немесе «Құндылықтар» мен «Квиз» бөлімдерін қараңыз.",
    },
}

CITE_RE = re.compile(r"\[(\d{1,2})\]")
# Отрицания в строке «📜 …»: модель иногда ставит значок, сообщая, что понятия в Конституции НЕТ
NEGATION_RE = re.compile(
    r"не\s+упомина|не\s+содерж|не\s+закреп|не\s+встреча|не\s+наз|отсутству|нет\b"
    r"|кездеспейді|жоқ|аталмайды|айтылмаған|бекітілмеген|көрсетілмеген", re.IGNORECASE)


def fix_constitution_lines(text: str) -> str:
    """Значок 📜 оставляем только там, где Конституция действительно закрепляет понятие."""
    out = []
    for line in text.split("\n"):
        if "📜" in line and NEGATION_RE.search(line):
            line = re.sub(r"\*\*Закреплено в Конституции РК 2026:\*\*\s*", "", line.replace("📜", "ℹ️"))
        out.append(line)
    return "\n".join(out)


def get_retriever() -> Retriever:
    global _retriever
    if _retriever is None:
        chunks, emb = rag_index.load()
        _retriever = Retriever(chunks, emb, rag_index.embed_query)
    return _retriever


def error_text(code: str, lang: str) -> str:
    return ERRORS.get(lang, ERRORS["ru"]).get(code, ERRORS["ru"]["api"])


def deep_link(chunk: dict) -> str:
    """Ссылка, которая открывает первоисточник сразу на нужном месте
    (Text Fragments: https://...#:~:text=...) — работает в Chrome/Edge/Safari."""
    first_line = chunk["text"].split("\n", 1)[0]
    words = first_line.split()[:8]
    if len(words) < 3:
        return chunk["url"]
    return f"{chunk['url']}#:~:text={quote(' '.join(words), safe='')}"


def source_card(n: int, hit) -> dict:
    c = hit.chunk
    return {
        "n": n,
        "title": c["title"],
        "type": c["type"],
        "type_label": prompts.TYPE_LABELS.get(c["type"], c["type"]),
        "date": c["date"],
        "article": c.get("article", ""),
        "section": c.get("section", ""),
        "url": c["url"],
        "link": deep_link(c),
        "snippet": c["text"][:320] + ("…" if len(c["text"]) > 320 else ""),
        "score": round(hit.dense, 3),
        "is_constitution": c["type"] == "constitution",
    }


async def standalone_question(question: str, history: list[dict]) -> str:
    """Уточняющий вопрос («а что там про молодёжь?») превращаем в самостоятельный,
    иначе поиск не поймёт, о чём речь."""
    if not history:
        return question
    hist = "\n".join(f"{m['role']}: {m['content'][:500]}" for m in history[-4:])
    try:
        rewritten = await llm.complete(prompts.REWRITE_PROMPT.format(history=hist, question=question))
    except llm.LLMError:
        return question
    return rewritten if 3 < len(rewritten) < 500 else question


async def answer(question: str, history: list[dict] | None = None, lang: str | None = None,
                 channel: str = "web", user: str = "anon") -> AsyncIterator[dict]:
    t0 = time.monotonic()
    history = [m for m in (history or []) if m.get("role") in ("user", "assistant") and m.get("content")][-6:]
    try:
        question = clean_question(question)
    except ValidationError as e:
        yield {"type": "error", "code": str(e), "message": error_text(str(e), lang or "ru")}
        return

    # Язык ответа — по самому вопросу: казахский вопрос в русском интерфейсе получит
    # ответ на казахском. Язык интерфейса — запасной вариант для неоднозначных случаев.
    detected = detect_lang(question)
    lang = "kk" if detected == "kk" else (lang if lang in ("ru", "kk") and len(question) < 12 else "ru")
    record = dict(user_hash=db.user_hash(user), channel=channel, lang=lang, question=question[:1000])
    if looks_like_injection(question):
        log.warning("Possible prompt injection from %s: %r", record["user_hash"], question[:200])

    search_q = await standalone_question(question, history)
    # Поиск — CPU-задача (векторизация), выносим из event loop
    hits = await asyncio.to_thread(get_retriever().search, search_q, config.TOP_K, lang)
    top = max((h.dense for h in hits), default=0.0)
    record["top_score"] = round(top, 4)

    # Порог: если даже лучший фрагмент слабо похож на вопрос — не тратим LLM,
    # честно говорим, что подтверждённой информации нет (п. 4.9 Положения).
    if top < config.MIN_RELEVANCE:
        text = prompts.NO_INFO_TEXT[lang]
        yield {"type": "delta", "text": text}
        qid = db.log_query(**record, answered=0, latency_ms=int((time.monotonic() - t0) * 1000))
        yield {"type": "done", "query_id": qid, "answered": False, "cited": [], "constitution": False,
               "latency_ms": int((time.monotonic() - t0) * 1000)}
        return

    if db.llm_calls_last_24h() >= config.DAILY_LLM_LIMIT:
        yield {"type": "error", "code": "daily_limit", "message": error_text("daily_limit", lang)}
        return

    sources = [source_card(n, h) for n, h in enumerate(hits, 1)]
    yield {"type": "sources", "sources": sources, "search_query": search_q if search_q != question else None}

    messages = [*({"role": m["role"], "content": m["content"][:2000]} for m in history),
                {"role": "user", "content": prompts.user_message(hits, question, lang)}]
    usage = llm.Usage()
    full, buffer, answered = [], "", True
    marker = prompts.NO_INFO_MARKER
    try:
        async for piece in llm.stream_answer(prompts.system_prompt(lang), messages, usage):
            if buffer is not None:  # ждём первые символы, чтобы поймать маркер «нет информации»
                buffer += piece
                stripped = buffer.lstrip()
                if stripped.startswith(marker):
                    answered = False
                    break
                if len(stripped) < len(marker) and marker.startswith(stripped):
                    continue
                piece, buffer = buffer, None
            full.append(piece)
            yield {"type": "delta", "text": piece}
        if buffer and answered:  # ответ короче маркера
            full.append(buffer)
            yield {"type": "delta", "text": buffer}
    except llm.LLMError as e:
        db.log_query(**record, answered=0, error=e.code, latency_ms=int((time.monotonic() - t0) * 1000))
        yield {"type": "error", "code": e.code, "message": error_text(e.code, lang)}
        return

    if usage.refused and not full:
        yield {"type": "delta", "text": error_text("refusal", lang)}
        answered = False
    if not answered:
        yield {"type": "replace", "text": prompts.NO_INFO_TEXT[lang]}

    text = "".join(full)
    if answered and "📜" in text:
        fixed = fix_constitution_lines(text)
        if fixed != text:
            text = fixed
            yield {"type": "replace", "text": text, "keep_sources": True}
    cited = sorted({int(n) for n in CITE_RE.findall(text) if 1 <= int(n) <= len(sources)}) if answered else []
    # «Опирается на Конституцию» — только если модель сама поставила строку 📜 со ссылкой на статью
    constitution = answered and "📜" in text and any(sources[n - 1]["is_constitution"] for n in cited)
    latency = int((time.monotonic() - t0) * 1000)
    qid = db.log_query(**record, answered=int(answered), latency_ms=latency, model=usage.model,
                       tokens_in=usage.input_tokens, tokens_out=usage.output_tokens)
    yield {"type": "done", "query_id": qid, "answered": answered, "cited": cited,
           "constitution": constitution, "latency_ms": latency, "model": usage.model}


async def answer_text(question: str, **kw) -> dict:
    """Нестриминговый вариант (для Telegram и тестов): собирает весь ответ."""
    text, result = [], {"sources": [], "answered": False, "cited": [], "error": None}
    async for ev in answer(question, **kw):
        if ev["type"] == "delta":
            text.append(ev["text"])
        elif ev["type"] == "replace":
            text = [ev["text"]]
        elif ev["type"] == "sources":
            result["sources"] = ev["sources"]
        elif ev["type"] == "done":
            result.update({k: ev[k] for k in ("query_id", "answered", "cited", "constitution")})
        elif ev["type"] == "error":
            result["error"] = ev["message"]
    result["text"] = "".join(text)
    return result
