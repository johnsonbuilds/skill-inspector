from __future__ import annotations

from collections import Counter
from pathlib import Path

from .models import (
    AssetType,
    Category,
    PackageClassification,
    PackageDuplicateCluster,
    SkillPackage,
)
from .health_scoring import PackageHealthResult, score_package
from .risk_analysis import RiskAnalysis, detect_risks
from .recommendations import Recommendation, generate_recommendations
from .usage_analysis import UsageAnalysis, analyze_usage, load_usage_data


class PackageReportGenerator:
    """Generates a markdown report for package-aware analysis."""

    def generate(
        self,
        categories: list[Category],
        classifications: dict[str, PackageClassification],
        duplicate_clusters: list[PackageDuplicateCluster],
        output: Path,
    ) -> str:
        # Gather stats
        total_categories = len(categories)
        total_packages = sum(cat.package_count for cat in categories)
        total_assets = sum(
            pkg.total_asset_count for cat in categories for pkg in cat.packages
        )

        # Classification counts
        pkg_classes = list(classifications.values())
        type_counts = Counter(pc.type for pc in pkg_classes)

        # Asset distribution totals
        total_references = sum(pkg.references_count for cat in categories for pkg in cat.packages)
        total_templates = sum(pkg.templates_count for cat in categories for pkg in cat.packages)
        total_scripts = sum(pkg.scripts_count for cat in categories for pkg in cat.packages)
        total_assets_extras = sum(pkg.assets_count for cat in categories for pkg in cat.packages)

        # Category ranking (descending by package count)
        cat_ranking = sorted(categories, key=lambda c: c.package_count, reverse=True)

        # Compute health scores for all packages
        health_results: dict[str, PackageHealthResult] = {}
        for cat in categories:
            for pkg in cat.packages:
                health_results[pkg.id] = score_package(pkg, classifications.get(pkg.id))

        # Detect risks
        risk_analysis = detect_risks(categories, classifications)

        # Generate recommendations
        recommendations = generate_recommendations(
            categories, classifications, health_results,
            risk_analysis.risks + risk_analysis.category_concentrations,
            len(duplicate_clusters),
        )

        # --- Runtime usage analysis (v0.4) ---
        usage_records = load_usage_data()
        all_pkgs = [pkg for cat in categories for pkg in cat.packages]
        usage_analysis = analyze_usage(usage_records, all_pkgs, categories)

        # Generate utilization-based recommendations
        utilization_recs = _generate_utilization_recommendations(usage_analysis, total_packages)
        recommendations.extend(utilization_recs)

        # --- Library-level health score ---
        library_health = self._compute_library_health(
            categories, health_results, risk_analysis, type_counts, total_packages,
        )

        # Category breakdown
        cat_breakdown: list[str] = []
        for cat in categories:
            cat_pkgs = cat.packages
            cat_types = Counter(
                classifications[p.id].type.value for p in cat_pkgs if p.id in classifications
            )
            lines = [f"### {cat.name}"]
            if cat.description:
                lines.append(f"*{cat.description[:200]}*" if len(cat.description) > 200 else f"*{cat.description}*")
            lines.append(f"- **{len(cat_pkgs)}** skill packages")
            for t in AssetType:
                count = cat_types.get(t.value, 0)
                if count:
                    lines.append(f"  - {t.value}: {count}")
            cat_breakdown.append("\n".join(lines))

        # Package type distribution (based ONLY on SKILL.md classification)
        type_dist_lines: list[str] = []
        for t in AssetType:
            count = type_counts.get(t, 0)
            if count:
                pct = count / max(total_packages, 1) * 100
                type_dist_lines.append(f"- **{t.value}**: {count} ({pct:.0f}%)")

        # All packages for sorting
        all_packages: list[tuple[Category, PackageClassification | None, SkillPackage]] = []
        for cat in categories:
            for pkg in cat.packages:
                pc = classifications.get(pkg.id)
                all_packages.append((cat, pc, pkg))

        # Largest packages by total_asset_count
        largest = sorted(all_packages, key=lambda x: x[2].total_asset_count, reverse=True)[:10]

        # Most complex packages by complexity_score
        complex_pkgs = sorted(
            all_packages,
            key=lambda x: x[2].complexity_score,
            reverse=True,
        )[:10]

        # Healthiest packages
        healthiest = sorted(
            health_results.values(),
            key=lambda h: h.overall,
            reverse=True,
        )[:10]

        # Highest risk packages
        highest_risk = sorted(
            health_results.values(),
            key=lambda h: h.overall,
        )[:10]

        # Most valuable packages: Executable + Supporting Assets + Complexity - Risk
        def value_score(hr: PackageHealthResult) -> int:
            pkg = None
            for cat in categories:
                for p in cat.packages:
                    if p.id == hr.package_id:
                        pkg = p
                        break
                if pkg:
                    break
            if not pkg:
                return 0
            cls = classifications.get(pkg.id)
            bonus = 0
            if cls and cls.type.value == "Executable Skill":
                bonus += 30
            elif cls and cls.type.value == "Workflow":
                bonus += 20
            bonus += pkg.total_asset_count * 2
            bonus += min(pkg.complexity_score, 30)
            risk_penalty = 100 - hr.overall
            return bonus - risk_penalty

        most_valuable = sorted(
            health_results.values(),
            key=value_score,
            reverse=True,
        )[:10]

        # Duplicate clusters
        dup_lines: list[str] = []
        if duplicate_clusters:
            for idx, cluster in enumerate(duplicate_clusters, 1):
                avg = cluster.average_similarity
                dup_lines.append(f"#### Cluster {idx} (avg similarity {avg:.2f})")
                for pkg in cluster.packages:
                    pc = classifications.get(pkg.id)
                    type_str = pc.type.value if pc else "Unclassified"
                    dup_lines.append(f"- `{pkg.id}` — {type_str}")
                dup_lines.append("")
        else:
            dup_lines.append("No duplicate skill packages detected.")

        # Governance summary
        governance_summary = self._build_governance_summary(
            categories, health_results, risk_analysis, type_counts, total_packages,
        )

        # Build report
        lines = [
            "# Skill Inspector Report (Package-Aware)",
            "",
            "## Summary",
            "",
            f"- **Total Categories**: {total_categories}",
            f"- **Total Skill Packages**: {total_packages}",
            f"- **Total Assets**: {total_assets}",
            f"- **Duplicate Clusters**: {len(duplicate_clusters)}",
            "",
        ] + _build_utilization_section(usage_analysis) + [
            "",
            "## Library Health Score",
            "",
            f"**Overall Health: {library_health['overall']} / 100**",
            "",
            f"- **Structure**: {library_health['structure']} / 25",
            f"- **Maintainability**: {library_health['maintainability']} / 25",
            f"- **Reusability**: {library_health['reusability']} / 25",
            f"- **Duplication**: {library_health['duplication']} / 25",
            "",
            "## Asset Distribution",
            "",
            f"- **References**: {total_references}",
            f"- **Templates**: {total_templates}",
            f"- **Scripts**: {total_scripts}",
            f"- **Assets**: {total_assets_extras}",
            "",
            "## Package Type Distribution",
            "",
        ] + type_dist_lines + [
            "",
            "## Top Categories",
            "",
        ] + [f"- **{cat.name}**: {cat.package_count} packages" for cat in cat_ranking] + [
            "",
            "## Category Breakdown",
            "",
        ] + cat_breakdown + [
            "",
            "## Largest Packages",
            "",
            "| Rank | Package | Category | References | Templates | Scripts | Assets | Complexity |",
            "|---:|---|---|---:|---:|---:|---:|---:|",
        ]
        for rank, (cat, pc, pkg) in enumerate(largest, 1):
            lines.append(
                f"| {rank} | `{pkg.id}` | {cat.name} "
                f"| {pkg.references_count} | {pkg.templates_count} "
                f"| {pkg.scripts_count} | {pkg.assets_count} "
                f"| {pkg.complexity_score} |"
            )

        lines += [
            "",
            "## Most Complex Packages",
            "",
            "| Rank | Package | Category | Complexity | References | Templates | Scripts | Assets |",
            "|---:|---|---|---:|---:|---:|---:|---:|",
        ]
        for rank, (cat, pc, pkg) in enumerate(complex_pkgs[:10], 1):
            type_str = pc.type.value if pc else "?"
            lines.append(
                f"| {rank} | `{pkg.id}` | {cat.name} | {pkg.complexity_score} "
                f"| {pkg.references_count} | {pkg.templates_count} "
                f"| {pkg.scripts_count} | {pkg.assets_count} |"
            )

        # Healthiest packages
        lines += [
            "",
            "## Healthiest Packages",
            "",
            "| Rank | Package | Category | Health |",
            "|---:|---|---|---:|",
        ]
        for rank, hr in enumerate(healthiest, 1):
            lines.append(f"| {rank} | `{hr.package_id}` | {hr.category} | {hr.overall} / 100 |")

        # Highest risk packages
        lines += [
            "",
            "## Highest Risk Packages",
            "",
            "| Rank | Package | Category | Health | Complexity | Risk Factors |",
            "|---:|---|---|---:|---:|---|",
        ]
        for rank, hr in enumerate(highest_risk, 1):
            risk_text = "; ".join(hr.risk_factors) if hr.risk_factors else "-"
            pkg_obj = next(
                (p for cat in categories for p in cat.packages if p.id == hr.package_id),
                None,
            )
            complexity = pkg_obj.complexity_score if pkg_obj else "?"
            lines.append(
                f"| {rank} | `{hr.package_id}` | {hr.category} "
                f"| {hr.overall} / 100 | {complexity} | {risk_text} |"
            )

        # Most valuable packages
        lines += [
            "",
            "## Most Valuable Packages",
            "",
            "| Rank | Package | Category | Health | Value Score |",
            "|---:|---|---|---:|---:|",
        ]
        for rank, hr in enumerate(most_valuable, 1):
            lines.append(
                f"| {rank} | `{hr.package_id}` | {hr.category} "
                f"| {hr.overall} / 100 | {value_score(hr)} |"
            )

        # Risk analysis
        all_risks = risk_analysis.risks + risk_analysis.category_concentrations
        if all_risks:
            lines += [
                "",
                "## Risk Analysis",
                "",
            ]
            # Group by type
            risk_groups: dict[str, list] = {}
            for r in all_risks:
                risk_groups.setdefault(r.risk_type, []).append(r)

            if "monolithic" in risk_groups:
                lines.append("### Monolithic Packages")
                lines.append("")
                for r in sorted(risk_groups["monolithic"], key=lambda x: int(x.detail.split(": ")[1] if ": " in x.detail else 0), reverse=True):
                    lines.append(f"- `{r.package_id}` Severity: {r.severity.value} — {r.detail}")
                lines.append("")

            if "ref_bloat" in risk_groups:
                lines.append("### Reference Bloat")
                lines.append("")
                for r in risk_groups["ref_bloat"]:
                    lines.append(f"- `{r.package_id}` {r.detail}")
                lines.append("")

            if "template_bloat" in risk_groups:
                lines.append("### Template Bloat")
                lines.append("")
                for r in risk_groups["template_bloat"]:
                    lines.append(f"- `{r.package_id}` {r.detail}")
                lines.append("")

            if "script_bloat" in risk_groups:
                lines.append("### Script Bloat")
                lines.append("")
                for r in risk_groups["script_bloat"]:
                    lines.append(f"- `{r.package_id}` {r.detail}")
                lines.append("")

            if "category_concentration" in risk_groups:
                lines.append("### Category Concentration")
                lines.append("")
                for r in risk_groups["category_concentration"]:
                    lines.append(f"- `{r.package_id}` {r.detail}")
                lines.append("")

        # Governance recommendations
        if recommendations:
            lines += [
                "",
                "## Governance Recommendations",
                "",
            ]
            # Sort by severity
            sev_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
            sorted_recs = sorted(recommendations, key=lambda r: sev_order.get(r.severity, 99))
            for rec in sorted_recs:
                scope = rec.package_id if rec.package_id else "[library-wide]"
                lines.append(f"### {rec.title}")
                lines.append(f"- **Scope**: `{scope}`")
                lines.append(f"- **Severity**: {rec.severity}")
                lines.append(f"- **Description**: {rec.description}")
                lines.append(f"- **Action**: {rec.action}")
                lines.append("")

        lines += [
            "",
            "## Duplicate Skill Packages",
            "",
        ] + dup_lines + [
            "",
            "## Governance Summary",
            "",
        ] + governance_summary

        text = "\n".join(lines) + "\n"
        output.write_text(text, encoding="utf-8")
        return text

    def _compute_library_health(
        self,
        categories: list[Category],
        health_results: dict[str, PackageHealthResult],
        risk_analysis: RiskAnalysis,
        type_counts: Counter,
        total_packages: int,
    ) -> dict[str, int]:
        """Compute overall library health score (0-100) from four dimensions."""
        if total_packages == 0:
            return {"overall": 0, "structure": 0, "maintainability": 0, "reusability": 0, "duplication": 0}

        # Structure: category balance + package distribution
        structure = self._score_structure(categories, total_packages)

        # Maintainability: average package health + risk penalties
        maintainability = self._score_maintainability(health_results, risk_analysis.risks)

        # Reusability: executable/workflow ratio
        reusability = self._score_reusability(type_counts, total_packages)

        # Duplication: based on duplicate clusters
        duplication = self._score_duplication(risk_analysis)

        overall = structure + maintainability + reusability + duplication
        overall = min(100, overall)

        return {
            "overall": overall,
            "structure": structure,
            "maintainability": maintainability,
            "reusability": reusability,
            "duplication": duplication,
        }

    def _score_structure(self, categories: list[Category], total: int) -> int:
        """Structure score (0-25)."""
        score = 25

        # Penalize category imbalance
        if total > 0:
            max_cat_ratio = max(c.package_count for c in categories) / total
            if max_cat_ratio > 0.30:
                score -= 5
            elif max_cat_ratio > 0.20:
                score -= 2

        # Penalize many categories with only 1 package (fragmentation)
        singleton_count = sum(1 for c in categories if c.package_count == 1)
        if total > 10 and singleton_count / total > 0.30:
            score -= 5
        elif singleton_count > 5:
            score -= 2

        return max(0, score)

    def _score_maintainability(self, health_results: dict[str, PackageHealthResult], risks: list) -> int:
        """Maintainability score (0-25)."""
        if not health_results:
            return 0

        avg_health = sum(h.overall for h in health_results.values()) / len(health_results)
        score = int(avg_health * 25 / 100)  # normalize to 0-25

        # Penalty for risk items (capped to prevent negative)
        total_penalty = 0
        for r in risks:
            if r.severity.value in ("High", "Critical"):
                total_penalty += 1
            else:
                total_penalty += 0.5
        score -= min(int(total_penalty), 10)  # cap penalty at 10 points

        return max(0, min(25, score))

    def _score_reusability(self, type_counts: Counter, total: int) -> int:
        """Reusability score (0-25)."""
        if total == 0:
            return 0

        exec_count = type_counts.get(AssetType.EXECUTABLE_SKILL, 0)
        workflow_count = type_counts.get(AssetType.WORKFLOW, 0)
        usable_ratio = (exec_count + workflow_count) / total

        # 0-25 scale: 100% usable = 25, 0% = 0
        return int(usable_ratio * 25)

    def _score_duplication(self, risk_analysis: RiskAnalysis) -> int:
        """Duplication score (0-25). 25 = no issues."""
        score = 25
        score -= len(risk_analysis.risks) * 1  # reduced penalty
        score -= len(risk_analysis.category_concentrations) * 2
        return max(0, score)

    def _build_governance_summary(
        self,
        categories: list[Category],
        health_results: dict[str, PackageHealthResult],
        risk_analysis: RiskAnalysis,
        type_counts: Counter,
        total_packages: int,
    ) -> list[str]:
        """Build the Governance Summary section."""
        lines: list[str] = []

        # Compute library health
        health = self._compute_library_health(
            categories, health_results, risk_analysis, type_counts, total_packages,
        )
        lines.append(f"**Library Health: {health['overall']} / 100**")
        lines.append("")

        # Strengths
        strengths: list[str] = []
        if total_packages > 0:
            max_cat_ratio = max(c.package_count for c in categories) / total_packages
            if max_cat_ratio <= 0.25:
                strengths.append("Strong category diversity")
            elif max_cat_ratio <= 0.30:
                strengths.append("Acceptable category distribution")

            exec_ratio = type_counts.get(AssetType.EXECUTABLE_SKILL, 0) / total_packages
            if exec_ratio > 0.3:
                strengths.append("Large executable skill inventory")
            elif exec_ratio > 0.1:
                strengths.append("Moderate executable skill coverage")

            workflow_ratio = type_counts.get(AssetType.WORKFLOW, 0) / total_packages
            if workflow_ratio > 0.2:
                strengths.append("Good workflow package coverage")

            if not risk_analysis.risks:
                strengths.append("No oversized packages detected")

        avg_health = sum(h.overall for h in health_results.values()) / len(health_results) if health_results else 0
        if avg_health >= 70:
            strengths.append("Good overall package health")
        elif avg_health >= 50:
            strengths.append("Moderate package health")

        if strengths:
            lines.append("**Strengths**")
            for s in strengths:
                lines.append(f"✓ {s}")

        # Risks
        risks: list[str] = []
        if risk_analysis.risks:
            critical_count = sum(1 for r in risk_analysis.risks if r.severity.value in ("High", "Critical"))
            if critical_count > 0:
                risks.append(f"{critical_count} oversized or bloated packages")
            ref_bloat = [r for r in risk_analysis.risks if r.risk_type == "ref_bloat"]
            tmpl_bloat = [r for r in risk_analysis.risks if r.risk_type == "template_bloat"]
            if ref_bloat:
                risks.append("Reference bloat in some packages")
            if tmpl_bloat:
                risks.append("Template concentration detected")

        for cc in risk_analysis.category_concentrations:
            risks.append(f"Category concentration: {cc.detail}")

        if not risk_analysis.risks and not risk_analysis.category_concentrations:
            pass  # no risks
        elif risks:
            lines.append("")
            lines.append("**Risks**")
            for r in risks:
                lines.append(f"⚠ {r}")

        return lines


