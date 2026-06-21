from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .models import Category, PackageClassification, SkillPackage


class PackageHealth(Enum):
    HEALTHY = "Healthy"
    WARNING = "Warning"
    AT_RISK = "At Risk"
    CRITICAL = "Critical"


@dataclass
class PackageHealthResult:
    """Health score and details for a single package."""
    package_id: str
    category: str
    overall: int  # 0-100
    structure_score: int  # 0-25
    maintainability_score: int  # 0-25
    reusability_score: int  # 0-25
    duplication_score: int  # 0-25
    archetype: str
    risk_factors: list[str] = field(default_factory=list)
    positive_factors: list[str] = field(default_factory=list)

    @property
    def health_level(self) -> PackageHealth:
        if self.overall >= 80:
            return PackageHealth.HEALTHY
        if self.overall >= 60:
            return PackageHealth.WARNING
        if self.overall >= 40:
            return PackageHealth.AT_RISK
        return PackageHealth.CRITICAL


def score_package(
    pkg: SkillPackage,
    classification: PackageClassification | None,
) -> PackageHealthResult:
    """Compute health score for a single package (0-100).

    Four dimensions, each 0-25:
      Structure: clarity of purpose, good organization
      Maintainability: complexity penalties
      Reusability: executable/workflow ratio
      Duplication: asset overlap signals
    """
    structure = _score_structure(pkg, classification)
    maintainability = _score_maintainability(pkg)
    reusability = _score_reusability(pkg, classification)
    duplication = _score_duplication(pkg)

    overall = structure + maintainability + reusability + duplication

    archetype_name = "Unknown"
    if classification:
        from .archetypes import classify_archetype
        archetype_name = classify_archetype(pkg, classification).value

    risk_factors: list[str] = []
    positive_factors: list[str] = []

    if pkg.complexity_score > 20:
        risk_factors.append(f"High complexity ({pkg.complexity_score})")
    if pkg.templates_count > 20:
        risk_factors.append(f"Template bloat ({pkg.templates_count} templates)")
    if pkg.references_count > 20:
        risk_factors.append(f"Reference bloat ({pkg.references_count} references)")
    if pkg.scripts_count > 10:
        risk_factors.append(f"Script bloat ({pkg.scripts_count} scripts)")
    if overall >= 80:
        positive_factors.append("Clear purpose and reasonable complexity")
    if overall >= 70 and pkg.scripts_count >= 1:
        positive_factors.append("Has executable procedures")
    if overall >= 70 and pkg.total_asset_count > 1:
        positive_factors.append("Good supporting assets")

    return PackageHealthResult(
        package_id=pkg.id,
        category=pkg.category,
        overall=overall,
        structure_score=structure,
        maintainability_score=maintainability,
        reusability_score=reusability,
        duplication_score=duplication,
        archetype=archetype_name,
        risk_factors=risk_factors,
        positive_factors=positive_factors,
    )


def _score_structure(pkg: SkillPackage, classification: PackageClassification | None) -> int:
    """Structure: 0-25. Measures clear purpose and good organization."""
    score = 25  # start full

    # Penalize monolithic packages
    if pkg.complexity_score > 50:
        score -= 10
    elif pkg.complexity_score > 20:
        score -= 5

    # Reward clear classification
    if classification and classification.type.value in ("Executable Skill", "Workflow"):
        score = min(25, score + 2)  # bonus capped

    # Penalize excessive templates (hard to maintain structure)
    if pkg.templates_count > 20:
        score -= 8
    elif pkg.templates_count > 10:
        score -= 4

    # Penalize excessive references
    if pkg.references_count > 20:
        score -= 6
    elif pkg.references_count > 10:
        score -= 3

    # Penalize excessive scripts
    if pkg.scripts_count > 10:
        score -= 4

    return max(0, score)


def _score_maintainability(pkg: SkillPackage) -> int:
    """Maintainability: 0-25. Penalizes oversized packages."""
    score = 25

    # Complexity penalty
    cs = pkg.complexity_score
    if cs > 100:
        score -= 15
    elif cs > 50:
        score -= 10
    elif cs > 20:
        score -= 5
    elif cs > 10:
        score -= 2

    # Total asset count penalty
    total = pkg.total_asset_count
    if total > 50:
        score -= 5
    elif total > 20:
        score -= 3
    elif total > 10:
        score -= 1

    return max(0, score)


def _score_reusability(pkg: SkillPackage, classification: PackageClassification | None) -> int:
    """Reusability: 0-25. Rewards executable/workflow packages."""
    score = 15  # base score

    if classification:
        ct = classification.type.value
        if ct == "Executable Skill":
            score += 10
        elif ct == "Workflow":
            score += 7
        elif ct == "Knowledge":
            score += 3
        elif ct == "Reference Material":
            score += 1

    # Bonus for having supporting assets that aid reuse
    if pkg.templates_count >= 1:
        score += 1
    if pkg.scripts_count >= 1:
        score += 1
    if pkg.references_count >= 1:
        score += 1

    return min(25, score)


def _score_duplication(pkg: SkillPackage) -> int:
    """Duplication: 0-25. Penalizes asset overlap signals.

    Since we don't have cross-package comparison here, we use structural
    heuristics: excessive homogeneous asset types suggest potential duplication.
    """
    score = 25

    # Penalize having too many of one asset type (suggests copy-paste)
    max_type = max(pkg.references_count, pkg.templates_count, pkg.scripts_count, pkg.assets_count)
    if max_type > 30:
        score -= 8
    elif max_type > 15:
        score -= 4
    elif max_type > 5:
        score -= 1

    return max(0, score)
