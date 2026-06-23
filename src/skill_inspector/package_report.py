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
from .usage_analysis import UsageAnalysis, UsageRecord, analyze_usage, load_usage_data


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
        all_pkgs = [pkg for cat in categories for pkg in cat.packages]
        total_assets = sum(
            pkg.total_asset_count for pkg in all_pkgs
        )

        # Classification counts
        pkg_classes = list(classifications.values())
        type_counts = Counter(pc.type for pc in pkg_classes)

        # Asset distribution totals
        total_references = sum(pkg.references_count for pkg in all_pkgs)
        total_templates = sum(pkg.templates_count for pkg in all_pkgs)
        total_scripts = sum(pkg.scripts_count for pkg in all_pkgs)
        total_assets_extras = sum(pkg.assets_count for pkg in all_pkgs)

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
        usage_analysis = analyze_usage(usage_records, all_pkgs, categories)

        # Generate utilization-based recommendations
        utilization_recs = _generate_utilization_recommendations(usage_analysis, total_packages)
        recommendations.extend(utilization_recs)

        # --- Library-level health score ---
        library_health = self._compute_library_health(
            categories, health_results, risk_analysis, type_counts, total_packages,
        )

        # Match usage to packages
        from .usage_analysis import match_usage_to_packages
        matched_usage = match_usage_to_packages(usage_records, [p.id for p in all_pkgs])

        # Governance summary
        governance_summary = self._build_governance_summary(
            categories, health_results, risk_analysis, type_counts, total_packages, usage_analysis, duplicate_clusters,
        )

        # Category breakdown
        cat_breakdown: list[str] = []
        for cat in categories:
            cat_pkgs = cat.packages
            cat_types = Counter(
                classifications[p.id].type.value for p in cat_pkgs if p.id in classifications
            )
            lines_cb = [f"### {cat.name}"]
            if cat.description:
                lines_cb.append(f"*{cat.description[:200]}*" if len(cat.description) > 200 else f"*{cat.description}*")
            lines_cb.append(f"- **{len(cat_pkgs)}** skill packages")
            for t in AssetType:
                count = cat_types.get(t.value, 0)
                if count:
                    lines_cb.append(f"  - {t.value}: {count}")
            cat_breakdown.append("\n".join(lines_cb))

        # Package type distribution (based ONLY on SKILL.md classification)
        type_dist_lines: list[str] = []
        for t in AssetType:
            count = type_counts.get(t, 0)
            if count:
                pct = count / max(total_packages, 1) * 100
                type_dist_lines.append(f"- **{t.value}**: {count} ({pct:.0f}%)")

        # Highest risk packages
        highest_risk = sorted(
            health_results.values(),
            key=lambda h: h.overall,
        )[:10]

        # Most valuable packages
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

        # Unused High-Cost Skills
        unused_pkgs = []
        for pkg in all_pkgs:
            rec = matched_usage.get(pkg.id)
            is_used = rec and (rec.use_count > 0 or rec.view_count > 0)
            if not is_used:
                unused_pkgs.append(pkg)
        unused_high_cost = sorted(unused_pkgs, key=lambda p: p.complexity_score, reverse=True)

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
        ]

        # 2. Skill Utilization Summary
        lines += self._build_utilization_summary(usage_analysis)

        # 3. Library Health Score
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

        # 4. Governance Summary
        lines += governance_summary

        # 5. Runtime Governance
        lines += self._build_runtime_governance(usage_analysis, matched_usage)

        # 6. Governance Recommendations
        if recommendations:
            lines += [
                "## Governance Recommendations",
                "",
            ]
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

        # 7. Highest Risk Packages
        lines += [
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
        lines.append("")

        # 8. Unused High-Cost Skills
        lines += [
            "## Unused High-Cost Skills",
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

        # 9. Most Valuable Packages
        lines += [
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
        lines.append("")

        # 10. ---
        lines += [
            "---",
            "",
        ]

        # 11. Package Type Distribution
        lines += [
            "## Package Type Distribution",
            "",
        ] + type_dist_lines + [
            "",
        ]

        # 12. Asset Distribution
        lines += [
            "## Asset Distribution",
            "",
            f"- **References**: {total_references}",
            f"- **Templates**: {total_templates}",
            f"- **Scripts**: {total_scripts}",
            f"- **Assets**: {total_assets_extras}",
            "",
        ]

        # 13. Category Breakdown
        lines += [
            "## Category Breakdown",
            "",
        ] + cat_breakdown + [
            "",
        ]

        # 14. Duplicate Skill Packages
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
        usage: UsageAnalysis,
        duplicate_clusters: list[PackageDuplicateCluster],
    ) -> list[str]:
        """Build the Governance Summary section (v0.4.1)."""
        lines = [
            "## Governance Summary",
            "",
        ]

        # Compute library health
        health = self._compute_library_health(
            categories, health_results, risk_analysis, type_counts, total_packages,
        )
        overall_health = health["overall"]

        # Health score bullet
        if overall_health < 70:
            lines.append("• Health score is below recommended level.")
        else:
            lines.append("• Health score is at or above recommended level.")

        # Utilization / Unused bullets
        has_data = usage.installed_skills > 0 or usage.used_skills > 0
        if has_data:
            lines.append(f"• Only {usage.utilization_rate}% of installed skills have been used.")
            lines.append(f"• {usage.unused_skills} skills have never been used.")
        else:
            lines.append("• No usage data available to evaluate skill utilization.")

        # Large unused packages representing overhead
        all_packages = [pkg for cat in categories for pkg in cat.packages]
        usage_records = load_usage_data()
        from .usage_analysis import match_usage_to_packages
        matched = match_usage_to_packages(usage_records, [p.id for p in all_packages])
        large_unused = 0
        for pkg in all_packages:
            rec = matched.get(pkg.id)
            is_used = rec and (rec.use_count > 0 or rec.view_count > 0)
            if not is_used and pkg.complexity_score > 10:
                large_unused += 1

        if large_unused > 0:
            lines.append("• Several large unused packages represent maintenance overhead.")
        else:
            lines.append("• Unused packages do not represent significant complexity overhead.")

        # Duplicate risk bullet
        if duplicate_clusters:
            lines.append(f"• Duplicate package risk is elevated ({len(duplicate_clusters)} clusters detected).")
        else:
            lines.append("• Duplicate package risk remains low.")

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
    ) -> list[str]:
        """Build the Runtime Governance section (v0.4.1)."""
        lines = [
            "## Runtime Governance",
            "",
        ]
        has_data = usage.installed_skills > 0 or usage.used_skills > 0
        if not has_data:
            lines.append("*No usage data available. Runtime governance analysis skipped.*")
            lines.append("")
            return lines

        # Most Used Skills
        # Display: | Skill | Uses | Views | Last Used |
        # Sort: use_count DESC
        used_pkgs = []
        for pkg_id, record in matched_usage.items():
            if record and (record.use_count > 0 or record.view_count > 0):
                used_pkgs.append((pkg_id, record))

        most_used_pkgs = sorted(used_pkgs, key=lambda x: x[1].use_count, reverse=True)

        lines.append("### Most Used Skills")
        lines.append("")
        lines.append("| Skill | Uses | Views | Last Used |")
        lines.append("| ----- | ---: | ----: | --------- |")
        for pkg_id, record in most_used_pkgs:
            last_used = record.last_used_at[:10] if record.last_used_at else "N/A"
            lines.append(f"| `{pkg_id}` | {record.use_count} | {record.view_count} | {last_used} |")
        lines.append("")

        # Recently Used Skills
        # Display: | Skill | Last Used |
        # Sort: last_used_at DESC
        recently_used_pkgs = [p for p in used_pkgs if p[1].last_used_at]
        recently_used_pkgs.sort(key=lambda x: x[1].last_used_at, reverse=True)

        lines.append("### Recently Used Skills")
        lines.append("")
        lines.append("| Skill | Last Used |")
        lines.append("| ----- | --------- |")
        for pkg_id, record in recently_used_pkgs:
            last_used = record.last_used_at[:10] if record.last_used_at else "N/A"
            lines.append(f"| `{pkg_id}` | {last_used} |")
        lines.append("")

        # Never Used Skills
        # Display: | Skill | Category |
        # Limit display: Top 20 entries
        # Show total count.
        lines.append("### Never Used Skills")
        lines.append("")
        lines.append(f"{usage.unused_skills} skills have never been used.")
        lines.append("")
        lines.append("| Skill | Category |")
        lines.append("| ----- | -------- |")
        for pkg_id, category in usage.never_used[:20]:
            lines.append(f"| `{pkg_id}` | {category} |")
        lines.append("")

        # Category Utilization
        # Display: | Category | Utilization | Used / Total |
        # Sort: utilization DESC
        lines.append("### Category Utilization")
        lines.append("")
        lines.append("| Category | Utilization | Used / Total |")
        lines.append("| -------- | ----------: | ------------ |")
        for cat_name, pct, used, total in usage.category_utilization:
            lines.append(f"| {cat_name} | {pct}% | {used} / {total} |")
        lines.append("")

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


def _generate_utilization_recommendations(
    usage: UsageAnalysis, total_packages: int,
) -> list[Recommendation]:
    """Generate utilization-based governance recommendations (v0.4.1)."""
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
                f"Only {usage.utilization_rate}% of installed skills are actively used. "
                f"{usage.unused_skills} skills have never been used."
            ),
            action="Consider archiving or removing unused skills. Review large unused packages before adding new skills.",
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

    return recs
