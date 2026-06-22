from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter
from typing import Any

from openai import OpenAI

from .hermes import HermesModelConfig
from .models import Asset, AssetType, Classification

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an Agent Asset Auditor.

You will receive N assets. For EACH asset, return a JSON object with its classification.

Classify each asset into exactly one category:
- Knowledge: Facts, strategies, lessons learned, guidance
- Workflow: Repeatable process or methodology
- Executable Skill: Can directly perform a task with clear inputs and outputs
- Preference: User-specific behavior or style preference
- Reference Material: External information stored for future use
- Unknown: Classification confidence is low

Return your answer as a JSON array of objects, one per asset, in this exact format:
[
  {
    "asset_index": 0,
    "type": "Knowledge",
    "confidence": 0.95,
    "reason": "Brief explanation"
  },
  {
    "asset_index": 1,
    "type": "Workflow",
    "confidence": 0.8,
    "reason": "Brief explanation"
  }
]

The "asset_index" must match the 0-based position of the asset in the input (0 for first, 1 for second, etc.).
Return ONLY the JSON array, no other text."""


class LLMClassifier:
    def __init__(self, config: HermesModelConfig) -> None:
        self.config = config

    def classify(self, asset: Asset) -> Classification:
        results = self.classify_batch([asset])
        return results[asset.id]

    def classify_batch(self, assets: list[Asset]) -> dict[str, Classification]:
        """Classify multiple assets in a single API call for efficiency."""
        BATCH_SIZE = 5
        results: dict[str, Classification] = {}
        for batch_start in range(0, len(assets), BATCH_SIZE):
            batch = assets[batch_start:batch_start + BATCH_SIZE]
            success_count = 0
            for attempt in range(2):  # retry once on failure
                if success_count == len(batch):
                    break
                entries = []
                for i, asset in enumerate(batch):
                    entries.append(f"--- ASSET {i} ---\nName: {asset.name}\nPath: {asset.id}\nContent:\n{asset.content[:6000]}")
                user_content = "\n\n".join(entries)
                try:
                    text = self._chat(user_content)
                except Exception as e:
                    logger.error("Chat classification attempt %d failed: %s", attempt + 1, e)
                    continue
                # Try to parse as JSON array
                parsed = []
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    # Try to extract JSON array from response
                    match = re.search(r"\[.*\]", text, re.S)
                    if match:
                        try:
                            parsed = json.loads(match.group(0))
                        except json.JSONDecodeError:
                            pass

                if isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, dict) and "asset_index" in item:
                            idx = item["asset_index"]
                            if 0 <= idx < len(batch):
                                asset = batch[idx]
                                asset_type = AssetType(item.get("type", "Unknown")) if item.get("type", "") in {t.value for t in AssetType} else AssetType.UNKNOWN
                                results[asset.id] = Classification(
                                    asset_type,
                                    max(0.0, min(1.0, float(item.get("confidence", 0)))),
                                    str(item.get("reason", ""))[:500]
                                )
                                success_count += 1
            # For remaining unclassified assets, classify individually with retry
            for asset in batch:
                if asset.id not in results:
                    classified = False
                    for _attempt in range(2):
                        try:
                            results[asset.id] = self._fallback_classify(asset)
                            classified = True
                            break
                        except Exception as e:
                            logger.error("Fallback classify attempt %d failed for asset %s: %s", _attempt + 1, asset.id, e)
                            continue
                    if not classified:
                        logger.warning("Asset %s (%s) classification failed after retries, defaulting to UNKNOWN", asset.id, asset.name)
                        results[asset.id] = Classification(AssetType.UNKNOWN, 0.0, "Classification failed after retries")
        return results

    def _fallback_classify(self, asset: Asset) -> Classification:
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
        # Ensure base ends with /v1 (OpenAI-compatible convention), not /v1/chat/completions
        if base.endswith("/chat/completions"):
            base = base.rsplit("/chat/completions", 1)[0]
        client = OpenAI(base_url=base, api_key=self.config.api_key or "not-needed", timeout=600.0)
        resp = client.chat.completions.create(
            model=self.config.model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"},
        )
        return resp.choices[0].message.content

    def _anthropic(self, prompt: str) -> str:
        base = (self.config.base_url or "https://api.anthropic.com/v1").rstrip("/")
        # Anthropic's /v1/messages endpoint is compatible with OpenAI SDK format
        client = OpenAI(base_url=base, api_key=self.config.api_key or "not-needed", timeout=600.0)
        resp = client.chat.completions.create(
            model=self.config.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_tokens=800,
            temperature=0,
        )
        return resp.choices[0].message.content

    def _ollama(self, prompt: str) -> str:
        base = (self.config.base_url or "http://localhost:11434").rstrip("/")
        client = OpenAI(base_url=f"{base}/api", api_key="ollama", timeout=600.0)
        resp = client.chat.completions.create(
            model=self.config.model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
            stream=False,
            format="json",
        )
        return resp.choices[0].message.content

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
        except Exception as e:
            logger.warning("Remote embedding failed (%s), falling back to local hash", e)
            return [self._local_embedding(t) for t in texts]

    def _remote(self, texts: list[str]) -> list[list[float]]:
        if self.config.provider == "ollama":
            base = (self.config.base_url or "http://localhost:11434").rstrip("/")
            client = OpenAI(base_url=f"{base}/api", api_key="ollama", timeout=600.0)
            return [self._ollama_embed(client, t) for t in texts]
        
        base = (self.config.base_url or ("https://openrouter.ai/api/v1" if self.config.provider == "openrouter" else "https://api.openai.com/v1")).rstrip("/")
        # Strip trailing path segments if base_url already contains them
        for suffix in ("/chat/completions", "/embeddings"):
            if base.endswith(suffix):
                base = base.rsplit(suffix, 1)[0]
                break
        
        model = "text-embedding-3-small" if self.config.provider in {"openai", "openrouter", ""} else self.config.model
        client = OpenAI(base_url=base, api_key=self.config.api_key or "not-needed", timeout=600.0)
        resp = client.embeddings.create(model=model, input=texts)
        return [item.embedding for item in resp.data]

    def _ollama_embed(self, client: OpenAI, text: str) -> list[float]:
        resp = client.embeddings.create(model=self.config.model, input=text)
        return resp.data[0].embedding

    def _local_embedding(self, text: str, dims: int = 384) -> list[float]:
        vec = [0.0] * dims
        for token, count in Counter(re.findall(r"[a-zA-Z0-9_]+", text.lower())).items():
            vec[hash(token) % dims] += float(count)
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]
