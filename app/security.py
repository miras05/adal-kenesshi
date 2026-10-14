"""Защита: валидация ввода, лимит запросов, обнаружение prompt-injection."""
import re
import time
from collections import defaultdict, deque

from app import config

CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
INJECTION_PATTERNS = re.compile(
    r"(ignore|forget|disregard)\s+(all\s+|the\s+|your\s+)?(previous|above|prior)?\s*(instructions|rules|prompt)"
    r"|system\s*prompt|jailbreak|developer\s+mode|you\s+are\s+now"
    r"|игнорируй|забудь\s+(все\s+)?(инструкции|правила)|системн\w+\s+промпт|теперь\s+ты"
    r"|нұсқаулықты\s+елеме",
    re.IGNORECASE,
)


class ValidationError(ValueError):
    pass


def clean_question(text: str) -> str:
    if not isinstance(text, str):
        raise ValidationError("empty")
    text = CONTROL_RE.sub("", text).strip()
    text = re.sub(r"\s{3,}", "  ", text)
    if not text:
        raise ValidationError("empty")
    if len(text) > config.MAX_QUESTION_LEN:
        raise ValidationError("too_long")
    return text


def looks_like_injection(text: str) -> bool:
    """Эвристика для журнала/аналитики. Основная защита — в системном промпте
    (документы и ввод пользователя помечены как данные, а не инструкции)."""
    return bool(INJECTION_PATTERNS.search(text))


class RateLimiter:
    """Скользящее окно: не больше N запросов в минуту с одного пользователя."""

    def __init__(self, per_minute: int = config.RATE_LIMIT_PER_MIN):
        self.per_minute = per_minute
        self.hits: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        q = self.hits[key]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= self.per_minute:
            return False
        q.append(now)
        return True
