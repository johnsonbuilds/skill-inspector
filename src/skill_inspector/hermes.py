from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


from .models import Asset


@dataclass(frozen=True)
class HermesModelConfig:
    provider: str
    base_url: str | None
    model: str
    api_key: str | None


class HermesAdapter:
    """Reads Hermes configuration and skill assets without modifying them."""

    def __init__(self, data_dir: Path = Path("/opt/data")) -> None:
        self.data_dir = data_dir
        self.config_path = data_dir / "config.yaml"
        self.skills_dir = data_dir / "skills"

    def load_model_config(self) -> HermesModelConfig:
        raw = _simple_yaml(self.config_path.read_text(encoding="utf-8"))
        model = raw.get("model", {}) if isinstance(raw.get("model", {}), dict) else {}
        return HermesModelConfig(
            provider=self._expand(model.get("provider", "")).lower(),
            base_url=self._expand(model.get("base_url")) or None,
            model=self._expand(model.get("default", "")),
            api_key=self._expand(model.get("api_key")) or None,
        )

    # Files that are metadata/boilerplate, not actual skill content
    SKIP_FILES = frozenset({
        "description.md", "readme.md", "license", "license.txt",
        "port_notes.md", "changelog.md", "contributors.md",
        ".gitkeep", "description",
    })
    # Minimum content length to be considered a meaningful asset
    MIN_CONTENT_LENGTH = 80
    # Maximum content length to avoid bloating API payloads
    MAX_CONTENT_LENGTH = 20000

    def discover_assets(self) -> list[Asset]:
        if not self.skills_dir.exists():
            raise FileNotFoundError(f"Hermes skills directory not found: {self.skills_dir}")
        assets: list[Asset] = []
        for path in sorted(self.skills_dir.rglob("*")):
            if not path.is_file():
                continue
            stem_lower = path.stem.lower()
            suffix_lower = path.suffix.lower()
            # Only process SKILL.md files and content-bearing .md/.txt files
            if stem_lower in self.SKIP_FILES:
                continue
            if path.name.lower() != "skill.md" and suffix_lower not in {".md", ".txt", ".yaml", ".yml"}:
                continue
            content = path.read_text(encoding="utf-8", errors="replace")
            if not content.strip() or len(content) < self.MIN_CONTENT_LENGTH:
                continue
            if len(content) > self.MAX_CONTENT_LENGTH:
                continue
            rel = path.relative_to(self.skills_dir)
            name = path.parent.name if path.name.lower() == "skill.md" else path.stem
            assets.append(Asset(id=str(rel), name=name, path=path, content=content, metadata=self._metadata(content)))
        return assets

    def _expand(self, value: Any) -> str:
        if value is None:
            return ""
        return os.path.expandvars(str(value)).strip()

    def _metadata(self, content: str) -> dict[str, str]:
        if not content.startswith("---"):
            return {}
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.S)
        if not match:
            return {}
        data = _simple_yaml(match.group(1))
        return {str(k): str(v) for k, v in data.items() if not isinstance(v, dict)}


def _simple_yaml(text: str) -> dict[str, Any]:
    """Tiny YAML subset parser for Hermes config/front matter key-value maps."""
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"\'')
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if value == "":
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = value
    return root
