#!/usr/bin/env python3
"""
SAP Migration Post-Load Validator — CLI
Usage:
    python validate.py --source <csv> --target <csv/xlsx> [options]

Examples:
    python validate.py --source transformed_materials.csv --target s4hana_export.csv
    python validate.py --source data/mat.csv --target data/s4h.xlsx --output-dir results/
    python validate.py --source mat.csv --target s4h.csv --target-delimiter ";"
"""

import argparse
import sys
import os
from pathlib import Path
from datetime import datetime

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent))

from core.validator import MaterialValidator, MATERIAL_FIELD_MAP
from core.reporter import generate_excel_report, generate_html_report


def parse_args():
    p = argparse.ArgumentParser(
        description="SAP 4.7 → S/4HANA Material Master Post-Load Validator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--source", required=True,
                   help="Path to transformed CSV from SAP 4.7 (source)")
    p.add_argument("--target", required=True,
                   help="Path to exported file from S/4HANA Public Cloud (target)")
    p.add_argument("--source-delimiter", default=",",
                   help="CSV delimiter for source file (default: ,)")
    p.add_argument("--target-delimiter", default=",",
                   help="CSV delimiter for target file (default: ,)")
    p.add_argument("--output-dir", default="reports",
                   help="Directory for output reports (default: ./reports)")
    p.add_argument("--max-mismatch-rows", type=int, default=100,
                   help="Max mismatch rows captured per field (default: 100)")
    p.add_argument("--no-excel", action="store_true",
                   help="Skip Excel report generation")
    p.add_argument("--no-html", action="store_true",
                   help="Skip HTML report generation")
    p.add_argument("--list-fields", action="store_true",
                   help="Print the default field mapping and exit")
    return p.parse_args()


def main():
    args = parse_args()

    if args.list_fields:
        print("\nDefault Material Field Mapping (source → target):")
        print(f"  {'Source (CSV)':25s}  {'Target (S/4HANA)':30s}")
        print("  " + "-" * 57)
        for src, tgt in MATERIAL_FIELD_MAP.items():
            print(f"  {src:25s}  {tgt:30s}")
        print()
        return 0

    # Validate file existence
    for path, label in [(args.source, "Source"), (args.target, "Target")]:
        if not Path(path).exists():
            print(f"❌  {label} file not found: {path}")
            return 1

    print("\n" + "═" * 60)
    print("  SAP Material Master — Post-Load Validator")
    print("═" * 60)
    print(f"  Source : {args.source}")
    print(f"  Target : {args.target}")
    print("═" * 60 + "\n")

    validator = MaterialValidator()

    print("▶ Running validation…")
    result = validator.validate(
        source_path=args.source,
        target_path=args.target,
        source_delimiter=args.source_delimiter,
        target_delimiter=args.target_delimiter,
        max_mismatch_rows=args.max_mismatch_rows,
    )

    if result.errors:
        for e in result.errors:
            print(f"  ❌ ERROR: {e}")
        return 2

    # Print quick summary to console
    ss = result.summary_stats
    print(f"\n  Records   : {result.records_matched:,} matched "
          f"| {result.records_only_in_source:,} source-only "
          f"| {result.records_only_in_target:,} target-only")
    print(f"  Fields    : {ss['fields_passed']}/{ss['total_fields_validated']} passed "
          f"({ss['pass_rate_pct']}%)")
    print()

    # Print field table
    print(f"  {'Field':<22} {'Match%':>7}  {'Status'}")
    print("  " + "-" * 40)
    for fr in result.field_results:
        icon = "✅" if fr.status == "PASS" else "❌"
        print(f"  {fr.field_source:<22} {fr.match_pct:>6.1f}%  {icon} {fr.status}")

    # Generate reports
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "─" * 60)
    if not args.no_excel:
        xl_path = out_dir / f"validation_{ts}.xlsx"
        try:
            generate_excel_report(result, str(xl_path))
            print(f"  📊 Excel  : {xl_path}")
        except ImportError:
            print("  ⚠ Excel skipped (pip install openpyxl)")

    if not args.no_html:
        html_path = out_dir / f"validation_{ts}.html"
        generate_html_report(result, str(html_path))
        print(f"  🌐 HTML   : {html_path}")

    overall = result.overall_status
    icon = "✅" if overall == "PASS" else "❌"
    print(f"\n  {icon}  Overall Status: {overall}\n")

    return 0 if overall == "PASS" else 3


if __name__ == "__main__":
    sys.exit(main())
