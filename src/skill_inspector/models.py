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
