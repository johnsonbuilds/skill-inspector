from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class UsageRecord:
    """Normalized usage data for a single skill."""
    skill_id: str
    use_count: int
    view_count: int
    last_used_at: str | None = None
    last_viewed_at: str | None = None


@dataclass
class UsageAnalysis:
    """Aggregated usage analysis results."""
    installed_skills: int = 0
    used_skills: int = 0
    unused_skills: int = 0
    utilization_rate: float = 0.0
    most_used: list[tuple[str, int]] = field(default_factory=list)  # (skill_id, use_count)
    recently_used: list[tuple[str, str | None]] = field(default_factory=list)  # (skill_id, last_used_date)
    never_used: list[tuple[str, str]] = field(default_factory=list)  # (skill_id, category)
    category_utilization: list[tuple[str, float, int, int]] = field(default_factory=list)  # (category, pct, used, total)
    usage_records: dict[str, UsageRecord] = field(default_factory=dict)


USAGE_JSON_PATHS = [
    Path.home() / ".hermes" / "skills" / ".usage.json",
    Path("/opt/data/skills/.usage.json"),
]


def _find_usage_json() -> Path | None:
    """Find the first existing usage.json file."""
    for p in USAGE_JSON_PATHS:
        if p.exists():
            return p
    return None


def load_usage_data(path: Path | None = None) -> dict[str, UsageRecord]:
    """Load and normalize usage data from .usage.json.

    Returns a dict mapping skill name (flat) -> UsageRecord.
    """
    if path is None:
        path = _find_usage_json()
    if path is None or not path.exists():
        return {}

    raw = json.loads(path.read_text(encoding="utf-8"))
    records: dict[str, UsageRecord] = {}
    for skill_name, data in raw.items():
        records[skill_name] = UsageRecord(
            skill_id=skill_name,
            use_count=int(data.get("use_count", 0)),
            view_count=int(data.get("view_count", 0)),
            last_used_at=data.get("last_used_at"),
            last_viewed_at=data.get("last_viewed_at"),
        )
    return records


def match_usage_to_packages(
    usage_records: dict[str, UsageRecord],
    installed_ids: list[str],
) -> dict[str, UsageRecord | None]:
    """Match usage records to installed package IDs.

    Matching strategy:
    - For flat package IDs (no '/'), match directly.
    - For scoped package IDs ('category/name'), extract the name part and match.
    - Also try matching 'category:name' format (colon-separated) from usage keys.

    Returns dict mapping package_id -> UsageRecord or None.
    """
    result: dict[str, UsageRecord | None] = {}

    for pkg_id in installed_ids:
        record = None

        # Strategy 1: exact match (root-level skills like 'dogfood')
        if pkg_id in usage_records:
            record = usage_records[pkg_id]
        else:
            # Strategy 2: extract last component and match
            # e.g., 'devops/agent-skill-governance' -> 'agent-skill-governance'
            flat_name = pkg_id.rsplit("/", 1)[-1]
            if flat_name in usage_records:
                record = usage_records[flat_name]
            else:
                # Strategy 3: try 'category:name' format
                parts = pkg_id.rsplit("/", 1)
                if len(parts) == 2:
                    cat, name = parts
                    colon_key = f"{cat}:{name}"
                    if colon_key in usage_records:
                        record = usage_records[colon_key]

        result[pkg_id] = record

    return result


def analyze_usage(
    usage_records: dict[str, UsageRecord],
    packages: list,  # SkillPackage objects
    categories: list,  # Category objects
) -> UsageAnalysis:
    """Perform full usage analysis and return aggregated results."""
    analysis = UsageAnalysis()
    analysis.installed_skills = len(packages)

    # Match usage to packages
    pkg_ids = [p.id for p in packages]
    matched = match_usage_to_packages(usage_records, pkg_ids)

    # Build category lookup
    cat_lookup: dict[str, str] = {}
    for cat in categories:
        for pkg in cat.packages:
            cat_lookup[pkg.id] = cat.name

    used_ids: list[str] = []
    unused_entries: list[tuple[str, str]] = []  # (pkg_id, category)

    for pkg_id, record in matched.items():
        cat_name = cat_lookup.get(pkg_id, "unknown")
        if record and (record.use_count > 0 or record.view_count > 0):
            used_ids.append(pkg_id)
        else:
            unused_entries.append((pkg_id, cat_name))

    analysis.used_skills = len(used_ids)
    analysis.unused_skills = len(unused_entries)
    total = max(len(packages), 1)
    analysis.utilization_rate = round(analysis.used_skills / total * 100, 1)

    # Most used: sort by use_count DESC
    used_with_counts = [
        (pkg_id, (matched[pkg_id].use_count if matched[pkg_id] else 0))
        for pkg_id in used_ids
    ]
    used_with_counts.sort(key=lambda x: x[1], reverse=True)
    analysis.most_used = used_with_counts

    # Recently used: sort by last_used_at DESC
    recently: list[tuple[str, str | None]] = []
    for pkg_id in used_ids:
        rec = matched[pkg_id]
        if rec and rec.last_used_at:
            date_str = rec.last_used_at[:10]  # YYYY-MM-DD
            recently.append((pkg_id, date_str))
    recently.sort(key=lambda x: x[1] or "", reverse=True)
    analysis.recently_used = recently

    # Never used: limited to first 20
    analysis.never_used = unused_entries[:20]

    # Category utilization
    cat_stats: dict[str, dict[str, int]] = {}
    for pkg_id, record in matched.items():
        cat_name = cat_lookup.get(pkg_id, "unknown")
        if cat_name not in cat_stats:
            cat_stats[cat_name] = {"total": 0, "used": 0}
        cat_stats[cat_name]["total"] += 1
        if record and (record.use_count > 0 or record.view_count > 0):
            cat_stats[cat_name]["used"] += 1

    for cat_name, stats in cat_stats.items():
        if stats["total"] > 0:
            pct = round(stats["used"] / stats["total"] * 100)
            analysis.category_utilization.append((cat_name, pct, stats["used"], stats["total"]))
    analysis.category_utilization.sort(key=lambda x: x[1], reverse=True)

    return analysis
