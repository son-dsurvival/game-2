"""Shared persistent model-call gateway for every campaign runtime component.

The gateway is the only provider-facing layer. It journals every attempt (with
prompts but never API keys), optionally reuses prior successful identical calls,
and supports both OpenAI-compatible endpoints and local Ollama chat.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from dataclasses import dataclass
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


_JOURNAL_LOCK = threading.Lock()
# A runtime holds an OS lease for its root. Worker threads share that operation's
# immutable model scope; independent campaign roots remain isolated.
_SCOPES: ContextVar[dict[str, dict[str, Any]]] = ContextVar('model_scopes', default={})


@contextmanager
def model_scope(root: Path, metadata: dict[str, Any], transport: Callable[[dict[str, Any]], str] | None = None) -> Iterator[None]:
    key = str(root.resolve())
    previous = _SCOPES.get().get(key, {})
    scope: dict[str, Any] = {'metadata': metadata, 'transport': transport or previous.get('transport'), 'calls': []}
    token = _SCOPES.set({**_SCOPES.get(), key: scope})
    try:
        yield
    except Exception:
        gateway = ModelGateway(root)
        for cache_key in scope['calls']:
            gateway._append({'status': 'invalidated', 'cache_key': cache_key})
        raise
    finally:
        _SCOPES.reset(token)


@dataclass(frozen=True)
class ModelCallResult:
    content: str
    call_id: str
    cache_key: str
    reused: bool
    provider: str
    model: str


class ModelGateway:
    """Provider adapter with append-only call history and exact-response reuse."""

    def __init__(
        self,
        repo_root: str | Path = ".",
        *,
        journal_path: str | Path | None = None,
        transport: Callable[[dict[str, Any]], str] | None = None,
    ):
        self.root = Path(repo_root).resolve()
        try:
            from dotenv import load_dotenv
            load_dotenv(dotenv_path=self.root / ".env")
        except ImportError:
            pass
        self.journal_path = (
            Path(journal_path).resolve()
            if journal_path is not None
            else self.root / "brain" / "state" / "model_calls.jsonl"
        )
        self.transport = transport
        self._successes = self._load_successes()

    def complete(
        self,
        *,
        stage: str,
        messages: list[dict[str, str]],
        model: str | None = None,
        provider: str = "deepseek",
        temperature: float = 0,
        json_mode: bool = False,
        timeout: float = 120,
        max_retries: int = 2,
        request_id: str | None = None,
        reuse: bool = True,
        metadata: dict[str, Any] | None = None,
        ollama_host: str | None = None,
    ) -> ModelCallResult:
        """Run or reuse one exact model request.

        ``stage`` identifies the internal caller (for example
        ``specialist.rules`` or ``evidence.selector``). ``request_id`` links
        attempts to a turn/admin operation but is deliberately not part of the
        reuse key, so an identical deterministic request can be replayed after
        restart.
        """
        if not stage.strip():
            raise ValueError("Model calls require a stage")
        normalized_messages = self._messages(messages)
        provider = provider.casefold().strip()
        model = model or self._default_model(provider)
        scope = _SCOPES.get().get(str(self.root), {})
        metadata = {**scope.get('metadata', {}), **(metadata or {})}
        request = {
            "provider": provider,
            "model": model,
            "temperature": temperature,
            "json_mode": json_mode,
            "messages": normalized_messages,
            "ollama_host": ollama_host.rstrip("/") if isinstance(ollama_host, str) else None,
        }
        request['endpoint'] = (ollama_host or os.getenv('OLLAMA_HOST', 'http://127.0.0.1:11434')) if provider == 'ollama' else (os.getenv('DEEPSEEK_BASE_URL') or os.getenv('BASE_URL') or 'https://api.deepseek.com')
        cache_key = self._hash({'request': request, 'stage': stage, 'scope': metadata})
        self._successes = self._load_successes()
        prior = self._successes.get(cache_key)
        if reuse and prior:
            self._append({'status': 'reused', 'cache_key': cache_key, 'stage': stage, 'request_id': request_id, 'metadata': metadata, 'reused_call_id': prior['call_id']})
            scope.get('calls', []).append(cache_key)
            return ModelCallResult(
                content=str(prior["response"]),
                call_id=str(prior["call_id"]),
                cache_key=cache_key,
                reused=True,
                provider=provider,
                model=model,
            )

        call_id = f"model-{uuid.uuid4().hex}"
        base_record = {
            "call_id": call_id,
            "cache_key": cache_key,
            "stage": stage,
            "request_id": request_id,
            "request": request,
            "metadata": metadata or {},
        }
        try:
            content = self._invoke({**request, "timeout": timeout, "max_retries": max_retries})
            if not isinstance(content, str) or not content:
                raise RuntimeError("Model provider returned empty content")
        except Exception as exc:
            self._append({**base_record, "status": "failed", "error_type": type(exc).__name__, "error": str(exc)})
            raise

        valid = True
        if json_mode:
            try:
                json.loads(content)
            except json.JSONDecodeError:
                valid = False
        record = {**base_record, 'status': 'succeeded' if valid else 'invalid_response', 'response': content}
        self._append(record)
        if valid:
            self._successes[cache_key] = record
            scope.get('calls', []).append(cache_key)
        return ModelCallResult(
            content=content,
            call_id=call_id,
            cache_key=cache_key,
            reused=False,
            provider=provider,
            model=model,
        )

    def _invoke(self, request: dict[str, Any]) -> str:
        transport = self.transport or _SCOPES.get().get(str(self.root), {}).get('transport')
        if transport is not None:
            return transport(request)
        if request["provider"] in {"deepseek", "openai", "openai_compatible"}:
            return self._openai_compatible(request)
        if request["provider"] == "ollama":
            return self._ollama(request)
        raise ValueError(f"Unsupported model provider: {request['provider']}")

    @staticmethod
    def _messages(messages: Any) -> list[dict[str, str]]:
        if not isinstance(messages, list) or not messages:
            raise ValueError("Model calls require at least one message")
        normalized = []
        for message in messages:
            if not isinstance(message, dict):
                raise ValueError("Each model message must be an object")
            role = message.get("role")
            content = message.get("content")
            if role not in {"system", "user", "assistant"} or not isinstance(content, str):
                raise ValueError("Model messages require a supported role and string content")
            normalized.append({"role": role, "content": content})
        return normalized

    def _openai_compatible(self, request: dict[str, Any]) -> str:
        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("API_KEY")
        if not api_key:
            raise RuntimeError("Model calls require DEEPSEEK_API_KEY or API_KEY")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("Model calls require the 'openai' package") from exc
        base_url = os.getenv("DEEPSEEK_BASE_URL") or os.getenv("BASE_URL") or "https://api.deepseek.com"
        client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=request["timeout"],
            max_retries=request["max_retries"],
        )
        kwargs: dict[str, Any] = {
            "model": request["model"],
            "temperature": request["temperature"],
            "messages": request["messages"],
        }
        if request["json_mode"]:
            kwargs["response_format"] = {"type": "json_object"}
        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    @staticmethod
    def _ollama(request: dict[str, Any]) -> str:
        host = request.get("ollama_host") or os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
        body: dict[str, Any] = {
            "model": request["model"],
            "messages": request["messages"],
            "stream": False,
            "options": {"temperature": request["temperature"]},
        }
        if request["json_mode"]:
            body["format"] = "json"
        raw = json.dumps(body).encode("utf-8")
        http_request = Request(f"{host}/api/chat", data=raw, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(http_request, timeout=request["timeout"]) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Ollama request failed: {exc}") from exc
        content = payload.get("message", {}).get("content") if isinstance(payload, dict) else None
        return content if isinstance(content, str) else ""

    @staticmethod
    def _default_model(provider: str) -> str:
        return os.getenv("OLLAMA_MODEL", "llama3") if provider == "ollama" else os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    @staticmethod
    def _hash(value: dict[str, Any]) -> str:
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _load_successes(self) -> dict[str, dict[str, Any]]:
        successes: dict[str, dict[str, Any]] = {}
        try:
            with self.journal_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(record, dict) and record.get('status') == 'invalidated':
                        successes.pop(str(record.get('cache_key')), None)
                    if (
                        isinstance(record, dict)
                        and record.get("status") == "succeeded"
                        and isinstance(record.get("cache_key"), str)
                        and isinstance(record.get("response"), str)
                    ):
                        successes[record["cache_key"]] = record
        except FileNotFoundError:
            pass
        return successes

    def _append(self, record: dict[str, Any]) -> None:
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        # Credentials can also occur in provider error text or supplied metadata.
        def scrub(value: Any) -> Any:
            if isinstance(value, dict):
                return {key: ('[REDACTED]' if any(word in key.casefold() for word in ('api_key', 'authorization', 'password', 'secret')) else scrub(item)) for key, item in value.items()}
            if isinstance(value, list):
                return [scrub(item) for item in value]
            if isinstance(value, str):
                for key in ('DEEPSEEK_API_KEY', 'API_KEY', 'OPENAI_API_KEY'):
                    token = os.getenv(key)
                    if token:
                        value = value.replace(token, '[REDACTED]')
            return value
        line = json.dumps(scrub(record), ensure_ascii=False, sort_keys=True) + "\n"
        with _JOURNAL_LOCK:
            with self.journal_path.open("a", encoding="utf-8") as handle:
                handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())