def value_score(hr, categories):
    """Helper for the most valuable packages ranking.

    Formula: Executable bonus + Supporting assets + Complexity - Risk
    """
    from .models import AssetType

    pkg = None
    for cat in categories:
        for p in cat.packages:
            if p.id == hr.package_id:
                pkg = p
                break
        if pkg:
            break
    if not pkg:
        return 0

    # This is a placeholder — the actual scoring happens inline in generate()
    return hr.overall


def _build_utilization_section(usage: UsageAnalysis) -> list[str]:
    """Build the Skill Utilization section for the report (v0.4)."""
    lines: list[str] = [
        "## Skill Utilization",
        "",
    ]

    # Check if usage data is available
    has_data = usage.installed_skills > 0 or usage.used_skills > 0

    if not has_data:
        lines.append("*No usage data available. Runtime governance analysis skipped.*")
        lines.append("")
        return lines

    lines.append(f"**Installed Skills**: {usage.installed_skills}")
    lines.append("")
    lines.append(f"**Used Skills**: {usage.used_skills}")
    lines.append("")
    lines.append(f"**Unused Skills**: {usage.unused_skills}")
    lines.append("")
    lines.append(f"**Utilization Rate**: {usage.utilization_rate}%")
    lines.append("")

    # Most Used Skills
    if usage.most_used:
        lines.append("### Most Used Skills")
        lines.append("")
        lines.append("| Skill | Uses |")
        lines.append("|---|---:|")
        for skill_id, use_count in usage.most_used:
            lines.append(f"| `{skill_id}` | {use_count} |")
        lines.append("")

    # Recently Used Skills
    if usage.recently_used:
        lines.append("### Recently Used Skills")
        lines.append("")
        lines.append("| Skill | Last Used |")
        lines.append("|---|---|")
        for skill_id, last_date in usage.recently_used:
            date_str = last_date if last_date else "N/A"
            lines.append(f"| `{skill_id}` | {date_str} |")
        lines.append("")

    # Never Used Skills (limited to 20)
    if usage.never_used:
        lines.append("### Never Used Skills")
        lines.append("")
        lines.append(f"*{usage.unused_skills} skills have never been used.*")
        lines.append("")
        lines.append("| Skill | Category |")
        lines.append("|---|---|")
        for skill_id, category in usage.never_used:
            lines.append(f"| `{skill_id}` | {category} |")
        if usage.unused_skills > 20:
            lines.append(f"\n*... and {usage.unused_skills - 20} more*")
        lines.append("")

    # Category Utilization
    if usage.category_utilization:
        lines.append("### Category Utilization")
        lines.append("")
        lines.append("| Category | Utilization | Used / Total |")
        lines.append("|---|---:|---:|")
        for cat_name, pct, used, total in usage.category_utilization:
            lines.append(f"| {cat_name} | {pct}% | {used} / {total} |")
        lines.append("")

    return lines


