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
from .usage_analysis import (
    UsageAnalysis,
    UsageRecord,
    analyze_usage,
    is_package_used,
    is_recently_used,
    load_usage_data,
)


class PackageReportGenerator:
    """Generates a markdown report for package-aware analysis."""

    def generate(
        self,
        categories: list[Category],
        classifications: dict[str, PackageClassification],
        duplicate_clusters: list[PackageDuplicateCluster],
        output: Path,
    ) -> str:
        total_categories = len(categories)
        total_packages = sum(cat.package_count for cat in categories)
        all_pkgs = [pkg for cat in categories for pkg in cat.packages]
        total_assets = sum(pkg.total_asset_count for pkg in all_pkgs)

        type_counts = Counter(pc.type for pc in classifications.values())

        total_references = sum(pkg.references_count for pkg in all_pkgs)
        total_templates = sum(pkg.templates_count for pkg in all_pkgs)
        total_scripts = sum(pkg.scripts_count for pkg in all_pkgs)
        total_assets_extras = sum(pkg.assets_count for pkg in all_pkgs)

        package_lookup = {pkg.id: pkg for pkg in all_pkgs}

        health_results: dict[str, PackageHealthResult] = {}
        for cat in categories:
            for pkg in cat.packages:
                health_results[pkg.id] = score_package(pkg, classifications.get(pkg.id))

        risk_analysis = detect_risks(categories, classifications)

        recommendations = generate_recommendations(
            categories,
            classifications,
            health_results,
            risk_analysis.risks + risk_analysis.category_concentrations,
            len(duplicate_clusters),
        )

        usage_records = load_usage_data()
        usage_analysis = analyze_usage(usage_records, all_pkgs, categories)

        utilization_recs = _generate_utilization_recommendations(usage_analysis, total_packages)
        recommendations.extend(utilization_recs)

        library_health = self._compute_library_health(
            categories,
            health_results,
            risk_analysis,
            type_counts,
            total_packages,
        )

        from .usage_analysis import match_usage_to_packages

        matched_usage = match_usage_to_packages(usage_records, [p.id for p in all_pkgs])

        governance_summary = self._build_governance_summary(
            categories,
            health_results,
            risk_analysis,
            type_counts,
            total_packages,
            usage_analysis,
            duplicate_clusters,
            matched_usage,
        )

        cat_breakdown: list[str] = []
        for cat in categories:
            cat_pkgs = cat.packages
            cat_types = Counter(
                classifications[p.id].type.value for p in cat_pkgs if p.id in classifications
            )
            lines_cb = [f"### {cat.name}"]
            if cat.description:
                desc = cat.description[:200]
                lines_cb.append(f"*{desc}*" if len(cat.description) > 200 else f"*{cat.description}*")
            lines_cb.append(f"- **{len(cat_pkgs)}** skill packages")
            for asset_type in AssetType:
                count = cat_types.get(asset_type.value, 0)
                if count:
                    lines_cb.append(f"  - {asset_type.value}: {count}")
            cat_breakdown.append("\n".join(lines_cb))

        type_dist_lines: list[str] = []
        for asset_type in AssetType:
            count = type_counts.get(asset_type, 0)
            if count:
                pct = count / max(total_packages, 1) * 100
                type_dist_lines.append(f"- **{asset_type.value}**: {count} ({pct:.0f}%)")

        highest_risk = sorted(health_results.values(), key=lambda result: result.overall)[:10]

        most_valuable = sorted(
            health_results.values(),
            key=lambda result: _value_score(result, package_lookup, classifications),
            reverse=True,
        )[:10]

        unused_pkgs = [pkg for pkg in all_pkgs if not is_package_used(matched_usage.get(pkg.id))]
        unused_high_cost = sorted(unused_pkgs, key=lambda pkg: pkg.complexity_score, reverse=True)

        cleanup_priorities = self._build_cleanup_priorities(
            all_pkgs,
            health_results,
            risk_analysis,
            matched_usage,
        )

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
        ]

        lines += self._build_utilization_summary(usage_analysis)

        lines += [
            "## Library Health Score",
            "",
            f"**Overall Health: {library_health['overall']} / 100**",
            "",
            f"- **Structure**: {library_health['structure']} / 25",
            f"- **Maintainability**: {library_health['maintainability']} / 25",
            f"- **Reusability**: {library_health['reusability']} / 25",
            f"- **Duplication**: {library_health['duplication']} / 25",
            "",
        ]

        lines += governance_summary
        lines += self._build_runtime_governance(usage_analysis, matched_usage, package_lookup, unused_high_cost)

        lines += self._render_cleanup_priorities(cleanup_priorities)

        critical_high_recs = [rec for rec in recommendations if rec.severity in {"Critical", "High"}]
        hidden_medium = sum(1 for rec in recommendations if rec.severity == "Medium")
        hidden_low = sum(1 for rec in recommendations if rec.severity == "Low")
        if critical_high_recs:
            lines += [
                "## Governance Recommendations",
                "",
            ]
            sev_order = {"Critical": 0, "High": 1}
            sorted_recs = sorted(critical_high_recs, key=lambda rec: sev_order.get(rec.severity, 99))
            for rec in sorted_recs:
                scope = rec.package_id if rec.package_id else "[library-wide]"
                lines.append(f"### {rec.title}")
                lines.append(f"- **Scope**: `{scope}`")
                lines.append(f"- **Severity**: {rec.severity}")
                lines.append(f"- **Description**: {rec.description}")
                lines.append(f"- **Action**: {rec.action}")
                lines.append("")
        if hidden_medium or hidden_low:
            lines += [
                "Additional Recommendations Hidden",
                "",
                f"- Medium: {hidden_medium}",
                f"- Low: {hidden_low}",
                "",
            ]

        lines += [
            "## Highest Risk Packages",
            "",
            "| Rank | Package | Category | Health | Complexity | Risk Factors |",
            "|---:|---|---|---:|---:|---|",
        ]
        for rank, result in enumerate(highest_risk, 1):
            risk_text = "; ".join(result.risk_factors) if result.risk_factors else "-"
            pkg_obj = package_lookup.get(result.package_id)
            complexity = pkg_obj.complexity_score if pkg_obj else "?"
            lines.append(
                f"| {rank} | `{result.package_id}` | {result.category} "
                f"| {result.overall} / 100 | {complexity} | {risk_text} |"
            )
        lines.append("")

        lines += [
            "## Most Valuable Packages",
            "",
            "| Rank | Package | Category | Health | Value Score | Drivers |",
            "|---:|---|---|---:|---:|---|",
        ]
        for rank, result in enumerate(most_valuable, 1):
            lines.append(
                f"| {rank} | `{result.package_id}` | {result.category} "
                f"| {result.overall} / 100 | {_value_score(result, package_lookup, classifications)} | "
                f"{_value_drivers(result, package_lookup, classifications)} |"
            )
        lines.append("")

        lines += [
            "---",
            "",
        ]

        lines += [
            "## Package Type Distribution",
            "",
        ] + type_dist_lines + [
            "",
        ]

        lines += [
            "## Asset Distribution",
            "",
            f"- **References**: {total_references}",
            f"- **Templates**: {total_templates}",
            f"- **Scripts**: {total_scripts}",
            f"- **Assets**: {total_assets_extras}",
            "",
        ]

        lines += [
            "## Category Breakdown",
            "",
        ] + cat_breakdown + [
            "",
        ]

        lines += [
            "## Duplicate Skill Packages",
            "",
        ] + dup_lines

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

        structure = self._score_structure(categories, total_packages)
        maintainability = self._score_maintainability(health_results, risk_analysis.risks)
        reusability = self._score_reusability(type_counts, total_packages)
        duplication = self._score_duplication(risk_analysis)

        overall = min(100, structure + maintainability + reusability + duplication)
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

        if total > 0:
            max_cat_ratio = max(c.package_count for c in categories) / total
            if max_cat_ratio > 0.30:
                score -= 5
            elif max_cat_ratio > 0.20:
                score -= 2

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

        avg_health = sum(result.overall for result in health_results.values()) / len(health_results)
        score = int(avg_health * 25 / 100)

        total_penalty = 0
        for risk in risks:
            if risk.severity.value in ("High", "Critical"):
                total_penalty += 1
            else:
                total_penalty += 0.5
        score -= min(int(total_penalty), 10)

        return max(0, min(25, score))

    def _score_reusability(self, type_counts: Counter, total: int) -> int:
        """Reusability score (0-25)."""
        if total == 0:
            return 0

        exec_count = type_counts.get(AssetType.EXECUTABLE_SKILL, 0)
        workflow_count = type_counts.get(AssetType.WORKFLOW, 0)
        usable_ratio = (exec_count + workflow_count) / total
        return int(usable_ratio * 25)

    def _score_duplication(self, risk_analysis: RiskAnalysis) -> int:
        """Duplication score (0-25). 25 = no issues."""
        score = 25
        score -= len(risk_analysis.risks) * 1
        score -= len(risk_analysis.category_concentrations) * 2
        return max(0, score)

    def _build_governance_summary(
        self,
        categories: list[Category],
        health_results: dict[str, PackageHealthResult],
        risk_analysis: RiskAnalysis,
        type_counts: Counter,
        total_packages: int,
        usage: UsageAnalysis,
        duplicate_clusters: list[PackageDuplicateCluster],
        matched_usage: dict[str, UsageRecord | None],
    ) -> list[str]:
        """Build the Governance Summary section (v0.4.2)."""
        lines = [
            "## Governance Summary",
            "",
        ]

        health = self._compute_library_health(
            categories,
            health_results,
            risk_analysis,
            type_counts,
            total_packages,
        )

        findings: list[tuple[int, str]] = []
        if usage.utilization_rate < 10:
            findings.append((100, f"• Only {usage.utilization_rate}% of installed skills have ever been executed."))
        else:
            findings.append((100, f"• {usage.utilization_rate}% of installed skills have ever been executed."))
        findings.append((95, f"• {usage.unused_skills} skills have never been executed."))

        unused_pkgs = [pkg for cat in categories for pkg in cat.packages if not is_package_used(matched_usage.get(pkg.id))]
        if unused_pkgs:
            largest_unused = max(unused_pkgs, key=lambda pkg: pkg.complexity_score)
            findings.append((90, f"• `{largest_unused.id}` is the largest unused package by complexity ({largest_unused.complexity_score})."))

        if health_results:
            weakest = min(health_results.values(), key=lambda result: result.overall)
            findings.append((85, f"• `{weakest.package_id}` has the lowest health score at {weakest.overall} / 100."))

        if duplicate_clusters:
            findings.append((70, f"• Duplicate package risk is elevated ({len(duplicate_clusters)} clusters detected)."))
        else:
            findings.append((60, "• Duplicate package risk remains low."))

        if health["overall"] < 70:
            findings.append((80, f"• Library health is below target at {health['overall']} / 100."))
        else:
            findings.append((50, f"• Library health is at {health['overall']} / 100."))

        if risk_analysis.risks:
            highest_risk = min(health_results.values(), key=lambda result: result.overall)
            findings.append((75, f"• `{highest_risk.package_id}` currently carries the highest governance risk."))

        for _, finding in sorted(findings, key=lambda item: item[0], reverse=True)[:5]:
            lines.append(finding)
            lines.append("")
        
        return lines

    def _build_utilization_summary(self, usage: UsageAnalysis) -> list[str]:
        """Build the Skill Utilization Summary section (v0.4.1)."""
        lines = [
            "## Skill Utilization Summary",
            "",
        ]
        has_data = usage.installed_skills > 0 or usage.used_skills > 0
        if not has_data:
            lines.append("*No usage data available. Runtime governance analysis skipped.*")
            lines.append("")
            return lines

        lines.append(f"Installed Skills: {usage.installed_skills}")
        lines.append("")
        lines.append(f"Used Skills: {usage.used_skills}")
        lines.append("")
        lines.append(f"Unused Skills: {usage.unused_skills}")
        lines.append("")
        lines.append(f"Utilization Rate: {usage.utilization_rate}%")
        lines.append("")
        return lines

    def _build_runtime_governance(
        self,
        usage: UsageAnalysis,
        matched_usage: dict[str, UsageRecord | None],
        package_lookup: dict[str, SkillPackage],
        unused_high_cost: list[SkillPackage],
    ) -> list[str]:
        """Build the Runtime Governance section (v0.4.2)."""
        lines = [
            "## Runtime Governance",
            "",
        ]
        has_data = usage.installed_skills > 0 or usage.used_skills > 0
        if not has_data:
            lines.append("*No usage data available. Runtime governance analysis skipped.*")
            lines.append("")
            return lines

        used_pkgs = []
        for pkg_id, record in matched_usage.items():
            if is_package_used(record):
                used_pkgs.append((pkg_id, record))

        most_used_pkgs = sorted(used_pkgs, key=lambda item: item[1].use_count, reverse=True)[:5]

        lines.append("### Most Used Skills")
        lines.append("")
        if usage.utilization_rate < 10:
            lines.append(f"Only {usage.used_skills} of {usage.installed_skills} installed skills have ever been executed.")
        else:
            lines.append(f"{usage.used_skills} of {usage.installed_skills} installed skills have ever been executed.")
        lines.append("")
        lines.append("| Skill | Uses | Views | Last Used |")
        lines.append("| ----- | ---: | ----: | --------- |")
        for pkg_id, record in most_used_pkgs:
            last_used = record.last_used_at[:10] if record.last_used_at else "N/A"
            lines.append(f"| `{pkg_id}` | {record.use_count} | {record.view_count} | {last_used} |")
        lines.append("")

        recently_used_pkgs = [item for item in used_pkgs if is_recently_used(item[1], days=3)]
        recently_used_pkgs.sort(key=lambda item: item[1].last_used_at or "", reverse=True)

        lines.append("### Recently Used Skills")
        lines.append("")
        lines.append("Skills executed within the last 3 days.")
        lines.append("")
        lines.append("| Skill | Last Used |")
        lines.append("| ----- | --------- |")
        for pkg_id, record in recently_used_pkgs:
            last_used = record.last_used_at[:10] if record.last_used_at else "N/A"
            lines.append(f"| `{pkg_id}` | {last_used} |")
        lines.append("")

        lines += [
            "### Unused High-Cost Skills",
            "",
            f"{len(unused_high_cost)} installed skills have no recorded executions. The table shows the top 10 by complexity.",
            "",
            "| Skill | Category | Complexity | References | Templates | Scripts |",
            "| ----- | -------- | ----------: | ----------: | ---------: | --------: |",
        ]
        for pkg in unused_high_cost[:10]:
            lines.append(
                f"| `{pkg.id}` | {pkg.category} | {pkg.complexity_score} | "
                f"{pkg.references_count} | {pkg.templates_count} | {pkg.scripts_count} |"
            )
        lines.append("")

        zero_util_categories = sum(1 for _, pct, _, _ in usage.category_utilization if pct == 0)
        active_categories = [item for item in usage.category_utilization if item[1] > 0]

        lines.append("### Category Utilization")
        lines.append("")
        lines.append(f"{zero_util_categories} categories have 0% utilization and are collapsed from the table.")
        lines.append("")
        lines.append("| Category | Utilization | Used / Total |")
        lines.append("| -------- | ----------: | ------------ |")
        for cat_name, pct, used, total in active_categories:
            lines.append(f"| {cat_name} | {pct}% | {used} / {total} |")
        lines.append("")

        return lines

    def _build_cleanup_priorities(
        self,
        packages: list[SkillPackage],
        health_results: dict[str, PackageHealthResult],
        risk_analysis: RiskAnalysis,
        matched_usage: dict[str, UsageRecord | None],
    ) -> list[dict[str, str | int]]:
        """Build cleanup priority candidates from existing risk and usage signals."""
        risk_counts: Counter[str] = Counter()
        for risk in risk_analysis.risks:
            if getattr(risk, "package_id", None):
                risk_counts[risk.package_id] += 1

        priorities: list[dict[str, str | int]] = []
        for pkg in packages:
            if is_package_used(matched_usage.get(pkg.id)):
                continue

            result = health_results.get(pkg.id)
            health = result.overall if result else 0
            score = 40
            reasons = ["Unused"]

            if pkg.complexity_score >= 100:
                score += 35
                reasons.append(f"Complexity {pkg.complexity_score}")
            elif pkg.complexity_score >= 50:
                score += 25
                reasons.append(f"Complexity {pkg.complexity_score}")
            elif pkg.complexity_score >= 20:
                score += 15
                reasons.append(f"Complexity {pkg.complexity_score}")

            if health < 40:
                score += 25
                reasons.append(f"Health {health}")
            elif health < 60:
                score += 15
                reasons.append(f"Health {health}")

            risk_count = risk_counts.get(pkg.id, 0)
            if risk_count:
                score += min(risk_count * 10, 30)
                reasons.append(f"{risk_count} risk signal{'s' if risk_count != 1 else ''}")

            priorities.append(
                {
                    "package": pkg.id,
                    "score": score,
                    "reason": " + ".join(reasons),
                }
            )

        priorities.sort(key=lambda item: (int(item["score"]), str(item["package"])), reverse=True)
        return priorities[:10]

    def _render_cleanup_priorities(self, priorities: list[dict[str, str | int]]) -> list[str]:
        """Render the Cleanup Priorities section."""
        lines = [
            "## Cleanup Priorities",
            "",
            "If you only clean up a few packages first, start with the highest-scoring unused packages below.",
            "",
            "| Rank | Package | Priority Score | Reason |",
            "| ----: | ------- | -------------: | ------ |",
        ]
        for rank, item in enumerate(priorities, 1):
            lines.append(
                f"| {rank} | `{item['package']}` | {item['score']} | {item['reason']} |"
            )
        if not priorities:
            lines.append("| - | - | - | No unused packages require cleanup prioritization. |")
        lines.append("")
        return lines


