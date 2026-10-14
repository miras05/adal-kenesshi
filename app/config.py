"""Все настройки проекта читаются из переменных окружения (.env).
Секреты (ключи API, токены) в коде не хранятся."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, default))


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, default))


# --- LLM (Anthropic Claude) ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
# Haiku 5.5 — дёшево для разработки; на защите можно поставить claude-opus-5-5
LLM_MODEL = os.getenv("LLM_MODEL", "claude-haiku-5-5")
# Модель для служебных задач (переформулировка вопроса) — всегда дешёвая
LLM_FAST_MODEL = os.getenv("LLM_FAST_MODEL", "claude-haiku-5-5")
LLM_EFFORT = os.getenv("LLM_EFFORT", "low")  # low | medium | high
LLM_MAX_TOKENS = _int("LLM_MAX_TOKENS", 4000)

# --- RAG ---
DATA_DIR = ROOT / "data"
CORPUS_DIR = DATA_DIR / "corpus"
INDEX_DIR = DATA_DIR / "index"
MODELS_DIR = DATA_DIR / "models"
EMBED_MODEL = os.getenv("EMBED_MODEL", "intfloat/multilingual-e5-large")
TOP_K = _int("TOP_K", 8)
# Ниже этого порога (косинусная близость e5) считаем, что в базе ответа нет
MIN_RELEVANCE = _float("MIN_RELEVANCE", 0.80)

# --- Сервер / безопасность ---
DB_PATH = Path(os.getenv("DB_PATH", DATA_DIR / "app.db"))
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
RATE_LIMIT_PER_MIN = _int("RATE_LIMIT_PER_MIN", 20)
# Защита бюджета: не больше N вопросов к LLM за сутки на весь сайт
DAILY_LLM_LIMIT = _int("DAILY_LLM_LIMIT", 300)
MAX_QUESTION_LEN = _int("MAX_QUESTION_LEN", 1000)
ALLOWED_ORIGINS = [o for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o]

# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
