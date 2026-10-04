#!/usr/bin/env python
"""
Validate the VIDHIVEDA Open Knowledge Format bundle (OKF v0.2).

    python scripts/validate_okf.py
    python scripts/validate_okf.py --bundle knowledge --json

Reports total/valid/invalid documents, missing metadata, broken links, missing
provenance, duplicate ids, trust tiers, staleness and validation errors. Invalid
records are reported, never silently discarded.

Exit codes: 0 conformant, 1 non-conformant, 2 bundle missing.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import OKF_BUNDLE_DIR  # noqa: E402
from app.okf import OKFImporter, OKFValidator  # noqa: E402


def print_human(report: dict) -> None:
    print("VIDHIVEDA — OKF v0.2 validation")
    print("=" * 60)
    print(f"Bundle:            {report['bundle']}")
    print(
        f"OKF version:       {report['okf_version']} "
        f"(target {report['target_version']}, compatible={report['version_compatible']})"
    )
    print(f"Documents:         {report['documents_total']}")
    print(f"Concepts:          {report['concepts_total']}")
    print(f"Valid concepts:    {report['valid_concepts']}")
    print(f"Invalid documents: {report['invalid_concepts']}")
    print()

    print("Provenance")
    print("-" * 60)
    coverage = report["provenance"]
    print(
        f"  with sources: {coverage['with_sources']}/{coverage['total_concepts']} "
        f"({coverage['coverage'] * 100:.1f}%)"
    )
    print(
        f"  missing provenance: {len(report['missing_provenance'])}"
    )
    print(f"  missing sources[].resource: {len(report['missing_source_resource'])}")
    print(f"  duplicate source ids: {len(report['duplicate_source_ids'])}")
    print()

    print("Trust")
    print("-" * 60)
    for tier, count in report["trust"].items():
        print(f"  {tier}: {count}")
    print(f"  stale concepts: {len(report['stale_concepts'])}")
    print()

    print("Links")
    print("-" * 60)
    print(f"  broken internal links: {len(report['broken_links'])}")
    for broken in report["broken_links"][:20]:
        print(
            f"    {broken['concept_id']} -> {broken['target']} (line {broken['line']})"
        )
    if len(report["broken_links"]) > 20:
        print(f"    ... and {len(report['broken_links']) - 20} more")
    print()

    print("Types")
    print("-" * 60)
    for concept_type in report["types"]:
        print(f"  {concept_type}")
    print()

    if report["invalid_documents"] or report["structural_errors"]:
        print("Errors")
        print("-" * 60)
        for item in report["invalid_documents"]:
            for error in item["errors"]:
                print(f"  {item['concept_id']}: {error}")
        for error in report["structural_errors"]:
            print(f"  {error}")
        print()

    status = "CONFORMANT" if report["valid"] else "NON-CONFORMANT"
    print(f"Result: {status} (unreturned broken links / missing optional "
          "families do not break conformance — OKF §11)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an OKF v0.2 bundle.")
    parser.add_argument("--bundle", default=str(OKF_BUNDLE_DIR))
    parser.add_argument("--json", action="store_true", help="print the raw report")
    args = parser.parse_args()

    bundle_root = Path(args.bundle)
    if not bundle_root.is_dir():
        print(f"ERROR: bundle '{bundle_root}' does not exist.")
        print("Build it with: python scripts/build_okf_bundle.py")
        return 2

    documents = OKFImporter(bundle_root).load()
    report = OKFValidator(bundle_root, documents).validate()

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print_human(report)

    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
