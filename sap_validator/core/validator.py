"""
SAP Migration Post-Load Validator
Compares transformed CSV (source) against S/4HANA exported file (target)
for Material Master data validation.
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Optional
import logging

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Field mapping: CSV column  →  S/4HANA column
# Edit this to match your actual file headers
# ──────────────────────────────────────────────
MATERIAL_FIELD_MAP = {
    # CSV (source)          S/4HANA export (target)
    "MATNR":               "Material",
    "MAKTX":               "Material Description",
    "MTART":               "Material Type",
    "MATKL":               "Material Group",
    "MEINS":               "Base Unit of Measure",
    "MEINH":               "Order Unit",
    "BRGEW":               "Gross Weight",
    "NTGEW":               "Net Weight",
    "GEWEI":               "Weight Unit",
    "VOLUM":               "Volume",
    "VOLEH":               "Volume Unit",
    "BISMT":               "Old Material Number",
    "MFRPN":               "Manufacturer Part Number",
    "WERKS":               "Plant",
    "LGORT":               "Storage Location",
    "EKGRP":               "Purchasing Group",
    "DISPO":               "MRP Controller",
    "DISMM":               "MRP Type",
    "MINBE":               "Reorder Point",
    "EISBE":               "Safety Stock",
    "STPRS":               "Standard Price",
    "VPRSV":               "Price Control",
    "PEINH":               "Price Unit",
    "WAERS":               "Currency",
}

# Fields where numeric tolerance is allowed (±)
NUMERIC_TOLERANCE_MAP = {
    "BRGEW": 0.001,
    "NTGEW": 0.001,
    "VOLUM": 0.001,
    "STPRS": 0.01,
    "MINBE": 0.0,
    "EISBE": 0.0,
}

# Key field used to join source & target
JOIN_KEY_SOURCE = "MATNR"
JOIN_KEY_TARGET = "Material"


@dataclass
class FieldResult:
    field_source: str
    field_target: str
    total_records: int
    matched: int
    mismatched: int
    missing_in_target: int
    missing_in_source: int
    mismatch_details: list = field(default_factory=list)

    @property
    def match_pct(self) -> float:
        if self.total_records == 0:
            return 0.0
        return round(self.matched / self.total_records * 100, 2)

    @property
    def status(self) -> str:
        if self.mismatch_details or self.missing_in_target or self.missing_in_source:
            return "FAIL"
        return "PASS"


@dataclass
class ValidationResult:
    source_file: str
    target_file: str
    total_source_records: int
    total_target_records: int
    records_matched: int          # key found in both
    records_only_in_source: int
    records_only_in_target: int
    field_results: list[FieldResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def overall_status(self) -> str:
        if self.errors:
            return "ERROR"
        failing = [f for f in self.field_results if f.status == "FAIL"]
        return "FAIL" if failing else "PASS"

    @property
    def summary_stats(self) -> dict:
        total_fields = len(self.field_results)
        passed = sum(1 for f in self.field_results if f.status == "PASS")
        return {
            "total_fields_validated": total_fields,
            "fields_passed": passed,
            "fields_failed": total_fields - passed,
            "pass_rate_pct": round(passed / total_fields * 100, 1) if total_fields else 0,
        }


class MaterialValidator:
    """
    Validates Material Master migration from SAP 4.7 CSV → S/4HANA export file.
    """

    def __init__(
        self,
        field_map: dict = None,
        tolerance_map: dict = None,
        join_key_source: str = JOIN_KEY_SOURCE,
        join_key_target: str = JOIN_KEY_TARGET,
    ):
        self.field_map = field_map or MATERIAL_FIELD_MAP
        self.tolerance_map = tolerance_map or NUMERIC_TOLERANCE_MAP
        self.join_key_source = join_key_source
        self.join_key_target = join_key_target

    # ── Public entry point ──────────────────────────────────────────────────
    def validate(
        self,
        source_path: str,
        target_path: str,
        source_delimiter: str = ",",
        target_delimiter: str = ",",
        max_mismatch_rows: int = 100,
    ) -> ValidationResult:
        """
        Load source CSV and target export file, run all validations,
        return a ValidationResult.
        """
        errors = []

        # Load files
        try:
            src_df = self._load_file(source_path, source_delimiter)
        except Exception as e:
            return ValidationResult(
                source_file=source_path, target_file=target_path,
                total_source_records=0, total_target_records=0,
                records_matched=0, records_only_in_source=0,
                records_only_in_target=0,
                errors=[f"Cannot load source file: {e}"]
            )

        try:
            tgt_df = self._load_file(target_path, target_delimiter)
        except Exception as e:
            return ValidationResult(
                source_file=source_path, target_file=target_path,
                total_source_records=len(src_df), total_target_records=0,
                records_matched=0, records_only_in_source=len(src_df),
                records_only_in_target=0,
                errors=[f"Cannot load target file: {e}"]
            )

        # Normalise key columns
        src_df = self._normalise_key(src_df, self.join_key_source)
        tgt_df = self._normalise_key(tgt_df, self.join_key_target)

        # Count key overlap
        src_keys = set(src_df[self.join_key_source].dropna())
        tgt_keys = set(tgt_df[self.join_key_target].dropna())
        matched_keys = src_keys & tgt_keys
        only_src = src_keys - tgt_keys
        only_tgt = tgt_keys - src_keys

        # Merge on key for field-level comparison
        merged = src_df.merge(
            tgt_df,
            left_on=self.join_key_source,
            right_on=self.join_key_target,
            how="inner",
            suffixes=("_src", "_tgt"),
        )

        # Run per-field validation
        field_results = []
        for src_col, tgt_col in self.field_map.items():
            if src_col == self.join_key_source:
                continue  # skip join key itself
            if src_col not in src_df.columns and tgt_col not in tgt_df.columns:
                continue  # field not present in either file — skip silently
            fr = self._validate_field(
                merged, src_col, tgt_col, max_mismatch_rows
            )
            if fr:
                field_results.append(fr)

        return ValidationResult(
            source_file=source_path,
            target_file=target_path,
            total_source_records=len(src_df),
            total_target_records=len(tgt_df),
            records_matched=len(matched_keys),
            records_only_in_source=len(only_src),
            records_only_in_target=len(only_tgt),
            field_results=field_results,
            errors=errors,
        )

    # ── Helpers ─────────────────────────────────────────────────────────────
    def _load_file(self, path: str, delimiter: str) -> pd.DataFrame:
        if path.endswith(".xlsx") or path.endswith(".xls"):
            df = pd.read_excel(path, dtype=str)
        else:
            df = pd.read_csv(path, delimiter=delimiter, dtype=str, encoding="utf-8-sig")
        df.columns = df.columns.str.strip()
        df = df.apply(lambda col: col.map(lambda x: x.strip() if isinstance(x, str) else x))
        return df

    def _normalise_key(self, df: pd.DataFrame, col: str) -> pd.DataFrame:
        if col in df.columns:
            # SAP material numbers are often zero-padded to 18 chars
            df[col] = df[col].astype(str).str.strip().str.lstrip("0").str.upper()
        return df

    def _validate_field(
        self, merged: pd.DataFrame, src_col: str, tgt_col: str, max_rows: int
    ) -> Optional[FieldResult]:
        # Determine actual column names after merge suffixes
        src_actual = src_col + "_src" if src_col + "_src" in merged.columns else src_col
        tgt_actual = tgt_col + "_tgt" if tgt_col + "_tgt" in merged.columns else tgt_col

        src_present = src_actual in merged.columns
        tgt_present = tgt_actual in merged.columns

        if not src_present and not tgt_present:
            return None

        total = len(merged)
        mismatches = []
        matched = 0
        miss_src = 0
        miss_tgt = 0

        tolerance = self.tolerance_map.get(src_col)

        for _, row in merged.iterrows():
            sv = row.get(src_actual, np.nan) if src_present else np.nan
            tv = row.get(tgt_actual, np.nan) if tgt_present else np.nan
            mat_num = row.get(self.join_key_source, "")

            sv_null = pd.isna(sv) or str(sv).strip() in ("", "nan", "NaN", "None")
            tv_null = pd.isna(tv) or str(tv).strip() in ("", "nan", "NaN", "None")

            if sv_null and tv_null:
                matched += 1
                continue
            if sv_null:
                miss_src += 1
                if len(mismatches) < max_rows:
                    mismatches.append({
                        "material": mat_num,
                        "source_value": "(blank)",
                        "target_value": str(tv),
                        "issue": "Missing in source",
                    })
                continue
            if tv_null:
                miss_tgt += 1
                if len(mismatches) < max_rows:
                    mismatches.append({
                        "material": mat_num,
                        "source_value": str(sv),
                        "target_value": "(blank)",
                        "issue": "Missing in target",
                    })
                continue

            # Numeric comparison with tolerance
            if tolerance is not None:
                try:
                    sv_f = float(str(sv).replace(",", "."))
                    tv_f = float(str(tv).replace(",", "."))
                    if abs(sv_f - tv_f) <= tolerance:
                        matched += 1
                    else:
                        if len(mismatches) < max_rows:
                            mismatches.append({
                                "material": mat_num,
                                "source_value": sv_f,
                                "target_value": tv_f,
                                "issue": f"Δ = {abs(sv_f-tv_f):.4f} (tolerance ±{tolerance})",
                            })
                    continue
                except ValueError:
                    pass  # fall through to string compare

            # String comparison (case-insensitive, strip)
            if str(sv).strip().upper() == str(tv).strip().upper():
                matched += 1
            else:
                if len(mismatches) < max_rows:
                    mismatches.append({
                        "material": mat_num,
                        "source_value": str(sv),
                        "target_value": str(tv),
                        "issue": "Value mismatch",
                    })

        mismatched = total - matched - miss_src - miss_tgt

        return FieldResult(
            field_source=src_col,
            field_target=tgt_col,
            total_records=total,
            matched=matched,
            mismatched=max(mismatched, len([m for m in mismatches if m["issue"] == "Value mismatch"])),
            missing_in_target=miss_tgt,
            missing_in_source=miss_src,
            mismatch_details=mismatches,
        )
