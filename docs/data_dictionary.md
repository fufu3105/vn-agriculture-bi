# Data Dictionary

## 1. Dataset Overview

This document defines the datasets used in the **Vietnam Agriculture Business Intelligence** project, including their sources, structures, data types, measurement units, preprocessing rules, and known limitations.

The project follows a three-layer data architecture:

- **Raw (`data/raw/`):** Original datasets collected from external sources.
- **Processed (`data/processed/`):** Cleaned and standardized datasets shared across business problems.
- **Analytics (`data/analytics/`):** Derived indicators, aggregated tables, and analytical results produced independently for each business problem.

The primary agricultural dataset contains annual rice statistics at the provincial level in Vietnam from 2010 to 2024.

**Dataset information**

| Property | Description |
|---|---|
| Dataset name | Vietnam Provincial Rice Statistics |
| Source | National Statistics Office of Vietnam (NSO) |
| Temporal coverage | 2010–2024 |
| Temporal granularity | Annual |
| Geographic granularity | Province |
| Geographic coverage | 63 provinces/cities under the historical classification |
| Number of records | 945 |
| Storage format | Apache Parquet |
| Primary analytical key | `province_id`, `year` |
| Data file | `data/processed/agriculture/rice_province_year/rice_province_year.parquet` |
| Quality report | `data/processed/agriculture/quality_report.json` |

The dataset serves as the shared agricultural data foundation for BP1, BP2, BP3, and BP4.

## 2. Data Sources

The agricultural data originates from three official NSO statistical tables.

| Table ID | Original file | Description | Original unit |
|---|---|---|---|
| V06.13 | `nso_V06.13_2010_2024.xlsx` | Annual rice cultivated area by province | Thousand hectares |
| V06.14 | `nso_V06.14_2010_2024.xlsx` | Annual rice yield by province | Quintals/hectare |
| V06.15 | `nso_V06.15_2010_2024.xlsx` | Annual rice production by province | Thousand tons |

**Source:** https://www.nso.gov.vn/nong-lam-nghiep-va-thuy-san/

The original Excel files are stored in `data/raw/agriculture/` and are preserved without manual modification.

Geographical classification is supported by `data/vietnam_regions_provinces.json`.

## 3. Processed Data Schema

**Dataset:** `rice_province_year`

Each record represents one province in one statistical year.

| Column | Data Type | Unit | Description |
|---|---|---|---|
| `year` | Integer | Year | Statistical reporting year |
| `province_id` | Integer | — | Project identifier assigned in JSON order, from 1 to 63 |
| `province_name` | String | — | Standardized province name |
| `region` | String | — | Geographical region |
| `rice_area_ha` | Double | ha | Annual rice cultivated area |
| `rice_yield_ton_ha` | Double | tons/ha | Annual rice yield |
| `rice_production_ton` | Double | tons | Annual rice production |

**Notes:**

- `rice_area_ha` represents annual cultivated area, which may include multiple rice cropping seasons within the same year.
- `rice_yield_ton_ha` represents rice production per unit of cultivated area.
- `rice_production_ton` represents the officially reported annual rice production.
- Measurements may be null. Unmatched provinces retain their source names with null `province_id` and `region`, and generate warnings.

## 4. Data Standardization

### 4.1. Measurement Unit Conversion

The original NSO tables use different measurement units.

| Column | Original unit | Standardized unit | Conversion |
|---|---|---|---|
| `rice_area_ha` | Thousand hectares | Hectares | Original value × 1,000 |
| `rice_yield_ton_ha` | Quintals/hectare | Tons/hectare | Original value ÷ 10 |
| `rice_production_ton` | Thousand tons | Tons | Original value × 1,000 |

All converted values are stored as floating-point numbers.

### 4.2. Temporal Standardization

- All years are represented as four-digit integers.
- The processed dataset covers 2010–2024.
- Data is organized at annual granularity.
- Missing observations must not be fabricated.

### 4.3. Geographical Standardization

Province names are standardized to support consistent joining across data sources.

The geographical reference file is:

`data/vietnam_regions_provinces.json`

Province matching normalizes case, accents, whitespace, dash variants, and the `TP.` prefix. The output uses names from the reference when matched.

