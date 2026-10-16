"""SQLite: журнал запросов (для аналитики), оценки ответов и результаты квиза.

Персональные данные не храним: вместо IP / Telegram-ID пишем солёный хэш
(требование Закона РК «О персональных данных и их защите»).
"""
import hashlib
import sqlite3
import threading
import time

from app import config

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS queries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          REAL NOT NULL,
    user_hash   TEXT,
    channel     TEXT,          -- web | telegram
    lang        TEXT,
    question    TEXT,
    mode        TEXT,          -- ask | situation | factcheck
    answered    INTEGER,       -- 1 = ответ найден, 0 = «нет информации»
    top_score   REAL,          -- лучшая близость в поиске
    latency_ms  INTEGER,
    model       TEXT,
    tokens_in   INTEGER,
    tokens_out  INTEGER,
    error       TEXT
);
CREATE TABLE IF NOT EXISTS feedback (
    query_id    INTEGER PRIMARY KEY REFERENCES queries(id),
    value       INTEGER NOT NULL,   -- 1 👍, -1 👎
    ts          REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS quiz_results (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          REAL NOT NULL,
    user_hash   TEXT,
    nickname    TEXT,
    score       INTEGER,
    total       INTEGER
);
"""


def conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(SCHEMA)
        cols = {r[1] for r in _conn.execute("PRAGMA table_info(queries)")}
        if "mode" not in cols:  # миграция БД, созданной до появления режимов
            _conn.execute("ALTER TABLE queries ADD COLUMN mode TEXT")
            _conn.commit()
    return _conn


def user_hash(raw: str) -> str:
    salt = config.ADMIN_TOKEN or "adal-qogam"
    return hashlib.sha256(f"{salt}:{raw}".encode()).hexdigest()[:16]


def log_query(**fields) -> int:
    fields.setdefault("ts", time.time())
    cols = ", ".join(fields)
    marks = ", ".join("?" for _ in fields)
    with _lock:
        cur = conn().execute(f"INSERT INTO queries ({cols}) VALUES ({marks})", tuple(fields.values()))
        conn().commit()
        return cur.lastrowid


def llm_calls_last_24h() -> int:
    """Сколько ответов сгенерировала LLM за сутки (для дневного лимита бюджета)."""
    return conn().execute("SELECT COUNT(*) FROM queries WHERE ts > ? AND model IS NOT NULL",
                          (time.time() - 86400,)).fetchone()[0]


def save_feedback(query_id: int, value: int) -> bool:
    with _lock:
        if not conn().execute("SELECT 1 FROM queries WHERE id=?", (query_id,)).fetchone():
            return False
        conn().execute("INSERT OR REPLACE INTO feedback VALUES (?, ?, ?)", (query_id, value, time.time()))
        conn().commit()
        return True


def save_quiz(user: str, nickname: str, score: int, total: int) -> None:
    with _lock:
        conn().execute("INSERT INTO quiz_results (ts, user_hash, nickname, score, total) VALUES (?,?,?,?,?)",
                       (time.time(), user, nickname, score, total))
        conn().commit()


def leaderboard(limit: int = 10) -> list[dict]:
    rows = conn().execute(
        # одно имя — одна строка с лучшим результатом (даже если играли с разных устройств)
        "SELECT nickname, MAX(score) AS score, total FROM quiz_results "
        "WHERE nickname != '' GROUP BY lower(trim(nickname)) ORDER BY score DESC, MIN(ts) LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def stats() -> dict:
    c = conn()
    one = lambda sql: c.execute(sql).fetchone()[0]  # noqa: E731
    day_ago = time.time() - 86400
    return {
        "total_queries": one("SELECT COUNT(*) FROM queries"),
        "queries_24h": c.execute("SELECT COUNT(*) FROM queries WHERE ts > ?", (day_ago,)).fetchone()[0],
        "unique_users": one("SELECT COUNT(DISTINCT user_hash) FROM queries"),
        "answered_rate": one("SELECT ROUND(AVG(answered) * 100, 1) FROM queries WHERE error IS NULL"),
        "avg_latency_ms": one("SELECT CAST(AVG(latency_ms) AS INTEGER) FROM queries WHERE error IS NULL"),
        "errors": one("SELECT COUNT(*) FROM queries WHERE error IS NOT NULL"),
        "likes": one("SELECT COUNT(*) FROM feedback WHERE value = 1"),
        "dislikes": one("SELECT COUNT(*) FROM feedback WHERE value = -1"),
        "tokens_in": one("SELECT COALESCE(SUM(tokens_in), 0) FROM queries"),
        "tokens_out": one("SELECT COALESCE(SUM(tokens_out), 0) FROM queries"),
        "by_lang": [dict(r) for r in c.execute(
            "SELECT lang, COUNT(*) AS n FROM queries GROUP BY lang ORDER BY n DESC")],
        "by_channel": [dict(r) for r in c.execute(
            "SELECT channel, COUNT(*) AS n FROM queries GROUP BY channel ORDER BY n DESC")],
        "by_mode": [dict(r) for r in c.execute(
            "SELECT COALESCE(mode, 'ask') AS mode, COUNT(*) AS n FROM queries GROUP BY 1 ORDER BY n DESC")],
        "by_day": [dict(r) for r in c.execute(
            "SELECT date(ts, 'unixepoch', '+5 hours') AS day, COUNT(*) AS n, SUM(answered) AS answered "
            "FROM queries GROUP BY day ORDER BY day DESC LIMIT 14")],
        "top_questions": [dict(r) for r in c.execute(
            "SELECT question, COUNT(*) AS n FROM queries GROUP BY lower(question) ORDER BY n DESC LIMIT 10")],
        "unanswered": [dict(r) for r in c.execute(
            "SELECT question, datetime(ts, 'unixepoch', '+5 hours') AS at FROM queries "
            "WHERE answered = 0 AND error IS NULL ORDER BY ts DESC LIMIT 10")],
        "quiz_games": one("SELECT COUNT(*) FROM quiz_results"),
    }
