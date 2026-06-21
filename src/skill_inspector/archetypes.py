from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .models import Category, PackageClassification, SkillPackage


class PackageArchetype(str, Enum):
    TOOL_SKILL = "Tool Skill"
    WORKFLOW_SKILL = "Workflow Skill"
    KNOWLEDGE_BASE = "Knowledge Base"
    TEMPLATE_LIBRARY = "Template Library"
    RESEARCH_LIBRARY = "Research Library"
    HYBRID_PACKAGE = "Hybrid Package"


def classify_archetype(
    pkg: SkillPackage,
    classification: PackageClassification | None,
) -> PackageArchetype:
    """Classify a package into an archetype based on SKILL.md type + asset composition.

    This is separate from the LLM-based type classification.
    Based purely on structural signals.
    """
    ref_c = pkg.references_count
    tmpl_c = pkg.templates_count
    scrpt_c = pkg.scripts_count
    asset_c = pkg.assets_count
    complexity = pkg.complexity_score

    # Determine LLM type if available
    llm_type = classification.type.value if classification else "Unknown"

    # Template Library: lots of templates, moderate complexity
    if tmpl_c > 10 and complexity > 20:
        return PackageArchetype.TEMPLATE_LIBRARY

    # Research Library: lots of references, no/low scripts
    if ref_c > 10 and scrpt_c == 0:
        return PackageArchetype.RESEARCH_LIBRARY

    # Knowledge Base: significant references or assets, low complexity relative to refs
    if ref_c > 5 and complexity <= 30:
        return PackageArchetype.KNOWLEDGE_BASE

    # Workflow Skill: has scripts + templates, moderate complexity
    if scrpt_c >= 2 and tmpl_c >= 1:
        return PackageArchetype.WORKFLOW_SKILL

    # Tool Skill: has scripts or small focused assets, low complexity
    if scrpt_c >= 1 or (tmpl_c >= 1 and complexity <= 10):
        return PackageArchetype.TOOL_SKILL

    # Hybrid: has multiple asset types suggesting broad scope
    type_counts = sum(1 for c in [ref_c, tmpl_c, scrpt_c, asset_c] if c > 0)
    if type_counts >= 3:
        return PackageArchetype.HYBRID_PACKAGE

    # Default: single-purpose skill
    return PackageArchetype.TOOL_SKILL
