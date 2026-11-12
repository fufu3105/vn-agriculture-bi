# Big Data & Business Intelligence Project

<h2 align="center"> Vietnam Agriculture Analytics </h2>

[![Python 3.12.14](https://img.shields.io/badge/Python-3.12.14-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/windows/)
[![Java 21.0.13.0.2](https://img.shields.io/badge/Java-21.0.13.0.2-437291?logo=openjdk&logoColor=white)](https://learn.microsoft.com/en-us/java/openjdk/download)

This project focuses on agricultural data analysis in Vietnam to explore agricultural patterns and differences across provinces. It aims to apply Big Data processing and Business Intelligence techniques to support data-driven insights and decision-making through analytical dashboards.

## Course Information

| Field | Information |
|-------|-------------|
| Course | Big Data & Business Intelligence |
| Course Code | CO4033 |
| Lecturer | Assoc. Prof. Dr. Võ Thị Ngọc Châu |
| Academic Year | HK251 |
| Topic | Agricultural Data Analytics in Vietnam |

## Team Members

| Full Name | Student ID|
|-----------|-------------------|
| Nguyễn Ngọc Cát Hà |2352288|
| Trương Hoàng Phú |2352924|
| Đặng Sinh Hùng |2352420|
| Phạm Viết Hào  |2352297|

## Dataset

The agricultural data comes from the [National Statistics Office of Vietnam (NSO): Agriculture, Forestry and Fishery](https://www.nso.gov.vn/nong-lam-nghiep-va-thuy-san/). The current rice dataset uses the following NSO PX-Web tables:

| Table | Measure | Local Excel export |
|-------|---------|--------------------|
| [V06.13](https://www.nso.gov.vn/px-web-2/?pxid=V0613&theme=N%C3%B4ng%2C%20l%C3%A2m%20nghi%E1%BB%87p%20v%C3%A0%20th%E1%BB%A7y%20s%E1%BA%A3n) | Annual rice sown area by province | `nso_V06.13_2010_2024.xlsx` |
| [V06.14](https://www.nso.gov.vn/px-web-2/?pxid=V0614&theme=N%C3%B4ng%2C%20l%C3%A2m%20nghi%E1%BB%87p%20v%C3%A0%20th%E1%BB%A7y%20s%E1%BA%A3n) | Annual rice yield by province | `nso_V06.14_2010_2024.xlsx` |
| [V06.15](https://www.nso.gov.vn/px-web-2/?pxid=V0615&theme=N%C3%B4ng%2C%20l%C3%A2m%20nghi%E1%BB%87p%20v%C3%A0%20th%E1%BB%A7y%20s%E1%BA%A3n) | Annual rice production by province | `nso_V06.15_2010_2024.xlsx` |

The local exports cover 2010–2024 and 63 historical provinces. Region mappings come from `data/vietnam_regions_provinces.json`. The ETL reads these local files; it does not download data automatically.

## Requirements

Use Python 3.12:

```powershell
python -m pip install -r requirements.txt
```

The shared ETL requires JDK 17 or 21. BP analytics and Streamlit can reuse the included processed Parquet without Java.

## Run the system

```powershell
python src/bp1/bp1.py
python -m streamlit run dashboard/app.py
```

Or double-click `run_bp1.cmd` on Windows. It prefers `.venv` when present and starts the shared application at http://localhost:8501 without rebuilding analytics. Use `run_bp1.cmd --build-bp1` to rebuild BP1 first.

The homepage routes four business dashboards. BP1 is implemented; BP2–BP4 have clearly marked integration pages. Each BP processes shared Silver data and owns its Gold Parquet tables and dashboard module. Streamlit reads Gold directly; PostgreSQL is a later extension.

## Guides

| Guide | Purpose |
|---|---|
| [Environment setup](docs/guides/environment_setup.md) | Python dependencies and Java for shared ETL |
| [Agriculture ETL](docs/guides/etl_pipeline.md) | Raw Excel → shared processed Parquet |
| [Dashboard and integration](docs/guides/dashboard.md) | Run the app and integrate each member's dashboard |
| [BP1](docs/bp/bp1.md) | Mart schemas, features, filters and calculations |
| [Data dictionary](docs/data_dictionary.md) | Shared schema, units and data quality |
| [Architecture](docs/architecture.md) | Bronze → Silver → BP analytics → Gold → Streamlit |

## Project Structure

```text
vn-agriculture-bi/
├── data/
│   ├── raw/
│   │   ├── agriculture/
│   │   └── weather/
│   ├── processed/
│   │   ├── agriculture/
│   │   └── weather/
│   ├── analytics/
│   │   ├── bp1/                  # BP1 Parquet mart
│   │   ├── bp2/
│   │   ├── bp3/
│   │   └── bp4/
│   └── vietnam_regions_provinces.json
├── src/
│   ├── ingestion/
│   ├── common/
│   ├── bp1/bp1.py                # Shared processed → BP1 analytics
│   ├── bp2/
│   ├── bp3/
│   ├── bp4/
│   └── storage/
├── dashboard/
│   ├── app.py                    # Homepage, shared shell and navigation
│   ├── styles.css                # Common visual styles
│   ├── bp1/bp1.py                # Reads data/analytics/bp1/
│   ├── bp2/bp2.py
│   ├── bp3/bp3.py
│   └── bp4/bp4.py
├── scripts/
│   ├── build_processed.py
│   ├── build_analytics.py
│   └── load_postgres.py
├── docs/
│   ├── bp/
│   └── guides/
├── notebooks/
├── models/
├── configs/
├── deliverables/
├── .streamlit/config.toml        # Agriculture color theme
├── requirements.txt
└── run_bp1.cmd
```

Raw workbooks, shared processing modules, other members' BP folders and Word reports are retained. BP1's obsolete CSV/JSON snapshots, static HTML/SVG dashboard and old PDF guide are retired; its canonical runtime data lives in `data/analytics/bp1/*.parquet`.
