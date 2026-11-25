"""Local Ollama transport; no credentials or third-party packages required."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OllamaClient:
    def __init__(self, model, host="http://localhost:11434", timeout=120):
        self.model = model
        self.host = host.rstrip("/")
        self.timeout = timeout

    def complete(self, messages, *, schema=None):
        payload = {
            "model": self.model,
            "messages": messages,
            "format": schema if schema is not None else "json",
            "stream": False,
            "options": {"temperature": 0},
        }
        request = Request(
            self.host + "/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                result = json.load(response)
        except (URLError, TimeoutError, OSError) as exc:
            # Avoid recording response bodies, which may contain private context.
            detail = f"HTTP {exc.code}" if isinstance(exc, HTTPError) else type(exc).__name__
            raise RuntimeError(
                f"Ollama request failed ({detail}). Check Ollama is running and the model is installed."
            ) from exc
        if result.get("error"):
            raise RuntimeError("Ollama returned an error; check the installed model.")
        if result.get("done_reason") == "length":
            raise ValueError("Model output was truncated.")
        content = result.get("message", {}).get("content")
        if not isinstance(content, str):
            raise ValueError("Ollama response is missing message.content.")
        return {
            "content": content,
            "model": result.get("model", self.model),
            "usage": {k: result[k] for k in ("prompt_eval_count", "eval_count") if k in result},
        }
