"""Тесты HTTP API (без загрузки модели и без вызовов LLM)."""
import json

import pytest
from fastapi.testclient import TestClient

from app import api, config, llm, service
from tests.test_core import FakeRetriever, fake_stream


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(service.db, "_conn", None)
    monkeypatch.setattr(service, "_retriever", FakeRetriever(0.9))
    monkeypatch.setattr(api, "limiter", api.RateLimiter(per_minute=100))
    return TestClient(api.app)  # без контекстного менеджера: lifespan (загрузка модели) не запускается


def sse(resp):
    return [json.loads(line[5:]) for line in resp.text.splitlines() if line.startswith("data:")]


def test_security_headers(client):
    r = client.get("/api/concepts")
    assert r.status_code == 200
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-frame-options"] == "DENY"


def test_chat_stream(client, monkeypatch):
    monkeypatch.setattr(llm, "stream_answer", fake_stream("Ответ [1]"))
    r = client.post("/api/chat", json={"question": "Что в статье 3?", "lang": "ru"})
    assert r.headers["content-type"].startswith("text/event-stream")
    events = sse(r)
    assert events[0]["type"] == "sources"
    assert events[-1]["type"] == "done" and events[-1]["cited"] == [1]


def test_chat_validation(client):
    assert client.post("/api/chat", json={"question": "x" * 5000}).status_code == 422
    assert client.post("/api/chat", json={"question": "ok", "lang": "en"}).status_code == 422


def test_rate_limit(client, monkeypatch):
    monkeypatch.setattr(api, "limiter", api.RateLimiter(per_minute=1))
    monkeypatch.setattr(llm, "stream_answer", fake_stream("ok"))
    assert client.post("/api/chat", json={"question": "1"}).status_code == 200
    assert client.post("/api/chat", json={"question": "2"}).status_code == 429


def test_feedback(client, monkeypatch):
    monkeypatch.setattr(llm, "stream_answer", fake_stream("Ответ [1]"))
    qid = sse(client.post("/api/chat", json={"question": "вопрос"}))[-1]["query_id"]
    assert client.post("/api/feedback", json={"query_id": qid, "value": 1}).json() == {"ok": True}
    assert client.post("/api/feedback", json={"query_id": 999999, "value": 1}).status_code == 404


def test_stats_requires_token(client, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_TOKEN", "secret")
    assert client.get("/api/stats").status_code == 401
    assert client.get("/api/stats", headers={"X-Admin-Token": "wrong"}).status_code == 401
    assert client.get("/api/stats", headers={"X-Admin-Token": "secret"}).json()["total_queries"] == 0


def test_quiz_hides_answers_and_scores_on_server(client):
    qs = client.get("/api/quiz?lang=kk").json()
    assert len(qs) == 7 and all("answer" not in q for q in qs)
    answers = {q["id"]: api.QUIZ_BY_ID[q["id"]]["answer"] for q in qs}
    res = client.post("/api/quiz/submit?lang=kk", json={"answers": answers, "nickname": "Тест<script>"}).json()
    assert res["score"] == res["total"] == 7
    assert client.get("/api/quiz/leaderboard").json()[0]["nickname"] == "Тестscript"


def test_quiz_bank_is_consistent():
    for q in api.QUIZ:
        for lang in ("ru", "kk"):
            assert len(q[lang]["options"]) == 4
            assert all(len(o) <= 100 for o in q[lang]["options"]), q["id"]  # лимит Telegram-викторины
        assert 0 <= q["answer"] < 4
