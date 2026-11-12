# BP1 — Rice production overview

BP1 provides descriptive analysis of production, sown area, yield, historical trends and variability. It supports sourcing-region assessment; production is potential supply rather than a guaranteed procurement quantity.

## Responsibilities and data flow

`data/raw/agriculture` → shared ETL → `data/processed/agriculture` → `src/bp1/bp1.py` → `data/analytics/bp1` → `dashboard/bp1/bp1.py`.

- Shared cleaning and standardization belong to `scripts/build_processed.py`. BP1 does not reread Excel or write to processed storage.
- BP1 reads `data/processed/agriculture/rice_province_year/`.
- Its dashboard reads only the four Parquet tables in `data/analytics/bp1/`; features are calculated in the analytics stage.
- `dashboard/app.py` owns the shared homepage, sidebar and navigation for BP1–BP4.

## Run

From the repository root, after installing `requirements.txt`:

```powershell
python src/bp1/bp1.py
python -m streamlit run dashboard/app.py
```

Open http://localhost:8501 and select BP1, or use http://localhost:8501/bp1.
On Windows, `run_bp1.cmd` prefers `.venv` when available and launches all dashboards without rebuilding analytics. Use `run_bp1.cmd --build-bp1` to rebuild BP1 first.

If processed Parquet is missing, run the [shared ETL](../guides/etl_pipeline.md) first. Java is not required when reusing the existing processed data.

## Analytics tables

| File in data/analytics/bp1/ | Granularity | Current rows |
|---|---|---|
| province_year.parquet | Province × year | 945 |
| region_year.parquet | Region × year | 105 |
| national_year.parquet | National × year | 15 |
| province_profile_2010_2024.parquet | Fixed full-period province profile | 63 |

Stored measurements use standard units: `rice_area_ha` (ha), `rice_yield_ton_ha` (tonnes/ha) and `rice_production_ton` (tonnes). Millions are used only for display.

Derived columns:
- `area_yoy_pct`, `yield_yoy_pct`, `production_yoy_pct`: annual percentage changes.
- `area_share_pct`, `production_share_pct`: shares of the same-year national total, including when a region is selected.
- `production_rank`: same-year production rank within the table's geographical level.
The separate `province_profile_2010_2024.parquet` table contains province identity, 2024 production and:
- `profile_start_year` = 2010 and `profile_end_year` = 2024.
- `production_cagr_pct`: ((2024 production / 2010 production)^(1 / 14) − 1) × 100.
- `production_yoy_std_pp`: sample standard deviation of the 14 annual growth rates from 2011 through 2024, in percentage points.

This is a retrospective full-period summary, not an as-of-selected-year feature. It is stored separately from the annual tables.

Regional/national production and area are summed from provinces. Aggregated yield is the area-weighted average of published provincial yields. Published production is retained rather than replaced with area × yield.

Undefined changes and zero denominators remain null. Annual indicators use only current/past observations; the fixed profile intentionally uses the complete 2010–2024 history. No interpolation or zero filling is used. The build checks schema, numeric validity, duplicate keys, panel completeness and aggregate reconciliation. Each generated Parquet file is read back and compared before replacement.

## Understanding the metrics

| Metric | Meaning | Unit |
|---|---|---|
| Production | Total harvested paddy rice during the year | tonnes |
| Sown area | Total area planted across cropping seasons; a plot is counted again when planted in another season | ha |
| Yield | Output per sown hectare, describing productivity | tonnes/ha |

For example, 100 ha × 6 tonnes/ha ≈ 600 tonnes. A 50 ha plot planted twice contributes 100 ha of annual sown area. The area is not necessarily the physical land footprint. The production/area/yield relationship is approximate for these published tables because of reporting and rounding differences.

The interface provides metric help tooltips and an expandable explanation.

## Dashboard controls

The interface, chart labels, methods and exports use English. Vietnamese province names remain proper geographical names. Canonical region names in Parquet are translated at display time; source data is preserved.

- **Statistical year:** 2010–2024; defaults to the latest year.
- **Analysis scope:** All regions or one of seven regions; controls KPIs, leading provinces, historical trends, growth profiles and the data table.
- **Chart metric:** Production, Sown area or Yield; controls regional, provincial and historical comparisons.
- **01 · Regional comparison:** always compares all seven regions for national context. Production uses shares; area and yield use absolute values.
- **04 · Growth & volatility · 2010–2024:** always uses the complete 2010–2024 period. Both bubble size and the 500,000-tonne display threshold use 2024 production. Changing the statistical year leaves this chart unchanged; the region filter still applies.
- **Data & methods:** shows the filtered annual table, the separate fixed-period profile table, calculations, limitations and CSV export of annual data. CSV is an export convenience; Parquet remains the runtime storage format.

BP1 uses muted forest, wheat, slate, clay and sage tones, mapped consistently to English region names across charts. The shared green/gold application theme is retained.

BP1 describes history. BP2 explains area/yield contributions, BP3 forecasts production and BP4 examines weather associations. Descriptive BP1 indicators do not establish causes or predict outcomes.

## Retired outputs

Legacy CSV/JSON files in the analytics root, the separate processed CSV, static HTML templates/snapshots and generated SVG figures are retired. The old PDF dashboard guide and findings document are also retired. Both Word reports remain as historical references and are not regenerated by the build. The [notebook](../../notebooks/bp1.ipynb) is optional exploration rather than a runtime dependency.
