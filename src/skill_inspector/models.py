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
    assets: list[PackageAsset]  # all other files
    total_asset_count: int = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, "total_asset_count", 1 + len(self.assets))


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
