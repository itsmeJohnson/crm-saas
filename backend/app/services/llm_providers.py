"""Pluggable LLM provider layer — the bottom of the AI Platform.

Mirrors the email/whatsapp/sms provider pattern: a Mock provider that works in
dev/CI with zero credentials, plus real transports for OpenAI, Azure OpenAI,
Anthropic, Google Gemini, Ollama and any OpenAI-compatible custom endpoint —
all spoken over plain httpx (no vendor SDKs, no hardcoded provider). A call
never raises for a business failure: it returns an LLMResult with
status='failed' so the gateway can log it and walk the fallback chain.

Messages use the neutral [{role: system|user|assistant, content: str}] shape;
each provider adapts it to its own wire format. `stream()` yields text chunks
(SSE parsing per provider); providers without streaming fall back to a single
chunk from `complete()`.
"""
from __future__ import annotations
import json
import logging
import time
from dataclasses import dataclass

logger = logging.getLogger("app.ai.providers")

PROVIDER_KEYS = ("mock", "openai", "azure_openai", "anthropic", "gemini", "ollama", "custom")

# Default USD cost per 1K tokens (input, output) — overridable per provider config.
DEFAULT_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o": (0.0025, 0.01), "gpt-4o-mini": (0.00015, 0.0006), "gpt-4.1": (0.002, 0.008),
    "o3-mini": (0.0011, 0.0044),
    "claude-sonnet-4-5": (0.003, 0.015), "claude-haiku-4-5": (0.0008, 0.004),
    "claude-opus-4-1": (0.015, 0.075),
    "gemini-2.0-flash": (0.0001, 0.0004), "gemini-1.5-pro": (0.00125, 0.005),
    "mock-ai": (0.0, 0.0),
}


@dataclass
class LLMResult:
    status: str = "success"            # success|failed
    text: str = ""
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    error: str | None = None
    latency_ms: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


