from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class AssetType(str, Enum):
    KNOWLEDGE = "Knowledge"
    WORKFLOW = "Workflow"
    EXECUTABLE_SKILL = "Executable Skill"
    PREFERENCE = "Preference"
    REFERENCE = "Reference Material"
    UNKNOWN = "Unknown"


@dataclass(frozen=True)
class Asset:
    id: str
    name: str
    path: Path
    content: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Classification:
    type: AssetType
    confidence: float
    reason: str


@dataclass(frozen=True)
class DuplicateCluster:
    assets: list[Asset]
    average_similarity: float


# --- Package-aware models (v0.1.5) ---


@dataclass(frozen=True)
class PackageAsset:
    """A single file within a skill package (SKILL.md, references, templates, etc.)."""
    name: str
    path: Path
    content: str


@dataclass(frozen=True)
class SkillPackage:
    """A skill folder: one SKILL.md + optional references/templates/scripts/assets."""
    id: str
    name: str
    path: Path
    category: str  # e.g. "creative", "github", or root-level like "dogfood"
    skill_md: PackageAsset  # the required SKILL.md
    references: list[PackageAsset] = field(default_factory=list)
    templates: list[PackageAsset] = field(default_factory=list)
    scripts: list[PackageAsset] = field(default_factory=list)
    assets: list[PackageAsset] = field(default_factory=list)
    total_asset_count: int = field(init=False)
    references_count: int = field(init=False)
    templates_count: int = field(init=False)
    scripts_count: int = field(init=False)
    assets_count: int = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, "references_count", len(self.references))
        object.__setattr__(self, "templates_count", len(self.templates))
        object.__setattr__(self, "scripts_count", len(self.scripts))
        object.__setattr__(self, "assets_count", len(self.assets))
        object.__setattr__(self, "total_asset_count",
                             1 + self.references_count + self.templates_count
                             + self.scripts_count + self.assets_count)

    @property
    def complexity_score(self) -> int:
        """Weighted complexity: refs*1 + templates*2 + scripts*3 + assets*1."""
        return (
            self.references_count
            + self.templates_count * 2
            + self.scripts_count * 3
            + self.assets_count
        )


@dataclass(frozen=True)
class Category:
    """A category folder under skills/ containing multiple SkillPackages."""
    id: str
    name: str
    description: str  # from DESCRIPTION.md if present, else ""
    packages: list[SkillPackage]
    package_count: int = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, "package_count", len(self.packages))


@dataclass(frozen=True)
class PackageClassification:
    """Classification result for a single SkillPackage (based on SKILL.md only)."""
    package: SkillPackage
    type: AssetType
    confidence: float
    reason: str


@dataclass(frozen=True)
class PackageDuplicateCluster:
    """Duplicate cluster of SkillPackages (compared by SKILL.md content only)."""
    packages: list[SkillPackage]
    average_similarity: float