def _generate_utilization_recommendations(
    usage: UsageAnalysis, total_packages: int,
) -> list[Recommendation]:
    """Generate utilization-based governance recommendations (v0.4)."""
    recs: list[Recommendation] = []

    if usage.installed_skills == 0:
        return recs

    # Unused skills recommendation
    if usage.unused_skills > 0:
        recs.append(Recommendation(
            package_id=None,
            category=None,
            severity="Medium" if usage.unused_skills < 50 else "High",
            title="Review unused skills for archival",
            description=(
                f"{usage.unused_skills} skills have never been used. "
                f"({usage.utilization_rate}% utilization rate)"
            ),
            action="Consider archiving unused skills to reduce library bloat. "
                   "Unused skills consume memory and increase classification overhead.",
        ))

    # Low utilization rate
    if usage.utilization_rate < 10 and usage.installed_skills > 10:
        recs.append(Recommendation(
            package_id=None,
            category=None,
            severity="High",
            title="Skill utilization is below 10%",
            description=(
                f"Only {usage.utilization_rate}% of installed skills are actively used. "
                f"Large portions of the library may no longer provide value."
            ),
            action="Review the unused skills list and consider removing or archiving "
                   "skills that are no longer relevant to your workflow.",
        ))

    # Category with 0% utilization
    for cat_name, pct, used, total in usage.category_utilization:
        if pct == 0 and total > 0:
            recs.append(Recommendation(
                package_id=None,
                category=cat_name,
                severity="Low",
                title=f"Category '{cat_name}' has 0% utilization",
                description=(
                    f"All {total} skills in the '{cat_name}' category have never been used."
                ),
                action="Review whether these skills are still relevant to the current environment. "
                       "Consider archiving the entire category if unused.",
            ))

    return recs
