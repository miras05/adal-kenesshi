"""HTTP API (FastAPI) + раздача веб-интерфейса.

Запуск:  uvicorn app.api:app --reload
"""
import asyncio
import hmac
import json
import logging
import random
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import config, db, service
from app.security import RateLimiter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("api")

WEB_DIR = config.ROOT / "web"
QUIZ = json.loads((config.DATA_DIR / "quiz.json").read_text(encoding="utf-8"))
CONCEPTS = json.loads((config.DATA_DIR / "concepts.json").read_text(encoding="utf-8"))
QUIZ_BY_ID = {q["id"]: q for q in QUIZ}
SOURCES = json.loads((config.DATA_DIR / "sources.json").read_text(encoding="utf-8"))
QUIZ_SIZE = 7

limiter = RateLimiter()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Прогреваем индекс и модель эмбеддингов заранее, чтобы первый ответ был быстрым
    await asyncio.to_thread(service.get_retriever)
    await asyncio.to_thread(service.get_retriever().embed_query, "прогрев")
    db.conn()
    log.info("Готово: %d фрагментов в индексе, модель %s", len(service.get_retriever().chunks), config.LLM_MODEL)
    yield


app = FastAPI(title="Adal Kenesshi API", version="1.0", lifespan=lifespan)
if config.ALLOWED_ORIGINS:
    app.add_middleware(CORSMiddleware, allow_origins=config.ALLOWED_ORIGINS,
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

CSP = ("default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; "
       "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; "
       "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["Content-Security-Policy"] = CSP
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Permissions-Policy"] = "microphone=(self), camera=(), geolocation=()"
    return resp


def client_id(request: Request) -> str:
    """IP посетителя. За прокси (ngrok, Hugging Face) берём ПОСЛЕДНИЙ адрес из
    X-Forwarded-For — его дописал сам прокси; первые адреса клиент может подделать."""
    fwd = [x.strip() for x in request.headers.get("x-forwarded-for", "").split(",") if x.strip()]
    return fwd[-1] if fwd else (request.client.host if request.client else "unknown")


# ---------- Модели запросов ----------

class Msg(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=6000)


class ChatIn(BaseModel):
    question: str = Field(max_length=4000)
    history: list[Msg] = Field(default_factory=list, max_length=20)
    lang: Literal["ru", "kk"] | None = None
    mode: Literal["ask", "situation", "factcheck"] = "ask"


class FeedbackIn(BaseModel):
    query_id: int
    value: Literal[1, -1]


class QuizIn(BaseModel):
    answers: dict[str, int] = Field(max_length=QUIZ_SIZE)
    nickname: str = Field(default="", max_length=24)


# ---------- Чат ----------

def is_internal(request: Request) -> bool:
    """Запрос от нашего Telegram-бота (общий секрет), а не от браузера."""
    token = request.headers.get("x-internal-token", "")
    return bool(config.ADMIN_TOKEN) and hmac.compare_digest(token, config.ADMIN_TOKEN)


@app.post("/api/chat")
async def chat(body: ChatIn, request: Request):
    channel, user = "web", client_id(request)
    if is_internal(request):  # бот передаёт ID пользователя Telegram (в БД — только хэш)
        channel, user = "telegram", "tg:" + request.headers.get("x-user-id", "unknown")[:32]
    if not limiter.allow(user):
        msg = service.error_text("rate_limit", body.lang or "ru")
        return JSONResponse({"error": msg}, status_code=429)

    async def events():
        try:
            async for ev in service.answer(body.question, [m.model_dump() for m in body.history],
                                           body.lang, channel=channel, user=user, mode=body.mode):
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
        except Exception:  # непредвиденная ошибка — не роняем поток, сообщаем пользователю
            log.exception("chat failed")
            err = {"type": "error", "code": "api", "message": service.error_text("api", body.lang or "ru")}
            yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/feedback")
async def feedback(body: FeedbackIn):
    if not db.save_feedback(body.query_id, body.value):
        raise HTTPException(404, "query not found")
    return {"ok": True}


# ---------- Справочник ценностей ----------

@app.get("/api/concepts")
async def concepts():
    return CONCEPTS


# ---------- Квиз (геймификация) ----------

@app.get("/api/quiz")
async def quiz(lang: Literal["ru", "kk"] = "ru"):
    """Случайные вопросы без правильных ответов — проверка идёт на сервере."""
    qs = random.sample(QUIZ, k=min(QUIZ_SIZE, len(QUIZ)))
    return [{"id": q["id"], "question": q[lang]["question"], "options": q[lang]["options"]} for q in qs]


@app.post("/api/quiz/submit")
async def quiz_submit(body: QuizIn, request: Request, lang: Literal["ru", "kk"] = "ru"):
    results, score = [], 0
    for qid, choice in body.answers.items():
        q = QUIZ_BY_ID.get(qid)
        if not q:
            continue
        ok = choice == q["answer"]
        score += ok
        results.append({"id": qid, "correct": ok, "answer": q["answer"],
                        "explanation": q[lang]["explanation"], "source": q["source"]})
    nickname = "".join(ch for ch in body.nickname if ch.isalnum() or ch in " _-").strip()
    db.save_quiz(db.user_hash(client_id(request)), nickname, score, len(results))
    return {"score": score, "total": len(results), "results": results}


@app.get("/api/quiz/leaderboard")
async def leaderboard():
    return db.leaderboard()


# ---------- Служебное ----------

@app.get("/api/health")
async def health():
    chunks = service.get_retriever().chunks
    return {"status": "ok", "chunks": len(chunks), "documents": len({c["doc_id"] for c in chunks}),
            "model": config.LLM_MODEL}


@app.get("/api/stats")
async def stats(x_admin_token: str = Header(default="")):
    if not config.ADMIN_TOKEN or not hmac.compare_digest(x_admin_token, config.ADMIN_TOKEN):
        raise HTTPException(401, "unauthorized")
    return db.stats()


@app.get("/api/sources")
async def sources():
    """Список документов в базе знаний (для прозрачности)."""
    order = {s["id"]: i for i, s in enumerate(SOURCES)}  # порядок как в реестре: Конституция, Указ, Послания…
    seen = {}
    for c in sorted(service.get_retriever().chunks, key=lambda c: order.get(c["doc_id"], 999)):
        key = (c["doc_id"], c["lang"])
        if key not in seen:
            seen[key] = {"id": c["doc_id"], "lang": c["lang"], "title": c["title"], "date": c["date"],
                         "type": c["type"], "url": c["url"]}
    return list(seen.values())


@app.get("/")
async def index_page():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/admin")
async def admin_page():
    return FileResponse(WEB_DIR / "admin.html")


app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
