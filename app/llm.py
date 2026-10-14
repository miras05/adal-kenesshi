"""Обёртка над Anthropic Claude API: потоковая генерация ответа и служебные вызовы."""
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass

import anthropic

from app import config

log = logging.getLogger("llm")

_client: anthropic.AsyncAnthropic | None = None


def client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        if not config.ANTHROPIC_API_KEY:
            raise LLMError("no_key")
        _client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY, timeout=60.0, max_retries=2)
    return _client


class LLMError(Exception):
    """Ошибка LLM с кодом, который интерфейс переводит в понятное сообщение."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    refused: bool = False


def _request_args(model: str, system: str, messages: list[dict], max_tokens: int) -> dict:
    args = dict(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
        output_config={"effort": config.LLM_EFFORT},
    )
    # Для Opus включаем серверный fallback: если модель отклонит запрос
    # классификатором безопасности, API сам повторит его на резервной модели.
    if model.startswith("claude-opus"):
        args["betas"] = ["server-side-fallback-2026-07-01"]
        args["fallbacks"] = "default"
    return args


def _map_error(e: Exception) -> LLMError:
    if isinstance(e, anthropic.AuthenticationError):
        return LLMError("auth")
    if isinstance(e, anthropic.RateLimitError):
        return LLMError("rate_limit")
    if isinstance(e, anthropic.APIConnectionError):
        return LLMError("network")
    if isinstance(e, anthropic.APIStatusError):
        log.error("Anthropic API error %s: %s", e.status_code, e.message)
        return LLMError("credit" if "credit" in str(e.message).lower() else "api")
    return LLMError("api")


async def stream_answer(system: str, messages: list[dict], usage: Usage,
                        model: str | None = None) -> AsyncIterator[str]:
    """Стримит текст ответа по кусочкам. Статистику пишет в usage."""
    model = model or config.LLM_MODEL
    args = _request_args(model, system, messages, config.LLM_MAX_TOKENS)
    api = client().beta.messages if "betas" in args else client().messages
    try:
        async with api.stream(**args) as stream:
            async for text in stream.text_stream:
                yield text
            final = await stream.get_final_message()
    except anthropic.APIError as e:
        raise _map_error(e) from e
    usage.model = final.model
    usage.input_tokens = final.usage.input_tokens
    usage.output_tokens = final.usage.output_tokens
    usage.refused = final.stop_reason == "refusal"


async def complete(prompt: str, max_tokens: int = 1500, model: str | None = None) -> str:
    """Короткий служебный вызов без стриминга (переформулировка вопроса и т.п.)."""
    model = model or config.LLM_FAST_MODEL
    try:
        resp = await client().messages.create(
            model=model,
            max_tokens=max_tokens,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIError as e:
        raise _map_error(e) from e
    if resp.stop_reason == "refusal":
        return ""
    return "".join(b.text for b in resp.content if b.type == "text").strip()
