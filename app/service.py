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

# Ссылки на источники: [3], [1, 2], а также [1, п. 2] / [1, ст. 12] — берём номера в начале скобок
CITE_GROUP_RE = re.compile(r"\[(\d{1,2}(?:\s*,\s*\d{1,2})*)(?:,[^\]\[]{0,80})?\]")
CITE_RE = re.compile(r"\[(\d{1,2})\]")


def cited_numbers(text: str) -> list[int]:
    return [int(n) for g in CITE_GROUP_RE.findall(text) for n in re.findall(r"\d+", g)]
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
        "doc_id": c["doc_id"],
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


VERDICT_RE = re.compile(r"\[\[VERDICT:(TRUE|FALSE|PARTIAL|UNKNOWN)\]\]\s*")
SENT_SPLIT_RE = re.compile(r"(?<=[.!?;:])\s+|\n+")
MODES = ("ask", "situation", "factcheck")


def _sentences(text: str) -> list[str]:
    return [x.strip() for x in SENT_SPLIT_RE.split(text) if len(x.strip()) > 20]


def best_quotes(answer_text: str, hits, cited: list[int]) -> dict[int, str]:
    """Evidence mode: для каждой ссылки [n] находим во фрагменте-источнике
    предложение, которое лучше всего совпадает по словам с утверждением ответа."""
    from app.rag.retriever import tokenize
    claims: dict[int, set] = {}
    for sent in _sentences(answer_text):
        for n in cited_numbers(sent):
            claims.setdefault(n, set()).update(tokenize(CITE_GROUP_RE.sub("", sent)))
    quotes = {}
    for n in cited:
        words = claims.get(n)
        cands = _sentences(hits[n - 1].chunk["text"])
        if not words or not cands:
            continue
        score = lambda c: len(words & set(tokenize(c))) / (len(set(tokenize(c))) ** 0.5 + 1)  # noqa: E731
        best = max(cands, key=score)
        if len(words & set(tokenize(best))) >= 2:
            quotes[n] = best[:400]
    return quotes


def quote_link(url: str, text: str) -> str:
    """Ссылка на первоисточник, которая открывается сразу на цитате (Text Fragments)."""
    words = text.split()[:8]
    return f"{url}#:~:text={quote(' '.join(words), safe='')}" if len(words) >= 3 else url


async def legal_terms(situation: str) -> str:
    try:
        terms = await llm.complete(prompts.LEGAL_QUERY_PROMPT.format(question=situation[:1000]))
    except llm.LLMError:
        return ""
    return terms.replace("\n", " ")[:600]


