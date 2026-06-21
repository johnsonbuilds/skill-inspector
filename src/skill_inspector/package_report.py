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

        # Package type distribution
        type_dist_lines: list[str] = []
        for t in AssetType:
            count = type_counts.get(t, 0)
            if count:
                pct = count / max(total_packages, 1) * 100
                type_dist_lines.append(f"- **{t.value}**: {count} ({pct:.0f}%)")

        # Largest packages (by total asset count)
        all_packages: list[tuple[Category, PackageClassification | None, SkillPackage]] = []
        for cat in categories:
            for pkg in cat.packages:
                pc = classifications.get(pkg.id)
                all_packages.append((cat, pc, pkg))

        largest = sorted(all_packages, key=lambda x: x[2].total_asset_count, reverse=True)[:10]

        # Most complex packages (by number of reference/template/script files)
        complex_pkgs = sorted(
            all_packages,
            key=lambda x: len(x[2].assets),
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

        # Governance findings
        findings: list[str] = []
        if total_packages > 0:
            exec_ratio = type_counts.get(AssetType.EXECUTABLE_SKILL, 0) / total_packages
            if exec_ratio < 0.3:
                findings.append(f"Low executable skill ratio ({exec_ratio:.0%}) — consider reviewing knowledge/reference packages")
            ref_ratio = type_counts.get(AssetType.REFERENCE, 0) / total_packages
            if ref_ratio > 0.3:
                findings.append(f"High reference material ratio ({ref_ratio:.0%}) — consider moving to a separate knowledge base")
        if duplicate_clusters:
            findings.append(f"Duplicate or overlapping skill packages detected ({len(duplicate_clusters)} clusters)")
        if not findings:
            findings.append("No major governance issues detected")

        # Recommendations
        recommendations: list[str] = [
            "Review low-confidence classifications and reclassify packages where needed",
        ]
        if duplicate_clusters:
            recommendations.append("Merge or archive highly overlapping skill packages in duplicate clusters")
        if any("reference" in f.lower() for f in findings):
            recommendations.append("Move broad reference material into a separate knowledge base")
        if any("executable" in f.lower() for f in findings):
            recommendations.append("Ensure each executable skill has clear inputs, outputs, and actionable procedures")
        recommendations.append("Periodically audit categories to ensure DESCRIPTION.md files are up to date")

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
            "## Package Type Distribution",
            "",
        ] + type_dist_lines + [
            "",
            "## Category Breakdown",
            "",
        ] + cat_breakdown + [
            "",
            "## Largest Packages",
            "",
            "| Rank | Package | Category | Assets |",
            "|---:|---|---|---:|",
        ]
        for rank, (cat, pc, pkg) in enumerate(largest, 1):
            type_str = pc.type.value if pc else "?"
            lines.append(f"| {rank} | `{pkg.id}` | {cat.name} | {pkg.total_asset_count} |")

        lines += [
            "",
            "## Most Complex Packages",
            "",
            "| Rank | Package | Category | References |",
            "|---:|---|---|---:|",
        ]
        for rank, (cat, pc, pkg) in enumerate(complex_pkgs[:10], 1):
            lines.append(f"| {rank} | `{pkg.id}` | {cat.name} | {len(pkg.assets)} |")

        lines += [
            "",
            "## Duplicate Skill Packages",
            "",
        ] + dup_lines + [
            "",
            "## Governance Findings",
            "",
        ] + [f"- {f}" for f in findings] + [
            "",
            "## Recommendations",
            "",
        ] + [f"- {r}" for r in recommendations]

        text = "\n".join(lines) + "\n"
        output.write_text(text, encoding="utf-8")
        return text