def _value_score(
    result: PackageHealthResult,
    package_lookup: dict[str, SkillPackage],
    classifications: dict[str, PackageClassification],
) -> int:
    """Helper for the most valuable packages ranking."""
    pkg = package_lookup.get(result.package_id)
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
    risk_penalty = 100 - result.overall
    return bonus - risk_penalty


def _value_drivers(
    result: PackageHealthResult,
    package_lookup: dict[str, SkillPackage],
    classifications: dict[str, PackageClassification],
) -> str:
    """Explain the main drivers behind the value score."""
    pkg = package_lookup.get(result.package_id)
    if not pkg:
        return "-"

    drivers: list[str] = []
    if pkg.references_count:
        drivers.append(f"{pkg.references_count} references")
    if pkg.templates_count >= 10:
        drivers.append("high template density")
    elif pkg.templates_count:
        drivers.append(f"{pkg.templates_count} templates")
    if pkg.scripts_count >= 5:
        drivers.append("script-heavy")

    classification = classifications.get(result.package_id)
    if classification and classification.type.value in {"Executable Skill", "Workflow"}:
        drivers.append(classification.type.value.lower())

    if result.overall >= 70:
        drivers.append("good health")
    elif result.overall < 50:
        drivers.append("health penalty")

    if not drivers:
        drivers.append("balanced asset mix")

    return ", ".join(drivers)