async def answer(question: str, history: list[dict] | None = None, lang: str | None = None,
                 channel: str = "web", user: str = "anon", mode: str = "ask") -> AsyncIterator[dict]:
    """Режимы: ask — вопрос; situation — «что делать в моей ситуации»;
    factcheck — проверка утверждения с вердиктом."""
    t0 = time.monotonic()
    mode = mode if mode in MODES else "ask"
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
    record = dict(user_hash=db.user_hash(user), channel=channel, lang=lang, question=question[:1000], mode=mode)
    if looks_like_injection(question):
        log.warning("Possible prompt injection from %s: %r", record["user_hash"], question[:200])

    search_q = await standalone_question(question, history)
    if mode == "situation":
        # Бытовое описание («намекают на деньги») → юридические термины закона,
        # иначе поиск не найдёт нужные статьи. Ищем по обоим вариантам сразу.
        terms = await legal_terms(search_q)
        if terms:
            search_q = f"{search_q}\n{terms}"
    # Поиск — CPU-задача (векторизация), выносим из event loop
    hits = await asyncio.to_thread(get_retriever().search, search_q, config.TOP_K, lang)
    top = max((h.dense for h in hits), default=0.0)
    record["top_score"] = round(top, 4)

    # Порог: если даже лучший фрагмент слабо похож на вопрос — не тратим LLM,
    # честно говорим, что подтверждённой информации нет (п. 4.9 Положения).
    if top < config.MIN_RELEVANCE:
        if mode == "factcheck":
            yield {"type": "verdict", "value": "UNKNOWN"}
            text = prompts.FACTCHECK_UNKNOWN_TEXT[lang]
        else:
            text = prompts.NO_INFO_TEXT[lang]
        yield {"type": "delta", "text": text}
        qid = db.log_query(**record, answered=0, latency_ms=int((time.monotonic() - t0) * 1000))
        yield {"type": "done", "query_id": qid, "answered": False, "cited": [], "constitution": False,
               "quotes": {}, "latency_ms": int((time.monotonic() - t0) * 1000)}
        return

    if db.llm_calls_last_24h() >= config.DAILY_LLM_LIMIT:
        yield {"type": "error", "code": "daily_limit", "message": error_text("daily_limit", lang)}
        return

    sources = [source_card(n, h) for n, h in enumerate(hits, 1)]
    shown_q = search_q.split("\n")[0]
    yield {"type": "sources", "sources": sources, "search_query": shown_q if shown_q != question else None}

    messages = [*({"role": m["role"], "content": m["content"][:2000]} for m in history),
                {"role": "user", "content": prompts.user_message(hits, question, lang, mode)}]
    usage = llm.Usage()
    full, head, answered, verdict = [], "", True, None
    marker = prompts.NO_INFO_MARKER
    try:
        async for piece in llm.stream_answer(prompts.system_prompt(lang, mode), messages, usage):
            if head is not None:  # первые символы: ловим служебные метки [NO_INFO] и [[VERDICT:…]]
                head += piece
                s = head.lstrip()
                if s.startswith(marker):
                    answered = False
                    break
                forming = (marker.startswith(s) or (s.startswith("[[") and "]]" not in s)) and len(s) < 40
                if forming:
                    continue
                m = VERDICT_RE.match(s)
                if m:
                    verdict = m.group(1)
                    yield {"type": "verdict", "value": verdict}
                    s = s[m.end():]
                piece, head = s, None
                if not piece:
                    continue
            if not full:
                piece = piece.lstrip()  # без пустых строк в начале ответа
                if not piece:
                    continue
            full.append(piece)
            yield {"type": "delta", "text": piece}
        if head and answered:  # ответ короче метки
            full.append(head)
            yield {"type": "delta", "text": head}
    except llm.LLMError as e:
        db.log_query(**record, answered=0, error=e.code, latency_ms=int((time.monotonic() - t0) * 1000))
        yield {"type": "error", "code": e.code, "message": error_text(e.code, lang)}
        return

    if usage.refused and not full:
        yield {"type": "delta", "text": error_text("refusal", lang)}
        answered = False
    if not answered:
        if mode == "factcheck":
            yield {"type": "verdict", "value": "UNKNOWN"}
            yield {"type": "replace", "text": prompts.FACTCHECK_UNKNOWN_TEXT[lang]}
        else:
            yield {"type": "replace", "text": prompts.NO_INFO_TEXT[lang]}
    elif mode == "factcheck" and verdict is None:
        yield {"type": "verdict", "value": "UNKNOWN"}

    text = "".join(full)
    if answered and "📜" in text:
        fixed = fix_constitution_lines(text)
        if fixed != text:
            text = fixed
            yield {"type": "replace", "text": text, "keep_sources": True}
    cited = sorted({n for n in cited_numbers(text) if 1 <= n <= len(sources)}) if answered else []
    # «Опирается на Конституцию» — только если модель сама поставила строку 📜 со ссылкой на статью
    constitution = answered and "📜" in text and any(sources[n - 1]["is_constitution"] for n in cited)
    quotes = best_quotes(text, hits, cited) if answered else {}
    latency = int((time.monotonic() - t0) * 1000)
    qid = db.log_query(**record, answered=int(answered), latency_ms=latency, model=usage.model,
                       tokens_in=usage.input_tokens, tokens_out=usage.output_tokens)
    yield {"type": "done", "query_id": qid, "answered": answered, "cited": cited,
           "constitution": constitution, "latency_ms": latency, "model": usage.model,
           "verdict": verdict, "quotes": {str(n): {"text": q, "link": quote_link(sources[n - 1]["url"], q)}
                                           for n, q in quotes.items()}}


async def answer_text(question: str, **kw) -> dict:
    """Нестриминговый вариант (для тестов и оценки качества): собирает весь ответ."""
    text, result = [], {"sources": [], "answered": False, "cited": [], "error": None, "verdict": None, "quotes": {}}
    async for ev in answer(question, **kw):
        if ev["type"] == "delta":
            text.append(ev["text"])
        elif ev["type"] == "replace":
            text = [ev["text"]]
        elif ev["type"] == "sources":
            result["sources"] = ev["sources"]
        elif ev["type"] == "done":
            result.update({k: ev[k] for k in ("query_id", "answered", "cited", "constitution", "quotes")})
        elif ev["type"] == "verdict":
            result["verdict"] = ev["value"]
        elif ev["type"] == "error":
            result["error"] = ev["message"]
    result["text"] = "".join(text)
    return result
