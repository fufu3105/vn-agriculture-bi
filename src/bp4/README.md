# BP4 Historical Weather Pipeline

The pipeline downloads NASA POWER historical daily point data and builds Spark weather tables for joining to the agricultural dataset on integer `province_id` and `year`.

## Source and Geography

Requests use the official Daily Point API with `community=AG`, `T2M` (°C), `PRECTOTCORR` (mm/day), JSON format and Local Solar Time. Responses declare the missing-value sentinel in `header.fill_value`, currently `-999`. Raw response bytes are retained. [NASA Daily API documentation](https://power.larc.nasa.gov/docs/services/api/temporal/daily/)

The 63 historical provinces, seven project regions and IDs follow `data/vietnam_regions_provinces.json`. Coordinates in `configs/bp4_province_coordinates.json` come directly from the latitude/longitude label-point attributes of Natural Earth's admin-1 layer. Matching used province names and `gn_name`, including the GeoNames names for Natural Earth features with regional display labels. All 63 unique features matched, and all points were checked inside their corresponding source polygons. The coordinate file records the source URL, source hash, feature IDs, names and province mappings. [Natural Earth source](https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_10m_admin_1_states_provinces.geojson)

Each weather series represents one point/grid cell associated with a province. Spatial variation across rice-growing areas remains a limitation. Exact duplicate coordinates share a request. Distinct points are not rounded into assumed grid cells because the responses do not provide a reliable grid-cell identifier for this optimization.

## Modules

| File | Responsibility |
|------|----------------|
| `src/ingestion/weather.py` | HTTP sessions, retries, original JSON storage, cache validation and manifest |
| `src/common/cleaning.py` | `clean_weather_daily`, `aggregate_weather_period` and `add_weather_anomalies` |
| `src/bp4/pipeline.py` | Configuration, province checks, acquisition and Spark orchestration |
| `scripts/ingest_weather.py` | Command-line entry point |
| `tests/test_bp4_weather.py` | Offline synthetic fixtures and Spark checks |

## Setup and Configuration

Use the existing Python 3.12 / Java 17 or 21 environment and install `requirements.txt`, including PySpark and requests. The local Windows JDK and filesystem adapter used by the agricultural ETL are reused. Follow the environment guide when preparing a new device. [Environment setup](../../docs/guides/environment_setup.md)

`configs/bp4_weather.json` controls dates, province selection, parameters, HTTP timeout/retries/backoff, concurrency, paths, completeness thresholds and climate baseline coverage. Full collection defaults to **2010-01-01 through 2024-12-31**. Date overrides must stay within this interval. Pilot collection uses Thanh Hóa (26), Gia Lai (41), An Giang (57) and 2022–2023. Empty `province_ids` selects all 63 provinces.

Concurrency defaults to one request and can be set from one to five. Requests are spaced, temporary failures retry with exponential backoff, and HTTP 429 reduces subsequent batches to one request. Cache files are reused only after validating dates, location, parameters, units and structure. Failed requests remain in the manifest and are retried on the next run. Only one pipeline writer should operate on a given output directory at a time.

## Run

Run from the repository root with the project Python interpreter. Each command is a separate mode.

```powershell
.\.venv\Scripts\python.exe scripts/ingest_weather.py dry-run
.\.venv\Scripts\python.exe scripts/ingest_weather.py pilot
.\.venv\Scripts\python.exe scripts/ingest_weather.py full
.\.venv\Scripts\python.exe scripts/ingest_weather.py resume
```

`dry-run` prints the plan without downloading. The default full plan has 945 province-year requests. `pilot` downloads six province-year responses and runs validation. `full` requires a passed pilot using the same coordinate reference. `resume` repeats the most recent collection mode and validates cached chunks before skipping downloads. A pilot resumed from its manifest stays a pilot.

Optional selection and date overrides can be inspected before collecting.

```powershell
.\.venv\Scripts\python.exe scripts/ingest_weather.py dry-run --start 2010-01-01 --end 2024-12-31 --province-ids 26 41 57
```

## Storage and Schemas

Original responses are in `data/raw/weather/nasa_power/`. The request hash names each file. `data/weather_metadata/download_manifest.json` records request coordinates/dates, province IDs and regions, timestamps, status, response geometry/header, file paths, hashes, counts and errors. Quality reports are stored separately in that metadata directory. These generated weather paths are ignored by Git.

Full outputs use `data/processed/weather/`. Pilot outputs use its `pilot/` subdirectory. Each dataset directory contains a single Parquet file with a stable name, plus its checksum and Spark metadata. The quality report records the file paths in `quality.dataset_files`.

```text
data/processed/weather/pilot/
├── weather_daily/
│   └── weather_daily.parquet
├── weather_monthly/
│   └── weather_monthly.parquet
└── weather_annual/
    └── weather_annual.parquet
```

Read either the dataset directory or its named data file.

```python
annual = spark.read.parquet("data/processed/weather/pilot/weather_annual/weather_annual.parquet")
```

| Output | Columns |
|--------|---------|
| `weather_daily/weather_daily.parquet` | `province_id`, `date`, `year`, `month`, `temperature_c`, `rainfall_mm`, `data_status` |
| `weather_monthly/weather_monthly.parquet` | `province_id`, `year`, `month`, `avg_temperature_c`, `total_rainfall_mm`, `valid_temperature_days`, `valid_rainfall_days`, `expected_days`, `data_status` |
| `weather_annual/weather_annual.parquet` | `province_id`, `year`, `avg_temperature_c`, `annual_rainfall_mm`, `valid_temperature_days`, `valid_rainfall_days`, `expected_days`, `data_status`, `baseline_temperature_c`, `baseline_rainfall_mm`, `baseline_temperature_years`, `baseline_rainfall_years`, `temperature_anomaly_c`, `rainfall_anomaly_pct` |

Province IDs, year, month and expected days use integers. Valid-day and baseline-year counts use long integers. Weather measurements and anomalies use doubles, dates use Spark DateType, and status uses strings. Names and regions are available through the coordinate reference and manifest.

## Validation and Completeness

- Every response must contain both variables, verified units and all requested date keys. An unusable response fails collection and remains eligible for retry.
- Duplicate province-date keys or invalid dates stop processing. The selected calendar is generated explicitly so missing observations appear as null rows with `missing_date` status.
- Sentinel values become null. Unparseable/nonfinite values and negative rainfall become null with `invalid` status. Other missing values receive `missing` status. Zero rainfall is retained as an observed zero.
- Monthly and annual statistics use valid daily observations directly. Leap years and full calendar months/years determine `expected_days`, including partial collection intervals.
- Temperature means require at least 90% of calendar days by default. Rainfall totals require 100% of days, otherwise the analytical total is null. A period with any missing variable days is flagged `incomplete`.
- The annual join keys are checked against the agricultural Parquet schema, province IDs, names and regions. Each output is read back to verify schema and record count.

## Baselines and BP4 Integration

The requested climate reference remains 1991–2020, requiring at least 24 valid baseline years per variable. Rainfall additionally requires a positive baseline. Temperature anomaly is annual temperature minus the mean baseline temperature. Rainfall anomaly is the percentage difference from mean baseline rainfall.

Collection restricted to 2010–2024 provides at most 11 years within that reference period. The current configuration therefore leaves anomaly values null and reports insufficient baseline coverage. An alternative reference period and minimum-year policy can be configured explicitly if the project adopts one. The pilot also keeps anomalies null.

The annual table joins agricultural observations by `province_id` and `year`. A full collection covers the same 2010–2024 years. Subsequent BP4 work can filter its analysis years and interpret weather–yield associations with the limitations of point-based reanalysis data.

## Offline Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_bp4_weather.py -v
```

Tests use synthetic NASA JSON and local Spark, covering parsing, dates, missing values, duplicates, monthly/annual calculations, leap years, incomplete periods, anomalies, coordinate mappings, retry and validated cache reuse.

## Verified Execution

The live pilot completed on 2026-11-12 with six original JSON responses, 2,190 daily rows, 72 monthly rows and six annual rows for Thanh Hóa, Gia Lai and An Giang over 2022–2023. Every day and both variables were present. The pilot had zero duplicate province-date keys, missing measurements, incomplete months or incomplete years. Parquet read-back and the agricultural ID/type compatibility checks passed. Repeating the run through `resume` reused all six validated responses.

A separate API coverage check at the same three points returned 5,479 days per province for 2010-01-01 through 2024-12-31, with zero missing T2M or PRECTOTCORR values. The 63-province full collection is configured and its request plan verified. Live collection and completeness have been verified for the three pilot points. Fifteen focused offline tests passed, including Spark processing checks.
