from __future__ import annotations

import json
import logging
import re
from typing import Any

from openai import OpenAI

from .hermes import HermesModelConfig
from .models import (
    AssetType,
    Category,
    PackageAsset,
    PackageClassification,
    SkillPackage,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an Agent Asset Auditor.

You will receive N skill packages. For EACH package, classify its SKILL.md into exactly one category:

- Knowledge: Facts, strategies, lessons learned, guidance
- Workflow: Repeatable process or methodology
- Executable Skill: Can directly perform a task with clear inputs and outputs
- Preference: User-specific behavior or style preference
- Reference Material: External information stored for future use
- Unknown: Classification confidence is low

Return your answer as a JSON array of objects, one per package, in this exact format:
[
  {
    "package_index": 0,
    "type": "Knowledge",
    "confidence": 0.95,
    "reason": "Brief explanation"
  }
]

The "package_index" must match the 0-based position of the package in the input.
Return ONLY the JSON array, no other text."""


class PackageClassifier:
    """Classifies SkillPackages based on SKILL.md content only."""

    def __init__(self, config: HermesModelConfig) -> None:
        self.config = config

    def classify(self, package: SkillPackage) -> PackageClassification:
        results = self.classify_batch([package])
        return results[package.id]

    def classify_packages(self, categories: list[Category]) -> dict[str, PackageClassification]:
        """Classify all packages across all categories in batch."""
        all_packages: list[SkillPackage] = []
        for cat in categories:
            all_packages.extend(cat.packages)
        return self.classify_batch(all_packages)

    def classify_batch(self, packages: list[SkillPackage]) -> dict[str, PackageClassification]:
        """Classify multiple packages in a single API call for efficiency."""
        BATCH_SIZE = 5
        results: dict[str, PackageClassification] = {}

        for batch_start in range(0, len(packages), BATCH_SIZE):
            batch = packages[batch_start:batch_start + BATCH_SIZE]
            success_count = 0

            for attempt in range(2):  # retry once on failure
                if success_count == len(batch):
                    break

                entries = []
                for i, pkg in enumerate(batch):
                    entries.append(
                        f"--- PACKAGE {i} ---\n"
                        f"Name: {pkg.name}\n"
                        f"Category: {pkg.category}\n"
                        f"SKILL.md Content:\n{pkg.skill_md.content[:8000]}"
                    )
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
                    match = re.search(r"\[.*\]", text, re.S)
                    if match:
                        try:
                            parsed = json.loads(match.group(0))
                        except json.JSONDecodeError:
                            pass

                if isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, dict) and "package_index" in item:
                            idx = item["package_index"]
                            if 0 <= idx < len(batch):
                                pkg = batch[idx]
                                type_str = item.get("type", "Unknown")
                                asset_type = (
                                    AssetType(type_str)
                                    if type_str in {t.value for t in AssetType}
                                    else AssetType.UNKNOWN
                                )
                                results[pkg.id] = PackageClassification(
                                    package=pkg,
                                    type=asset_type,
                                    confidence=max(0.0, min(1.0, float(item.get("confidence", 0)))),
                                    reason=str(item.get("reason", ""))[:500],
                                )
                                success_count += 1

            # For remaining unclassified packages, classify individually with retry
            for pkg in batch:
                if pkg.id not in results:
                    classified = False
                    for _attempt in range(2):
                        try:
                            results[pkg.id] = self._fallback_classify(pkg)
                            classified = True
                            break
                        except Exception as e:
                            logger.error("Fallback classify attempt %d failed for package %s: %s", _attempt + 1, pkg.id, e)
                            continue
                    if not classified:
                        logger.warning("Package %s (%s) classification failed after retries, defaulting to UNKNOWN", pkg.id, pkg.name)
                        results[pkg.id] = PackageClassification(
                            package=pkg,
                            type=AssetType.UNKNOWN,
                            confidence=0.0,
                            reason="Classification failed after retries",
                        )

        return results

    def _fallback_classify(self, package: SkillPackage) -> PackageClassification:
        prompt = (
            f"Package name: {package.name}\n"
            f"Category: {package.category}\n"
            f"SKILL.md Content:\n{package.skill_md.content[:12000]}"
        )
        text = self._chat(prompt)
        data = self._json(text)
        type_str = data.get("type", "Unknown")
        asset_type = (
            AssetType(type_str)
            if type_str in {t.value for t in AssetType}
            else AssetType.UNKNOWN
        )
        return PackageClassification(
            package=package,
            type=asset_type,
            confidence=max(0.0, min(1.0, float(data.get("confidence", 0)))),
            reason=str(data.get("reason", ""))[:500],
        )

    def _chat(self, prompt: str) -> str:
        provider = self.config.provider
        if provider == "anthropic":
            return self._anthropic(prompt)
        if provider == "ollama":
            return self._ollama(prompt)
        return self._openai_compatible(prompt)

    def _openai_compatible(self, prompt: str) -> str:
        base = (
            self.config.base_url
            or ("https://openrouter.ai/api/v1" if self.config.provider == "openrouter" else "https://api.openai.com/v1")
        ).rstrip("/")
        if base.endswith("/chat/completions"):
            base = base.rsplit("/chat/completions", 1)[0]
        client = OpenAI(base_url=base, api_key=self.config.api_key or "not-needed", timeout=600.0)
        resp = client.chat.completions.create(
            model=self.config.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        return resp.choices[0].message.content

    def _anthropic(self, prompt: str) -> str:
        base = (self.config.base_url or "https://api.anthropic.com/v1").rstrip("/")
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
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
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
