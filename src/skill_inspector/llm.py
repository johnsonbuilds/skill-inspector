from __future__ import annotations

import json
import math
import re
import urllib.error
import urllib.request
from collections import Counter
from typing import Any

from .hermes import HermesModelConfig
from .models import Asset, AssetType, Classification


SYSTEM_PROMPT = """You are an Agent Asset Auditor.

Classify the following asset into exactly one category:

1. Knowledge
2. Workflow
3. Executable Skill
4. Preference
5. Reference Material
6. Unknown

Definitions:

Knowledge:
Facts, strategies, lessons learned, guidance.

Workflow:
Repeatable process or methodology.

Executable Skill:
Can directly perform a task with clear inputs and outputs.

Preference:
User-specific behavior or style preference.

Reference Material:
External information stored for future use.

Unknown:
Use only when classification confidence is low.

Return JSON only with this schema:
{
  "type": "Knowledge | Workflow | Executable Skill | Preference | Reference Material | Unknown",
  "confidence": 0.0,
  "reason": "Short explanation for the classification."
}"""


class LLMClassifier:
    def __init__(self, config: HermesModelConfig) -> None:
        self.config = config

    def classify(self, asset: Asset) -> Classification:
        prompt = f"Asset name: {asset.name}\nPath: {asset.id}\nContent:\n{asset.content[:12000]}"
        text = self._chat(prompt)
        data = self._json(text)
        asset_type = AssetType(data.get("type", "Unknown")) if data.get("type") in {t.value for t in AssetType} else AssetType.UNKNOWN
        return Classification(asset_type, max(0.0, min(1.0, float(data.get("confidence", 0)))), str(data.get("reason", ""))[:500])

    def _chat(self, prompt: str) -> str:
        provider = self.config.provider
        if provider == "anthropic":
            return self._anthropic(prompt)
        if provider == "ollama":
            return self._ollama(prompt)
        return self._openai_compatible(prompt)

    def _openai_compatible(self, prompt: str) -> str:
        base = (self.config.base_url or ("https://openrouter.ai/api/v1" if self.config.provider == "openrouter" else "https://api.openai.com/v1")).rstrip("/")
        payload = {"model": self.config.model, "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}], "temperature": 0, "response_format": {"type": "json_object"}}
        data = self._post(f"{base}/chat/completions", payload, auth=True)
        return data["choices"][0]["message"]["content"]

    def _anthropic(self, prompt: str) -> str:
        payload = {"model": self.config.model, "max_tokens": 800, "temperature": 0, "system": SYSTEM_PROMPT, "messages": [{"role": "user", "content": prompt}]}
        data = self._post((self.config.base_url or "https://api.anthropic.com/v1").rstrip("/") + "/messages", payload, auth=True, extra={"anthropic-version": "2023-06-01"})
        return data["content"][0]["text"]

    def _ollama(self, prompt: str) -> str:
        payload = {"model": self.config.model, "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}], "stream": False, "format": "json"}
        data = self._post((self.config.base_url or "http://localhost:11434").rstrip("/") + "/api/chat", payload, auth=False)
        return data["message"]["content"]

    def _post(self, url: str, payload: dict[str, Any], auth: bool, extra: dict[str, str] | None = None) -> dict[str, Any]:
        headers = {"Content-Type": "application/json", **(extra or {})}
        if auth and self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
            if self.config.provider == "anthropic":
                headers["x-api-key"] = self.config.api_key
                headers.pop("Authorization", None)
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())

    def _json(self, text: str) -> dict[str, Any]:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.S)
            if not match:
                raise
            return json.loads(match.group(0))


class EmbeddingClient:
    def __init__(self, config: HermesModelConfig) -> None:
        self.config = config

    def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            return self._remote(texts)
        except Exception:
            return [self._local_embedding(t) for t in texts]

    def _remote(self, texts: list[str]) -> list[list[float]]:
        if self.config.provider == "ollama":
            base = (self.config.base_url or "http://localhost:11434").rstrip("/")
            return [self._ollama_embed(base, t) for t in texts]
        base = (self.config.base_url or ("https://openrouter.ai/api/v1" if self.config.provider == "openrouter" else "https://api.openai.com/v1")).rstrip("/")
        model = "text-embedding-3-small" if self.config.provider in {"openai", "openrouter", ""} else self.config.model
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        req = urllib.request.Request(f"{base}/embeddings", data=json.dumps({"model": model, "input": texts}).encode(), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode())
        return [item["embedding"] for item in data["data"]]

    def _ollama_embed(self, base: str, text: str) -> list[float]:
        req = urllib.request.Request(f"{base}/api/embeddings", data=json.dumps({"model": self.config.model, "prompt": text}).encode(), headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())["embedding"]

    def _local_embedding(self, text: str, dims: int = 384) -> list[float]:
        vec = [0.0] * dims
        for token, count in Counter(re.findall(r"[a-zA-Z0-9_]+", text.lower())).items():
            vec[hash(token) % dims] += float(count)
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]
