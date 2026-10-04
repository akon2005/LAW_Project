#!/usr/bin/env python
"""
VIDHIVEDA dataset inspection (Step 4).

    python scripts/inspect_dataset.py                 # inspect the active dataset
    python scripts/inspect_dataset.py --samples 50
    python scripts/inspect_dataset.py --list           # list registered datasets
    python scripts/inspect_dataset.py --json report.json

Streams a bounded sample (never the whole corpus) and reports the actual
schema: configurations, splits, field names, types, missing-value percentage,
approximate text length, and the best identifier for text / outcome / court /
date / section fields. If a field cannot be found it is reported as missing —
it is never fabricated.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.dataset_service import (  # noqa: E402
    PRIMARY_DATASET,
    DatasetLoadError,
    get_dataset_config,
    list_datasets,
)
from app.services.schema_service import (  # noqa: E402
    build_dataset_report,
    detect_schema,
    resolve_field_mapping,
    sample_records,
)


def discover_configs_and_splits(hf_path: str) -> dict:
    """Best-effort listing of a dataset's configurations and splits."""
    info = {"configs": [], "splits": [], "error": None}
    try:
        from datasets import get_dataset_config_names, get_dataset_split_names

        try:
            info["configs"] = list(get_dataset_config_names(hf_path))
        except Exception as exc:  # gated repo, offline, ...
            info["error"] = str(exc)
        try:
            info["splits"] = list(get_dataset_split_names(hf_path))
        except Exception:
            pass
    except ImportError:
        info["error"] = "the 'datasets' package is not installed"
    return info


def print_report(report: dict, schema: dict, mapping: dict) -> None:
    line = "-" * 60
    print("VIDHIVEDA — Dataset Inspection")
    print(line)
    print(f"Dataset key:   {report['dataset_key']}")
    print(f"Hugging Face:  {report['hf_path']}")
    print(f"Source URL:    {report['source_url']}")
    print(f"Split:         {report['split']}")
    print(f"Kind:          {report['kind']}")
    print(f"Collection:    {report['collection']}")
    print(f"Records read:  {schema.get('records_sampled', 0)}")
    print(f"Fields found:  {schema.get('field_count', 0)}")
    print(line)

    if report.get("error"):
        print(f"ERROR while streaming: {report['error']}")
        print("The schema below may be incomplete.")
        print(line)

    print("Fields (missing %, types, avg text length):")
    for name, stats in sorted((schema.get("fields") or {}).items()):
        extra = f", avg_len={stats.get('avg_text_length')}" if stats.get("avg_text_length") else ""
        print(
            f"  - {name}: {stats.get('missing_pct')}% missing, "
            f"types={stats.get('types')}{extra}"
        )
    print(line)

    print("Detected field mapping (canonical -> upstream column):")
    for canonical, column in sorted(mapping.items()):
        print(f"  - {canonical}: {column or '(not found)'}")
    print(line)


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a registered legal dataset.")
    parser.add_argument("--dataset", default=PRIMARY_DATASET, help="registered dataset key")
    parser.add_argument("--samples", type=int, default=20, help="records to stream")
    parser.add_argument("--split", default=None)
    parser.add_argument("--list", action="store_true", help="list registered datasets")
    parser.add_argument("--json", default=None, help="write the full report as JSON")
    args = parser.parse_args()

    if args.list:
        print("Registered datasets:")
        for entry in list_datasets():
            state = "enabled" if entry["enabled"] else "disabled"
            print(f"  - {entry['key']} [{state}] ({entry['kind']}) -> {entry['hf_path']}")
            if entry.get("note"):
                print(f"      {entry['note']}")
        return 0

    try:
        config = get_dataset_config(args.dataset)
    except KeyError as exc:
        print(f"ERROR: {exc}")
        return 2

    report = build_dataset_report(args.dataset, count=args.samples, split=args.split)
    discovery = discover_configs_and_splits(config["hf_path"])
    report["configs"] = discovery["configs"]
    report["splits"] = discovery["splits"]
    if discovery["error"]:
        report["discovery_error"] = discovery["error"]

    try:
        records = sample_records(args.dataset, count=args.samples, split=args.split)
    except DatasetLoadError as exc:
        report["error"] = str(exc)
        print(f"ERROR: {exc}")
        print("Check network access / Hugging Face availability, then re-run.")
        if args.json:
            Path(args.json).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        return 3

    schema = detect_schema(records)
    mapping = resolve_field_mapping(args.dataset, sample_records=records)
    report["schema"] = schema
    report["field_mapping"] = mapping

    print_report(report, schema, mapping)
    if report.get("configs"):
        print(f"Configurations: {report['configs']}")
    if report.get("splits"):
        print(f"Splits:         {report['splits']}")

    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nFull report written to {args.json}")

    # Honest summary of label availability for the outcome model (Steps 16, 49).
    if not mapping.get("outcome"):
        print(
            "\nNo outcome/label field was detected. Outcome prediction is therefore "
            "unavailable for this dataset (no reliable labeled training set)."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
