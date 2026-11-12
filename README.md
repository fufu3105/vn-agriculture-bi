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

Use Python 3.12. Install the project dependencies in your Python environment:

```powershell
python -m pip install -r requirements.txt
```

The shared ETL also requires JDK 17 or 21. The badges above show verified versions; Java is not required for the current CSV-based dashboard.

## Guides

| Guide | Purpose |
|-------|---------|
| [Environment setup](docs/guides/environment_setup.md) | Create `.venv`, install dependencies, configure Java on a new device, or reuse existing datasets. |
| [Agriculture ETL](docs/guides/etl_pipeline.md) | Prepare raw Excel inputs and generate the processed Parquet dataset and quality report. |
| [Run the dashboard](docs/guides/dashboard.md) | Start `dashboard/app.py` and check its required CSV snapshots. |
| [Data dictionary](docs/data_dictionary.md) | Dataset schema, units, geographical mapping, and data-quality rules. |

## Project Structure

```text
vn-agriculture-bi/
├── data/                          # Source datasets and analytical outputs
│   ├── raw/                       # Raw data
│   │   ├── agriculture/
│   │   └── weather/
│   ├── processed/                 # Cleaned and standardized data
│   │   ├── agriculture/
│   │   └── weather/
│   ├── analytics/                 # Aggregated tables and KPIs
│   └── vietnam_regions_provinces.json  # Province and region reference
│
├── src/                           # Data processing and analysis source code
│   ├── ingestion/                 # Data ingestion modules
│   │   ├── agriculture.py
│   │   └── weather.py
│   ├── common/                    # Shared data utilities
│   │   ├── cleaning.py
│   │   ├── provinces.py
│   │   └── validation.py
│   ├── bp1/                       # Analysis for business problem 1
│   │   └── bp1.py
│   ├── bp2/                       # Analysis for business problem 2
│   ├── bp3/                       # Analysis for business problem 3
│   ├── bp4/                       # Analysis for business problem 4
│   └── storage/                   # Data storage integration
│
├── dashboard/                     # Business Intelligence interface
│   ├── app.py
│   └── bp1/
│       ├── bp1_template.html
│       └── bp1.html
│
├── notebooks/                     # Exploratory analysis and experiments
├── models/                        # Model artifacts
├── scripts/                       # Utility and automation entry points
│   ├── build_processed.py
│   ├── build_analytics.py
│   └── load_postgres.py
├── configs/
│
├── docs/
│   ├── business_problems.md
│   ├── data_dictionary.md
│   ├── architecture.md
│   └── bp1.md
├── deliverables/                  # Reports and presentations
│   ├── report/
│   └── slides/
│
├── docker-compose.yml
├── .env.example
├── .gitattributes
├── .gitignore
├── requirements.txt
├── run_bp1.cmd
└── README.md
```
