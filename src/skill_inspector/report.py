from __future__ import annotations

from collections import Counter
from pathlib import Path

from .models import Asset, AssetType, Classification, DuplicateCluster


class ReportGenerator:
    def generate(self, assets: list[Asset], classifications: dict[str, Classification], clusters: list[DuplicateCluster], output: Path) -> str:
        counts = Counter(classifications[a.id].type for a in assets)
        findings = self._findings(assets, classifications, clusters)
        recommendations = self._recommendations(findings, clusters)
        lines = ["# Skill Inspector Report", "", "## Summary", "", f"Total assets: {len(assets)}", ""]
        for t in AssetType:
            lines.append(f"- {t.value}: {counts.get(t, 0)}")
        lines += ["", "## Classification Table", "", "| Asset | Type | Confidence | Reason |", "|---|---:|---:|---|"]
        for asset in assets:
            c = classifications[asset.id]
            lines.append(f"| {asset.name} | {c.type.value} | {c.confidence:.2f} | {c.reason.replace('|', '/')} |")
        lines += ["", "## Duplicate Clusters", ""]
        if clusters:
            for idx, cluster in enumerate(clusters, 1):
                lines.append(f"### Cluster {idx} (average similarity {cluster.average_similarity:.2f})")
                lines.extend(f"- {a.name} (`{a.id}`)" for a in cluster.assets)
                lines.append("")
        else:
            lines.append("No duplicate clusters detected.")
        lines += ["", "## Governance Findings", ""] + [f"- {f}" for f in findings]
        lines += ["", "## Recommendations", ""] + [f"- {r}" for r in recommendations]
        text = "\n".join(lines) + "\n"
        output.write_text(text, encoding="utf-8")
        return text

    def _findings(self, assets: list[Asset], classifications: dict[str, Classification], clusters: list[DuplicateCluster]) -> list[str]:
        total = max(len(assets), 1)
        counts = Counter(c.type for c in classifications.values())
        findings: list[str] = []
        if counts[AssetType.KNOWLEDGE] / total > 0.5:
            findings.append("Too many knowledge assets / high knowledge-to-skill ratio")
        if counts[AssetType.EXECUTABLE_SKILL] / total < 0.2:
            findings.append("Low executable skill ratio")
        if clusters:
            findings.append(f"Duplicate or overlapping assets detected ({len(clusters)} clusters)")
        if total > 30 and counts[AssetType.EXECUTABLE_SKILL] / total < 0.3:
            findings.append("Skill inflation detected")
        return findings or ["No major governance issues detected"]

    def _recommendations(self, findings: list[str], clusters: list[DuplicateCluster]) -> list[str]:
        recs = ["Review low-confidence classifications and reclassify assets where needed"]
        if clusters:
            recs.append("Merge or archive highly overlapping assets in duplicate clusters")
        if any("knowledge" in f.lower() for f in findings):
            recs.append("Move broad knowledge and reference material into a separate knowledge base")
        if any("executable" in f.lower() for f in findings):
            recs.append("Promote true executable procedures into skills with explicit inputs and outputs")
        return recs
