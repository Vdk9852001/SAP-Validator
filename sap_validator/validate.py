#!/usr/bin/env python3
"""
SAP Migration Post-Load Validator — CLI

AUTO (default):
    python validate.py --source transformed.csv --target s4hana_export.csv

PREVIEW mapping + numeric detection without running:
    python validate.py --source mat.csv --target s4h.csv --show-mapping

OVERRIDE join key:
    python validate.py --source mat.csv --target s4h.csv --join-key WERKS

OVERRIDE tolerance for specific columns:
    python validate.py --source mat.csv --target s4h.csv --tolerance STPRS=0.05
    python validate.py --source mat.csv --target s4h.csv --tolerance BRGEW=0.002 --tolerance STPRS=0.05
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from core.validator import MaterialValidator
from core.reporter import generate_excel_report, generate_html_report


def parse_args():
    p = argparse.ArgumentParser(
        description="SAP 4.7 → S/4HANA Post-Load Validator (fully auto-detecting)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--source",            required=True)
    p.add_argument("--target",            required=True)
    p.add_argument("--source-delimiter",  default=",")
    p.add_argument("--target-delimiter",  default=",")
    p.add_argument("--join-key",          default=None)
    p.add_argument("--tolerance",         action="append", default=[],
                   metavar="COL=VALUE",
                   help="Override tolerance for a column e.g. --tolerance STPRS=0.05")
    p.add_argument("--output-dir",        default="reports")
    p.add_argument("--max-mismatch-rows", type=int, default=100)
    p.add_argument("--show-mapping",      action="store_true",
                   help="Preview auto-detected mapping and numerics then exit")
    p.add_argument("--no-excel",          action="store_true")
    p.add_argument("--no-html",           action="store_true")
    return p.parse_args()


def parse_tolerance_overrides(raw: list) -> dict:
    out = {}
    for item in raw:
        try:
            col, val = item.split("=", 1)
            out[col.strip().upper()] = float(val.strip())
        except ValueError:
            print(f"  ⚠  Ignoring bad --tolerance value: {item!r}  (expected COL=VALUE)")
    return out


def print_mapping(mapping):
    print(f"\n  Join key      : {mapping.join_key}")
    print(f"  Source columns: {mapping.total_source_cols}  |  "
          f"Target columns: {mapping.total_target_cols}")

    print(f"\n  ✅ Fields validated ({len(mapping.matched_fields)}):")
    for col in mapping.matched_fields:
        tag = ""
        if col in mapping.numeric_fields:
            tol = mapping.tolerance_map.get(col, "?")
            tag = f"  [numeric, tol ±{tol}]"
        print(f"     {col}{tag}")

    if mapping.source_only_fields:
        print(f"\n  ⚠  Source-only — skipped ({len(mapping.source_only_fields)}):")
        for col in mapping.source_only_fields:
            print(f"     {col}")

    if mapping.target_only_fields:
        print(f"\n  ℹ  Target-only — skipped ({len(mapping.target_only_fields)}):")
        for col in mapping.target_only_fields:
            print(f"     {col}")

    print(f"\n  🔢 Auto-detected numeric columns ({len(mapping.numeric_fields)}):")
    if mapping.numeric_fields:
        for col in mapping.numeric_fields:
            print(f"     {col:<20}  tolerance ±{mapping.tolerance_map[col]}")
    else:
        print("     (none)")
    print()


def main():
    args         = parse_args()
    tol_override = parse_tolerance_overrides(args.tolerance)

    for path, label in [(args.source, "Source"), (args.target, "Target")]:
        if not Path(path).exists():
            print(f"❌  {label} file not found: {path}")
            return 1

    print("\n" + "═" * 64)
    print("  SAP Material Master — Post-Load Validator  (Auto-Detect)")
    print("═" * 64)
    print(f"  Source : {args.source}")
    print(f"  Target : {args.target}")
    if tol_override:
        print(f"  Tolerance overrides: {tol_override}")
    print("═" * 64)

    validator = MaterialValidator(
        join_key=args.join_key,
        tolerance_map=tol_override or None,
    )

    # ── Show-mapping preview ─────────────────────────────────────────────────
    if args.show_mapping:
        import pandas as pd
        print("\n▶ Sampling files for column and numeric detection…")
        src_df = pd.read_csv(args.source, dtype=str, encoding="utf-8-sig",
                             delimiter=args.source_delimiter)
        tgt_df = pd.read_csv(args.target, dtype=str, encoding="utf-8-sig",
                             delimiter=args.target_delimiter)
        src_df.columns = src_df.columns.str.strip().str.upper()
        tgt_df.columns = tgt_df.columns.str.strip().str.upper()
        join_key = validator._detect_join_key(src_df, tgt_df)
        if not join_key:
            print("  ❌ No common join key found.")
            return 2
        _, mapping = validator._build_field_map(src_df, tgt_df, join_key)
        print_mapping(mapping)
        return 0

    # ── Full validation ──────────────────────────────────────────────────────
    print("\n▶ Auto-detecting columns, numerics, and tolerances…")
    result = validator.validate(
        source_path=args.source,
        target_path=args.target,
        source_delimiter=args.source_delimiter,
        target_delimiter=args.target_delimiter,
        max_mismatch_rows=args.max_mismatch_rows,
    )

    if result.errors:
        for e in result.errors:
            print(f"\n  ❌ ERROR: {e}")
        return 2

    if result.mapping:
        print_mapping(result.mapping)

    ss = result.summary_stats
    print(f"  Records : {result.records_matched:,} matched "
          f"| {result.records_only_in_source:,} source-only "
          f"| {result.records_only_in_target:,} target-only")
    print(f"  Fields  : {ss['fields_passed']}/{ss['total_fields_validated']} "
          f"passed ({ss['pass_rate_pct']}%)\n")

    print(f"  {'Field':<22} {'Type':<10} {'Tolerance':>10}  {'Match%':>7}  Status")
    print("  " + "─" * 60)
    for fr in result.field_results:
        icon    = "✅" if fr.status == "PASS" else "❌"
        ftype   = "numeric" if fr.is_numeric else "string"
        tol_str = f"±{fr.tolerance_used}" if fr.is_numeric else "—"
        print(f"  {fr.field_source:<22} {ftype:<10} {tol_str:>10}  "
              f"{fr.match_pct:>6.1f}%  {icon} {fr.status}")

    ts      = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "─" * 64)
    if not args.no_excel:
        xl_path = out_dir / f"validation_{ts}.xlsx"
        try:
            generate_excel_report(result, str(xl_path))
            print(f"  📊 Excel : {xl_path}")
        except ImportError:
            print("  ⚠ Excel skipped (pip install openpyxl)")

    if not args.no_html:
        html_path = out_dir / f"validation_{ts}.html"
        generate_html_report(result, str(html_path))
        print(f"  🌐 HTML  : {html_path}")

    icon = "✅" if result.overall_status == "PASS" else "❌"
    print(f"\n  {icon}  Overall: {result.overall_status}\n")
    return 0 if result.overall_status == "PASS" else 3


if __name__ == "__main__":
    sys.exit(main())