`province_id` counts from 1 across regions and their province lists in the current JSON order, continuing across region boundaries. For example, Hà Giang = 1, Hà Nội = 16, and Cà Mau = 63. Reordering or inserting entries changes subsequent IDs. The report stores the reference hash and the name-to-ID mapping.

The project uses seven geographical regions:

1. Trung du và miền núi phía Bắc
2. Đồng bằng sông Hồng
3. Bắc Trung Bộ
4. Duyên hải Nam Trung Bộ
5. Tây Nguyên
6. Đông Nam Bộ
7. Đồng bằng sông Cửu Long

Historical administrative boundaries must be considered when integrating datasets from different periods.

### 4.4. Dataset Integration

The three NSO datasets are full-outer joined on normalized `province_key` and `year`, after checking each source for duplicate keys. The reference then supplies `province_id`, the standardized name, and the region. Missing measurements remain null. National and regional total rows are excluded from the provincial dataset.

## 5. Data Quality

The following quality checks are applied during preprocessing:

| Validation | Description |
|---|---|
| Schema validation | Stop on incorrect column names or data types |
| Missing values | Stop on invalid province/year keys, warn on missing measurements |
| Duplicate detection | Stop on duplicate source keys or processed province-year keys |
| Range validation | Convert invalid numbers to null and warn, retain negative values and warn |
| Geographic validation | Stop on ambiguous reference mappings, retain unmatched provinces and warn |
| Temporal validation | Validate years within 1900–2100 and report observed coverage |
| Consistency validation | Warn when production differs from area × yield beyond the threshold below |

Blank cells and missing markers such as `..`, `...`, `-`, and `N/A` become null. The pipeline also converts unrecognized numbers, NaN, and infinities to null. Missing observations and measurements receive no imputation.

### 5.1. Agricultural Consistency

For complete, nonnegative measurements, the pipeline checks the following relationship and warning threshold. Area is in hectares, yield in tons/hectare, and production in tons.

```text
expected_production = rice_area_ha × rice_yield_ton_ha
warning if abs(rice_production_ton - expected_production)
           > max(100, 0.02 × abs(expected_production))
```

The threshold allows rounding and statistical-definition differences. `rice_production_ton` uses the reported V06.15 values with unit conversion. Consistency checks flag deviations for investigation and preserve the source measurements.

### 5.2. Quality Reporting

`quality_report.json` records source files and hashes, excluded totals, output counts, year coverage, province IDs, missing values, duplicates, unmatched names, and numerical/consistency warnings. It includes counts and sample affected records.

`status: "completed"` means the Parquet file was written and its schema and row count verified by reading it back. A failed run records its error with `status: "failed"`.

The completed run checked on 2026-11-12 contains 945 records, 63 province IDs (1–63), seven regions, and years 2010–2024. It reports zero missing values, duplicates, unmatched provinces, negative/invalid measurements, and consistency warnings.

## 6. Data Limitations

### 6.1. Annual Temporal Resolution

The dataset contains annual observations and does not directly represent seasonal or monthly rice production variations.

### 6.2. Limited Time Series Length

The 2010–2024 period provides 15 annual observations per province.

This may limit the reliability of complex forecasting models and requires careful time-based evaluation.

### 6.3. Historical Administrative Boundaries

Vietnamese provincial and regional classifications may change over time.

Geographical mapping must be documented consistently to avoid incorrect comparisons and joins.

### 6.4. Production Is Not Market Supply

Total rice production does not directly represent the volume available for commercial procurement.

Factors such as domestic consumption, post-harvest losses, inventory, exports, prices, and logistics are not included.

### 6.5. Weather Integration

The agricultural dataset does not contain weather variables.

Temperature and rainfall data will be integrated separately for BP4, with attention to spatial alignment and temporal aggregation.

Statistical relationships between weather conditions and rice yield must not automatically be interpreted as causal effects.

---

## Maintenance

Update this document whenever:

- A new data source is introduced.
- Dataset columns or measurement units change.
- Geographical mapping rules are revised.
- Preprocessing logic changes the meaning of a field.
- New shared processed datasets are added.