def _approx_tokens(text: str) -> int:
    """Cheap token estimate (~4 chars/token) for providers that don't report usage."""
    return max(1, len(text) // 4)


class BaseLLMProvider:
    name = "base"

    def __init__(self, *, api_key: str | None = None, base_url: str | None = None,
                 deployment: str | None = None, api_version: str | None = None):
        self.api_key = api_key
        self.base_url = (base_url or "").rstrip("/")
        self.deployment = deployment
        self.api_version = api_version

    async def complete(self, *, messages: list[dict], model: str, temperature: float = 0.7,
                       max_tokens: int = 1024) -> LLMResult:  # pragma: no cover - abstract
        raise NotImplementedError

    async def stream(self, *, messages: list[dict], model: str, temperature: float = 0.7,
                     max_tokens: int = 1024):
        """Default streaming: one chunk from complete() (providers override with real SSE)."""
        res = await self.complete(messages=messages, model=model, temperature=temperature,
                                  max_tokens=max_tokens)
        if res.status == "success" and res.text:
            yield res.text

    async def _post_json(self, url: str, *, headers: dict, payload: dict, timeout: float = 60.0):
        import httpx
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.post(url, headers=headers, json=payload)


class MockLLMProvider(BaseLLMProvider):
    """Deterministic dev/CI provider — echoes a bounded completion, reports
    approximate token usage, streams word by word. Model name 'mock-ai'."""
    name = "mock"

    async def complete(self, *, messages, model, temperature=0.7, max_tokens=1024) -> LLMResult:
        started = time.monotonic()
        last_user = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        prompt_text = " ".join(m.get("content") or "" for m in messages)
        text = f"[AI mock] {str(last_user)[:200]}"
        return LLMResult(status="success", text=text, model=model or "mock-ai",
                         prompt_tokens=_approx_tokens(prompt_text), completion_tokens=_approx_tokens(text),
                         latency_ms=int((time.monotonic() - started) * 1000))

    async def stream(self, *, messages, model, temperature=0.7, max_tokens=1024):
        res = await self.complete(messages=messages, model=model, temperature=temperature,
                                  max_tokens=max_tokens)
        for word in res.text.split(" "):
            yield word + " "


class OpenAICompatibleProvider(BaseLLMProvider):
    """OpenAI chat-completions dialect — used by OpenAI itself, Ollama
    (/v1/chat/completions) and any custom OpenAI-compatible endpoint."""
    name = "openai"
    default_base = "https://api.openai.com/v1"

    def _url(self) -> str:
        return f"{self.base_url or self.default_base}/chat/completions"

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    async def complete(self, *, messages, model, temperature=0.7, max_tokens=1024) -> LLMResult:
        started = time.monotonic()
        try:
            r = await self._post_json(self._url(), headers=self._headers(), payload={
                "model": model, "messages": messages, "temperature": temperature,
                "max_tokens": max_tokens})
            latency = int((time.monotonic() - started) * 1000)
            if r.status_code >= 400:
                return LLMResult(status="failed", model=model, latency_ms=latency,
                                 error=f"HTTP {r.status_code}: {r.text[:300]}")
            body = r.json()
            usage = body.get("usage") or {}
            text = ((body.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
            return LLMResult(status="success", text=text, model=body.get("model") or model,
                             prompt_tokens=int(usage.get("prompt_tokens") or _approx_tokens(str(messages))),
                             completion_tokens=int(usage.get("completion_tokens") or _approx_tokens(text)),
                             latency_ms=latency)
        except Exception as e:
            return LLMResult(status="failed", model=model, error=str(e)[:300],
                             latency_ms=int((time.monotonic() - started) * 1000))

    async def stream(self, *, messages, model, temperature=0.7, max_tokens=1024):
        import httpx
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream("POST", self._url(), headers=self._headers(), json={
                        "model": model, "messages": messages, "temperature": temperature,
                        "max_tokens": max_tokens, "stream": True}) as r:
                    if r.status_code >= 400:
                        return
                    async for line in r.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            delta = ((json.loads(data).get("choices") or [{}])[0]
                                     .get("delta") or {}).get("content")
                            if delta:
                                yield delta
                        except Exception:
                            continue
        except Exception as e:
            logger.warning("OpenAI-compatible stream failed: %s", e)


class AzureOpenAIProvider(OpenAICompatibleProvider):
    """Azure dialect: deployment-scoped URL + api-key header."""
    name = "azure_openai"

    def _url(self) -> str:
        version = self.api_version or "2024-06-01"
        return (f"{self.base_url}/openai/deployments/{self.deployment}"
                f"/chat/completions?api-version={version}")

    def _headers(self) -> dict:
        return {"Content-Type": "application/json", "api-key": self.api_key or ""}


class OllamaProvider(OpenAICompatibleProvider):
    """Local Ollama — OpenAI-compatible /v1 endpoint, no API key, zero cost."""
    name = "ollama"
    default_base = "http://localhost:11434/v1"


class CustomProvider(OpenAICompatibleProvider):
    """Any OpenAI-compatible self-hosted / gateway endpoint (vLLM, LiteLLM, …)."""
    name = "custom"


class AnthropicProvider(BaseLLMProvider):
    name = "anthropic"
    default_base = "https://api.anthropic.com/v1"

    def _split(self, messages: list[dict]) -> tuple[str | None, list[dict]]:
        system = "\n".join(m["content"] for m in messages if m.get("role") == "system") or None
        rest = [m for m in messages if m.get("role") != "system"]
        return system, rest

    async def complete(self, *, messages, model, temperature=0.7, max_tokens=1024) -> LLMResult:
        started = time.monotonic()
        system, rest = self._split(messages)
        payload = {"model": model, "max_tokens": max_tokens, "temperature": temperature,
                   "messages": rest}
        if system:
            payload["system"] = system
        try:
            r = await self._post_json(f"{self.base_url or self.default_base}/messages",
                                      headers={"x-api-key": self.api_key or "",
                                               "anthropic-version": "2023-06-01",
                                               "Content-Type": "application/json"},
                                      payload=payload)
            latency = int((time.monotonic() - started) * 1000)
            if r.status_code >= 400:
                return LLMResult(status="failed", model=model, latency_ms=latency,
                                 error=f"HTTP {r.status_code}: {r.text[:300]}")
            body = r.json()
            text = "".join(b.get("text") or "" for b in (body.get("content") or [])
                           if b.get("type") == "text")
            usage = body.get("usage") or {}
            return LLMResult(status="success", text=text, model=body.get("model") or model,
                             prompt_tokens=int(usage.get("input_tokens") or 0),
                             completion_tokens=int(usage.get("output_tokens") or _approx_tokens(text)),
                             latency_ms=latency)
        except Exception as e:
            return LLMResult(status="failed", model=model, error=str(e)[:300],
                             latency_ms=int((time.monotonic() - started) * 1000))

    async def stream(self, *, messages, model, temperature=0.7, max_tokens=1024):
        import httpx
        system, rest = self._split(messages)
        payload = {"model": model, "max_tokens": max_tokens, "temperature": temperature,
                   "messages": rest, "stream": True}
        if system:
            payload["system"] = system
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream("POST", f"{self.base_url or self.default_base}/messages",
                                         headers={"x-api-key": self.api_key or "",
                                                  "anthropic-version": "2023-06-01",
                                                  "Content-Type": "application/json"},
                                         json=payload) as r:
                    if r.status_code >= 400:
                        return
                    async for line in r.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        try:
                            ev = json.loads(line[5:].strip())
                            if ev.get("type") == "content_block_delta":
                                delta = (ev.get("delta") or {}).get("text")
                                if delta:
                                    yield delta
                        except Exception:
                            continue
        except Exception as e:
            logger.warning("Anthropic stream failed: %s", e)


class GeminiProvider(BaseLLMProvider):
    name = "gemini"
    default_base = "https://generativelanguage.googleapis.com/v1beta"

    def _payload(self, messages: list[dict], temperature: float, max_tokens: int) -> dict:
        system = "\n".join(m["content"] for m in messages if m.get("role") == "system")
        contents = [{"role": "model" if m["role"] == "assistant" else "user",
                     "parts": [{"text": m["content"]}]}
                    for m in messages if m.get("role") != "system"]
        payload = {"contents": contents,
                   "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens}}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        return payload

    async def complete(self, *, messages, model, temperature=0.7, max_tokens=1024) -> LLMResult:
        started = time.monotonic()
        url = (f"{self.base_url or self.default_base}/models/{model}:generateContent"
               f"?key={self.api_key or ''}")
        try:
            r = await self._post_json(url, headers={"Content-Type": "application/json"},
                                      payload=self._payload(messages, temperature, max_tokens))
            latency = int((time.monotonic() - started) * 1000)
            if r.status_code >= 400:
                return LLMResult(status="failed", model=model, latency_ms=latency,
                                 error=f"HTTP {r.status_code}: {r.text[:300]}")
            body = r.json()
            cands = body.get("candidates") or [{}]
            text = "".join(p.get("text") or "" for p in
                           ((cands[0].get("content") or {}).get("parts") or []))
            usage = body.get("usageMetadata") or {}
            return LLMResult(status="success", text=text, model=model,
                             prompt_tokens=int(usage.get("promptTokenCount") or 0),
                             completion_tokens=int(usage.get("candidatesTokenCount") or _approx_tokens(text)),
                             latency_ms=latency)
        except Exception as e:
            return LLMResult(status="failed", model=model, error=str(e)[:300],
                             latency_ms=int((time.monotonic() - started) * 1000))


def get_llm_provider(key: str, *, api_key: str | None = None, base_url: str | None = None,
                     deployment: str | None = None, api_version: str | None = None) -> BaseLLMProvider:
    """Factory — never hardcodes a provider; unknown keys fall back to Mock."""
    cls = {"mock": MockLLMProvider, "openai": OpenAICompatibleProvider,
           "azure_openai": AzureOpenAIProvider, "anthropic": AnthropicProvider,
           "gemini": GeminiProvider, "ollama": OllamaProvider,
           "custom": CustomProvider}.get(key, MockLLMProvider)
    return cls(api_key=api_key, base_url=base_url, deployment=deployment, api_version=api_version)
