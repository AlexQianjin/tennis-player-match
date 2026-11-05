"""OpenAI-compatible chat client. Tests inject a fake via get_llm_client."""

from typing import Protocol

from tennis_match_api.config import Settings, get_settings

_client: "LLMClient | None" = None


class LLMClient(Protocol):
    async def complete(self, *, system: str, user: str) -> str: ...


class OpenAIChatClient:
    def __init__(self, settings: Settings) -> None:
        from openai import AsyncOpenAI

        key = settings.ai_model_api_key.get_secret_value() if settings.ai_model_api_key else ""
        kwargs: dict[str, object] = {
            "base_url": settings.ai_model_base_url,
            "api_key": key,
            "timeout": settings.llm_background_timeout_seconds,
            "max_retries": 0,
        }
        self._client = AsyncOpenAI(**kwargs)  # type: ignore[arg-type]
        self._model = settings.ai_model_name or ""
        self._json_mode = settings.llm_json_mode
        self._extra = dict(settings.llm_extra_body)

    async def complete(self, *, system: str, user: str) -> str:
        body: dict[str, object] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
        }
        if self._json_mode:
            body["response_format"] = {"type": "json_object"}
        if self._extra:
            body["extra_body"] = self._extra
        response = await self._client.chat.completions.create(**body)  # type: ignore[arg-type]
        content = response.choices[0].message.content or ""
        return content

    async def aclose(self) -> None:
        await self._client.close()


def get_llm_client() -> LLMClient | None:
    settings = get_settings()
    if not settings.llm_enabled:
        return None
    global _client
    if _client is None:
        _client = OpenAIChatClient(settings)
    return _client


async def close_llm_client() -> None:
    global _client
    current = _client
    _client = None
    if isinstance(current, OpenAIChatClient):
        await current.aclose()
