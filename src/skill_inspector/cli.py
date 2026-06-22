from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from .duplicates import DuplicateDetector
from .hermes import HermesAdapter
from .llm import EmbeddingClient, LLMClassifier
from .package_classifier import PackageClassifier
from .package_duplicates import PackageDuplicateDetector
from .package_report import PackageReportGenerator
from .report import ReportGenerator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skill-inspector", description="Audit Hermes skill libraries."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    scan_pkg = sub.add_parser(
        "scan-packages",
        help="Scan Hermes skills (package-aware) and generate report.md",
    )
    scan_pkg.add_argument(
        "--data-dir",
        default="/opt/data",
        help="Directory containing config.yaml and skills/ (default: /opt/data)",
    )
    scan_pkg.add_argument(
        "--output", default="report.md", help="Report path (default: report.md)"
    )
    scan_pkg.add_argument(
        "--duplicate-threshold",
        type=float,
        default=0.82,
        help="Cosine similarity threshold for duplicate clusters",
    )

    health = sub.add_parser("health", help="Generate health report only (v0.3)")
    health.add_argument(
        "--data-dir",
        default="/opt/data",
        help="Directory containing config.yaml and skills/ (default: /opt/data)",
    )
    health.add_argument(
        "--output",
        default="health-report.md",
        help="Report path (default: health-report.md)",
    )
    health.add_argument(
        "--duplicate-threshold",
        type=float,
        default=0.82,
        help="Cosine similarity threshold for duplicate clusters",
    )

    return parser


def scan_packages(args: argparse.Namespace) -> int:
    """Package-aware scan (v0.1.5+)."""
    adapter = HermesAdapter(Path(args.data_dir))
    model_config = adapter.load_model_config()

    # Discover packages
    categories = adapter.discover_packages()
    total_packages = sum(cat.package_count for cat in categories)
    total_assets = sum(
        pkg.total_asset_count for cat in categories for pkg in cat.packages
    )
    print(f"Categories Found: {len(categories)}")
    print(f"Skill Packages: {total_packages}")
    print(f"Total Assets: {total_assets}\n")

    # Classify packages
    classifier = PackageClassifier(model_config)
    classifications = classifier.classify_packages(categories)
    pkg_classes = list(classifications.values())
    type_counts = Counter(pc.type for pc in pkg_classes)

    print("Package Type Distribution:")
    for t in type_counts:
        print(f"  {t.value}: {type_counts[t]}")
    print()

    # Detect duplicates
    all_packages = [pkg for cat in categories for pkg in cat.packages]
    pkg_dup_detector = PackageDuplicateDetector(
        EmbeddingClient(model_config), args.duplicate_threshold
    )
    dup_clusters = pkg_dup_detector.detect(all_packages)
    print(f"Duplicate Package Clusters: {len(dup_clusters)}\n")

    # Generate report
    generator = PackageReportGenerator()
    generator.generate(categories, classifications, dup_clusters, Path(args.output))
    print("Report written: " + str(Path(args.output)))
    return 0


def health_cmd(args: argparse.Namespace) -> int:
    """Health report only (v0.3)."""
    adapter = HermesAdapter(Path(args.data_dir))
    model_config = adapter.load_model_config()

    # Discover packages
    categories = adapter.discover_packages()
    total_packages = sum(cat.package_count for cat in categories)
    print(f"Categories Found: {len(categories)}")
    print(f"Skill Packages: {total_packages}\n")

    # Classify packages
    classifier = PackageClassifier(model_config)
    classifications = classifier.classify_packages(categories)
    pkg_classes = list(classifications.values())
    type_counts = Counter(pc.type for pc in pkg_classes)

    print("Package Type Distribution:")
    for t in type_counts:
        print(f"  {t.value}: {type_counts[t]}")
    print()

    # Detect duplicates
    all_packages = [pkg for cat in categories for pkg in cat.packages]
    pkg_dup_detector = PackageDuplicateDetector(
        EmbeddingClient(model_config), args.duplicate_threshold
    )
    dup_clusters = pkg_dup_detector.detect(all_packages)
    print(f"Duplicate Package Clusters: {len(dup_clusters)}\n")

    # Generate health report
    generator = PackageReportGenerator()
    generator.generate(categories, classifications, dup_clusters, Path(args.output))
    print("Health report written: " + str(Path(args.output)))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "scan-packages":
        return scan_packages(args)
    if args.command == "health":
        return health_cmd(args)
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    sys.exit(main())