def _generate_utilization_recommendations(
    usage: UsageAnalysis,
    total_packages: int,
) -> list[Recommendation]:
    """Generate utilization-based governance recommendations (v0.4.1)."""
    recs: list[Recommendation] = []

    if usage.installed_skills == 0:
        return recs

    if usage.unused_skills > 0:
        recs.append(Recommendation(
            package_id=None,
            category=None,
            severity="Medium" if usage.unused_skills < 50 else "High",
            title="Review unused skills for archival",
            description=(
                f"{'Only ' if usage.utilization_rate < 10 else ''}{usage.utilization_rate}% of installed skills are actively used. "
                f"{usage.unused_skills} skills have never been used."
            ),
            action="Consider archiving or removing unused skills. Review large unused packages before adding new skills.",
        ))

    if usage.utilization_rate < 10 and usage.installed_skills > 10:
        recs.append(Recommendation(
            package_id=None,
            category=None,
            severity="High",
            title="Skill utilization is below 10%",
            description=(
                f"{'Only ' if usage.utilization_rate < 10 else ''}{usage.utilization_rate}% of installed skills are actively used. "
                f"Large portions of the library may no longer provide value."
            ),
            action="Review the unused skills list and consider removing or archiving "
                   "skills that are no longer relevant to your workflow.",
        ))

    return recs
