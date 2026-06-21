from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import Asset, Category, PackageAsset, SkillPackage


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


    # --- Package-aware discovery (v0.2.1) ---

    def discover_packages(self) -> list[Category]:
        """Discover skill packages organized by category.

        Returns a list of Category objects. Each category contains SkillPackages.
        Root-level skill folders (directly under skills/ with SKILL.md) are
        auto-detected — no hardcoded names.
        """
        if not self.skills_dir.exists():
            raise FileNotFoundError(f"Hermes skills directory not found: {self.skills_dir}")

        categories: list[Category] = []

        for entry in sorted(self.skills_dir.iterdir()):
            if not entry.is_dir():
                continue
            # Skip non-category directories
            if entry.name in ("index-cache",):
                continue

            # Check if this is a root-level skill folder (not a category):
            # A directory is root-level if skills/<folder>/SKILL.md exists directly.
            if (entry / "SKILL.md").exists():
                pkg = self._discover_single_package(entry, category_name="root")
                if pkg:
                    cat = Category(id=str(entry.relative_to(self.skills_dir)),
                                   name=entry.name, description="", packages=[pkg])
                    categories.append(cat)
                continue

            # Regular category: read DESCRIPTION.md if present
            desc_path = entry / "DESCRIPTION.md"
            description = ""
            if desc_path.exists():
                description = desc_path.read_text(encoding="utf-8", errors="replace").strip()

            # Discover skill packages in this category
            packages: list[SkillPackage] = []
            for skill_dir in sorted(entry.iterdir()):
                if not skill_dir.is_dir():
                    continue
                pkg = self._discover_single_package(skill_dir, category_name=entry.name)
                if pkg:
                    packages.append(pkg)

            if packages:
                categories.append(Category(
                    id=str(entry.relative_to(self.skills_dir)),
                    name=entry.name,
                    description=description,
                    packages=packages,
                ))

        return categories

    def _discover_single_package(self, skill_dir: Path, category_name: str) -> SkillPackage | None:
        """Discover a single skill package from a directory."""
        skill_md_path = skill_dir / "SKILL.md"
        if not skill_md_path.exists():
            return None

        skill_md_content = skill_md_path.read_text(encoding="utf-8", errors="replace")
        if not skill_md_content.strip():
            return None

        skill_md = PackageAsset(
            name="SKILL.md",
            path=skill_md_path,
            content=skill_md_content,
        )

        # Collect optional asset files, separated by directory type
        references: list[PackageAsset] = []
        templates: list[PackageAsset] = []
        scripts: list[PackageAsset] = []
        assets: list[PackageAsset] = []
        SKIP_ASSET_FILES = frozenset({"skill.md"})

        for subdir_name, target_list in [
            ("references", references),
            ("templates", templates),
            ("scripts", scripts),
        ]:
            subdir = skill_dir / subdir_name
            if subdir.is_dir():
                for fpath in sorted(subdir.rglob("*")):
                    if not fpath.is_file():
                        continue
                    if fpath.name.lower() in SKIP_ASSET_FILES:
                        continue
                    content = fpath.read_text(encoding="utf-8", errors="replace")
                    if content.strip():
                        target_list.append(PackageAsset(
                            name=fpath.name,
                            path=fpath,
                            content=content,
                        ))

        # Files outside recognized subdirectories go into "assets"
        for fpath in sorted(skill_dir.rglob("*")):
            if not fpath.is_file():
                continue
            if fpath.name.lower() in SKIP_ASSET_FILES:
                continue
            # Skip files already collected in known subdirectories
            try:
                rel = fpath.relative_to(skill_dir)
            except ValueError:
                continue
            if rel.parts and rel.parts[0] in ("references", "templates", "scripts", "assets"):
                continue
            content = fpath.read_text(encoding="utf-8", errors="replace")
            if content.strip():
                assets.append(PackageAsset(
                    name=fpath.name,
                    path=fpath,
                    content=content,
                ))

        return SkillPackage(
            id=str(skill_dir.relative_to(self.skills_dir)),
            name=skill_dir.name,
            path=skill_dir,
            category=category_name,
            skill_md=skill_md,
            references=references,
            templates=templates,
            scripts=scripts,
            assets=assets,
        )


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
