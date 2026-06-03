# SAP Migration Post-Load Validator
## Material Master | SAP 4.7 → S/4HANA Public Cloud

Compares your **transformed CSV** (source) against an **S/4HANA exported file** (target)
and produces an Excel + HTML report with field-level pass/fail analysis.

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run validation
python validate.py \
  --source  path/to/transformed_materials.csv \
  --target  path/to/s4hana_export.csv \
  --output-dir reports/
```

Reports are saved to `reports/validation_<timestamp>.xlsx` and `.html`.

---

## What It Validates

| Check | Description |
|-------|-------------|
| **Record count** | Total rows in source vs target |
| **Key matching** | Which material numbers exist in both / only one side |
| **Field values** | Per-field comparison for all mapped fields |
| **Numeric tolerance** | Weights, prices compared with configurable ±tolerance |
| **Blank detection** | Flags fields present in one file but blank in the other |

### Fields Validated (default mapping)

| Source (CSV) | Target (S/4HANA Export) |
|---|---|
| MATNR | Material |
| MAKTX | Material Description |
| MTART | Material Type |
| MATKL | Material Group |
| MEINS | Base Unit of Measure |
| BRGEW | Gross Weight |
| NTGEW | Net Weight |
| STPRS | Standard Price |
| VPRSV | Price Control |
| WERKS | Plant |
| LGORT | Storage Location |
| DISMM | MRP Type |
| DISPO | MRP Controller |
| … and more | |

Run `python validate.py --list-fields` for the full list.

---

## CLI Options

```
--source              Path to transformed CSV (SAP 4.7 extract)         [required]
--target              Path to S/4HANA exported file (CSV or XLSX)       [required]
--source-delimiter    Delimiter for source file  (default: ,)
--target-delimiter    Delimiter for target file  (default: ,)
--output-dir          Output folder for reports  (default: ./reports)
--max-mismatch-rows   Max mismatch rows per field in report (default: 100)
--no-excel            Skip Excel report
--no-html             Skip HTML report
--list-fields         Print field mapping and exit
```

---

## Customising the Field Mapping

Edit `core/validator.py` → `MATERIAL_FIELD_MAP`:

```python
MATERIAL_FIELD_MAP = {
    "MATNR": "Material",          # source_column: target_column
    "MAKTX": "Material Description",
    # Add your own fields here…
}
```

Adjust numeric tolerance (e.g. for weights or prices):

```python
NUMERIC_TOLERANCE_MAP = {
    "BRGEW": 0.001,   # ±0.001 kg
    "STPRS": 0.01,    # ±0.01 currency unit
}
```

---

## S/4HANA Export Instructions

In S/4HANA Public Cloud Migration Cockpit:
1. Go to **Material** migration object → **Loaded Data**
2. Use **Download** / **Export to Spreadsheet**
3. Save as CSV or XLSX

Or use **Fiori App: Manage Materials** → Export list view.

---

## Output Reports

### Excel Workbook
- **Summary** tab — run metadata, record counts, field-level pass/fail table
- **FAIL_<field>** tab — one tab per failing field with full mismatch detail

### HTML Report
- Self-contained, open in any browser
- Cards showing key metrics
- Colour-coded field table
- Expandable mismatch details per field

---

## Exit Codes
| Code | Meaning |
|------|---------|
| 0 | All validations PASSED |
| 1 | File not found |
| 2 | Fatal error (cannot parse file) |
| 3 | Validation completed but FAILED |

---

## Sample Data

```bash
python generate_samples.py   # creates sample_data/*.csv
python validate.py --source sample_data/source_materials.csv \
                   --target sample_data/target_s4hana_export.csv
```
