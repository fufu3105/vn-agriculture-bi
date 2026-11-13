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

The shared ETL also requires JDK 17 or 21. The badges above show verified versions. The dashboard reads Parquet outputs directly.

## Guides

| Guide | Purpose |
|-------|---------|
| [Environment setup](docs/guides/environment_setup.md) | Create `.venv`, install dependencies, configure Java on a new device, or reuse existing datasets. |
| [Agriculture ETL](docs/guides/etl_pipeline.md) | Prepare raw Excel inputs and generate the processed Parquet dataset and quality report. |
| [Run the dashboard](docs/guides/dashboard.md) | Start `dashboard/app.py` and build each dashboard's analytics Parquet as needed. |
| [Business problems](docs/business_problems.md) | See the four analytical questions and how they support sourcing decisions. |
| [Data dictionary](docs/data_dictionary.md) | Dataset schema, units, geographical mapping, and data-quality rules. |

## Project Structure

```text
vn-agriculture-bi/
├── configs/                        # Pipeline and application configuration
├── dashboard/                      # Interface
│   ├── bp1/                        
│   ├── bp2/                        
│   ├── bp3/                        
│   └── bp4/                        
├── data/                           # Source datasets and processing outputs
│   ├── analytics/                  # Aggregated tables and KPIs
│   ├── processed/                  # Cleaned and standardized datasets
│   ├── raw/                        # Original agriculture and weather data
│   ├── weather_metadata/           # Download manifests and weather quality reports
│   └── vietnam_regions_provinces.json
├── deliverables/                   # Project reports and presentations
│   ├── report/                     # Written reports
│   └── slides/                     # Presentation slides
├── docs/                           # Project documentation
│   ├── bp/                         # Business problem documentation
│   ├── guides/                     # Environment setup and execution guides
│   ├── architecture.md
│   ├── business_problems.md
│   └── data_dictionary.md
├── models/                         # Model artifacts
├── notebooks/                      # Exploratory analysis and experiments
├── scripts/                        # ETL and automation entry points
│   ├── build_analytics.py
│   ├── build_processed.py
│   ├── ingest_weather.py
│   └── load_postgres.py
├── src/                            # Data ingestion, processing, and analysis code
│   ├── bp1/                        
│   ├── bp2/                        
│   ├── bp3/                        
│   ├── bp4/                        
│   ├── common/                     # Shared cleaning, mapping, and validation utilities
│   ├── ingestion/                  # Agriculture extraction and weather downloads
│   └── storage/                    # Data storage integration
├── tests/                         
├── docker-compose.yml
├── .env.example
├── .gitattributes
├── .gitignore
├── requirements.txt
├── run_bp1.cmd
└── README.md
```
