from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
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

        if pkg_id in usage_records:
            record = usage_records[pkg_id]
        else:
            flat_name = pkg_id.rsplit("/", 1)[-1]
            if flat_name in usage_records:
                record = usage_records[flat_name]
            else:
                parts = pkg_id.rsplit("/", 1)
                if len(parts) == 2:
                    cat, name = parts
                    colon_key = f"{cat}:{name}"
                    if colon_key in usage_records:
                        record = usage_records[colon_key]

        result[pkg_id] = record

    return result


def is_package_used(record: UsageRecord | None) -> bool:
    """A package is considered used only when use_count > 0."""
    return bool(record and record.use_count > 0)


def is_recently_used(record: UsageRecord | None, days: int = 3) -> bool:
    """Return True when last_used_at falls within the trailing N-day window."""
    if not record or not record.last_used_at:
        return False

    try:
        last_used = datetime.fromisoformat(record.last_used_at.replace("Z", "+00:00")).date()
    except ValueError:
        return False

    delta = (date.today() - last_used).days
    return 0 <= delta <= days


def analyze_usage(
    usage_records: dict[str, UsageRecord],
    packages: list,
    categories: list,
) -> UsageAnalysis:
    """Perform full usage analysis and return aggregated results."""
    analysis = UsageAnalysis()
    analysis.installed_skills = len(packages)
    analysis.usage_records = usage_records

    pkg_ids = [p.id for p in packages]
    matched = match_usage_to_packages(usage_records, pkg_ids)

    cat_lookup: dict[str, str] = {}
    for cat in categories:
        for pkg in cat.packages:
            cat_lookup[pkg.id] = cat.name

    used_ids: list[str] = []
    unused_entries: list[tuple[str, str]] = []

    for pkg_id, record in matched.items():
        cat_name = cat_lookup.get(pkg_id, "unknown")
        if is_package_used(record):
            used_ids.append(pkg_id)
        else:
            unused_entries.append((pkg_id, cat_name))

    analysis.used_skills = len(used_ids)
    analysis.unused_skills = len(unused_entries)
    total = max(len(packages), 1)
    analysis.utilization_rate = round(analysis.used_skills / total * 100, 1)

    used_with_counts = [
        (pkg_id, matched[pkg_id].use_count if matched[pkg_id] else 0)
        for pkg_id in used_ids
    ]
    used_with_counts.sort(key=lambda x: x[1], reverse=True)
    analysis.most_used = used_with_counts

    recently: list[tuple[str, str | None]] = []
    for pkg_id in used_ids:
        rec = matched[pkg_id]
        if rec and rec.last_used_at and is_recently_used(rec, days=3):
            recently.append((pkg_id, rec.last_used_at[:10]))
    recently.sort(key=lambda x: x[1] or "", reverse=True)
    analysis.recently_used = recently

    analysis.never_used = unused_entries

    cat_stats: dict[str, dict[str, int]] = {}
    for pkg_id, record in matched.items():
        cat_name = cat_lookup.get(pkg_id, "unknown")
        if cat_name not in cat_stats:
            cat_stats[cat_name] = {"total": 0, "used": 0}
        cat_stats[cat_name]["total"] += 1
        if is_package_used(record):
            cat_stats[cat_name]["used"] += 1

    for cat_name, stats in cat_stats.items():
        if stats["total"] > 0:
            pct = round(stats["used"] / stats["total"] * 100)
            analysis.category_utilization.append((cat_name, pct, stats["used"], stats["total"]))
    analysis.category_utilization.sort(key=lambda x: (x[1], x[2], x[3]), reverse=True)

    return analysis
