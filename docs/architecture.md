# System architecture

## Data flow

1. Bronze — `data/raw/agriculture/` and `data/raw/weather/`: original source data, preserved without manual edits.
2. Shared ETL — `src/ingestion/`, `src/common/` and `scripts/build_processed.py`: validation, cleaning, key standardization and unit conversion.
3. Silver — `data/processed/agriculture/` and `data/processed/weather/`: cleaned Parquet shared by all four BPs.
4. Independent analytics — `src/bp1/` through `src/bp4/`: each member reads Silver and builds features, models or indicators for their BP.
5. Gold — `data/analytics/bp1/` through `data/analytics/bp4/`: Parquet outputs owned by each BP.
6. Presentation — `dashboard/app.py` provides the homepage and navigation; `dashboard/bpN/bpN.py` reads the corresponding BP's Gold data.

Preserve the repository's existing directory structure. Do not duplicate shared ETL in each BP or write BP-specific outputs into Silver. PostgreSQL is a possible later extension; Streamlit currently reads Parquet directly. Launching the shared application does not require rebuilding any BP. The homepage handles missing/invalid BP1 summary data, and each dashboard executes only when selected.

## Dashboards

| BP | Role | Status |
|---|---|---|
| BP1 | Rice production, sown area, yield and historical trends | Mart and dashboard implemented |
| BP2 | Explain production changes through area and yield | Integration placeholder |
| BP3 | Forecast next-year production and evaluate errors | Integration placeholder |
| BP4 | Examine temperature/rainfall associations with yield | Integration placeholder |

The shared interface uses English with a green, gold and ivory theme. Theme configuration lives in `configs/config.toml` and is loaded through Streamlit's `--theme.base` startup option; shared CSS lives in `dashboard/styles.css`. BP1 has its own distinct chart-series palette.

See the [integration guide](guides/dashboard.md) and [BP1 data contract](bp/bp1.md).
