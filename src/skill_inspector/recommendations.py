from __future__ import annotations

from dataclasses import dataclass, field

from .models import Category, PackageClassification, SkillPackage
from .health_scoring import PackageHealthResult


@dataclass
class Recommendation:
    """A single actionable recommendation."""
    package_id: str | None  # None = library-wide
    category: str | None
    severity: str  # "High", "Medium", "Low"
    title: str
    description: str
    action: str  # concrete step to take


def generate_recommendations(
    categories: list[Category],
    classifications: dict[str, PackageClassification],
    health_results: dict[str, PackageHealthResult],
    risk_items: list,  # from risk_analysis
    dup_clusters_count: int,
) -> list[Recommendation]:
    """Generate actionable governance recommendations."""
    recs: list[Recommendation] = []
    total_packages = sum(c.package_count for c in categories)

    # Per-package recommendations
    for cat in categories:
        for pkg in cat.packages:
            hr = health_results.get(pkg.id)
            if not hr:
                continue

            # Split monolithic packages
            if pkg.complexity_score > 20:
                recs.append(Recommendation(
                    package_id=pkg.id,
                    category=cat.name,
                    severity=_complexity_severity_str(pkg.complexity_score),
                    title="Split monolithic package",
                    description=(
                        f"`{pkg.id}` has complexity {pkg.complexity_score} with "
                        f"{pkg.templates_count} templates, "
                        f"{pkg.references_count} references, "
                        f"{pkg.scripts_count} scripts."
                    ),
                    action="Consider splitting into smaller focused packages. "
                           "Move templates/references into a dedicated knowledge package. "
                           "Keep executable scripts in the core skill.",
                ))

            # Reference bloat → move to knowledge base
            if pkg.references_count > 20:
                recs.append(Recommendation(
                    package_id=pkg.id,
                    category=cat.name,
                    severity="High",
                    title="Move references into dedicated knowledge package",
                    description=f"`{pkg.id}` has {pkg.references_count} reference files.",
                    action="Extract reference materials into a separate knowledge-base package "
                           "to reduce the main skill's complexity.",
                ))

            # Template bloat → split
            if pkg.templates_count > 20:
                recs.append(Recommendation(
                    package_id=pkg.id,
                    category=cat.name,
                    severity="High",
                    title="Split template library into dedicated package",
                    description=f"`{pkg.id}` has {pkg.templates_count} template files.",
                    action="Create a dedicated template-library package and move templates there. "
                           "The main skill should reference the library rather than contain all templates.",
                ))

            # Script bloat → modularize
            if pkg.scripts_count > 10:
                recs.append(Recommendation(
                    package_id=pkg.id,
                    category=cat.name,
                    severity="Medium",
                    title="Modularize scripts",
                    description=f"`{pkg.id}` has {pkg.scripts_count} script files.",
                    action="Group related scripts into sub-packages or a scripts library. "
                           "Consider whether all scripts serve a single executable purpose.",
                ))

            # Low complexity + reference type → convert to executable
            classification = classifications.get(pkg.id)
            if pkg.complexity_score <= 2 and classification:
                if classification.type.value == "Reference Material":
                    recs.append(Recommendation(
                        package_id=pkg.id,
                        category=cat.name,
                        severity="Low",
                        title="Convert to executable skill",
                        description=f"`{pkg.id}` is classified as Reference Material with low complexity.",
                        action="Define clear inputs, outputs, and procedures to make this an executable skill.",
                    ))

    # Library-wide recommendations
    if dup_clusters_count > 0:
        recs.append(Recommendation(
            package_id=None,
            category=None,
            severity="High",
            title="Merge or archive duplicate packages",
            description=f"{dup_clusters_count} duplicate package cluster(s) detected.",
            action="Review duplicate clusters and merge overlapping packages. "
                   "Archive packages that are superseded by others.",
        ))

    # Category concentration
    if total_packages > 0:
        for cat in categories:
            ratio = cat.package_count / total_packages
            if ratio > 0.30:
                recs.append(Recommendation(
                    package_id=None,
                    category=cat.name,
                    severity="Medium",
                    title="Address category concentration",
                    description=f"`{cat.name}` contains {ratio:.0%} of all packages.",
                    action="Consider whether this category should be split into sub-categories "
                           "or whether some packages belong in a different category.",
                ))

    # General: add descriptions to categories without them
    for cat in categories:
        if not cat.description:
            recs.append(Recommendation(
                package_id=None,
                category=cat.name,
                severity="Low",
                title="Add category description",
                description=f"`{cat.name}` has no DESCRIPTION.md.",
                action="Create a DESCRIPTION.md explaining the category's purpose and scope.",
            ))

    return recs


def _complexity_severity_str(score: int) -> str:
    if score >= 100:
        return "Critical"
    if score >= 50:
        return "High"
    return "Medium"
