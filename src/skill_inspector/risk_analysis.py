from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .models import Category, PackageClassification, SkillPackage


class RiskSeverity(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


@dataclass
class RiskItem:
    """A single risk finding."""
    package_id: str
    category: str
    risk_type: str  # e.g. "monolithic", "ref_bloat", "template_bloat"
    severity: RiskSeverity
    detail: str  # e.g. "54 templates"


@dataclass
class RiskAnalysis:
    """Aggregated risk findings for the library."""
    risks: list[RiskItem] = field(default_factory=list)
    category_concentrations: list[RiskItem] = field(default_factory=list)

    @property
    def has_warnings(self) -> bool:
        """True if any risk has severity >= HIGH."""
        return any(
            r.severity in (RiskSeverity.HIGH, RiskSeverity.CRITICAL)
            for r in self.risks + self.category_concentrations
        )


# --- Thresholds ---

MONOLITHIC_THRESHOLD = 20
CATEGORY_CONCENTRATION_THRESHOLD = 0.30
REF_BLOAT_THRESHOLD = 20
TEMPLATE_BLOAT_THRESHOLD = 20
SCRIPT_BLOAT_THRESHOLD = 10


def detect_risks(
    categories: list[Category],
    classifications: dict[str, PackageClassification],
) -> RiskAnalysis:
    """Detect all governance risks in the library."""
    analysis = RiskAnalysis()
    total_packages = sum(c.package_count for c in categories)

    # Per-package risks
    for cat in categories:
        for pkg in cat.packages:
            # Monolithic packages
            if pkg.complexity_score > MONOLITHIC_THRESHOLD:
                severity = _complexity_severity(pkg.complexity_score)
                analysis.risks.append(RiskItem(
                    package_id=pkg.id,
                    category=cat.name,
                    risk_type="monolithic",
                    severity=severity,
                    detail=f"complexity: {pkg.complexity_score}",
                ))

            # Reference bloat
            if pkg.references_count > REF_BLOAT_THRESHOLD:
                analysis.risks.append(RiskItem(
                    package_id=pkg.id,
                    category=cat.name,
                    risk_type="ref_bloat",
                    severity=RiskSeverity.HIGH,
                    detail=f"{pkg.references_count} references",
                ))

            # Template bloat
            if pkg.templates_count > TEMPLATE_BLOAT_THRESHOLD:
                analysis.risks.append(RiskItem(
                    package_id=pkg.id,
                    category=cat.name,
                    risk_type="template_bloat",
                    severity=RiskSeverity.CRITICAL,
                    detail=f"{pkg.templates_count} templates",
                ))

            # Script bloat
            if pkg.scripts_count > SCRIPT_BLOAT_THRESHOLD:
                analysis.risks.append(RiskItem(
                    package_id=pkg.id,
                    category=cat.name,
                    risk_type="script_bloat",
                    severity=RiskSeverity.HIGH,
                    detail=f"{pkg.scripts_count} scripts",
                ))

    # Category concentration
    for cat in categories:
        if total_packages > 0:
            ratio = cat.package_count / total_packages
            if ratio > CATEGORY_CONCENTRATION_THRESHOLD:
                analysis.category_concentrations.append(RiskItem(
                    package_id=cat.name,
                    category=cat.name,
                    risk_type="category_concentration",
                    severity=RiskSeverity.HIGH,
                    detail=f"{ratio:.0%} of packages",
                ))

    return analysis


def _complexity_severity(score: int) -> RiskSeverity:
    if score >= 100:
        return RiskSeverity.CRITICAL
    if score >= 50:
        return RiskSeverity.HIGH
    return RiskSeverity.MEDIUM
