from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from .duplicates import DuplicateDetector
from .hermes import HermesAdapter
from .llm import EmbeddingClient, LLMClassifier
from .report import ReportGenerator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="skill-inspector", description="Audit Hermes skill libraries.")
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan", help="Scan Hermes skills and generate report.md")
    scan.add_argument("--data-dir", default="/opt/data", help="Directory containing config.yaml and skills/ (default: /opt/data)")
    scan.add_argument("--output", default="report.md", help="Report path (default: report.md)")
    scan.add_argument("--duplicate-threshold", type=float, default=0.82, help="Cosine similarity threshold for duplicate clusters")
    return parser


def scan(args: argparse.Namespace) -> int:
    adapter = HermesAdapter(Path(args.data_dir))
    model_config = adapter.load_model_config()
    assets = adapter.discover_assets()
    classifier = LLMClassifier(model_config)
    classifications = {}
    for asset in assets:
        classifications[asset.id] = classifier.classify(asset)
    clusters = DuplicateDetector(EmbeddingClient(model_config), args.duplicate_threshold).detect(assets)
    ReportGenerator().generate(assets, classifications, clusters, Path(args.output))
    counts = Counter(c.type.value for c in classifications.values())
    print(f"Assets Found: {len(assets)}\n")
    for name in ["Knowledge", "Workflow", "Preference", "Executable Skill", "Reference Material", "Unknown"]:
        print(f"{name}: {counts.get(name, 0)}")
    print(f"\nDuplicate Clusters: {len(clusters)}\n")
    print("Report written: " + str(Path(args.output)))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "scan":
        return scan(args)
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    sys.exit(main())
