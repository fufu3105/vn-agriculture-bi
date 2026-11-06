# Big Data & Business Intelligence Project

<h2 align="center"> Vietnam Agriculture Analytics </h2>

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

**Dataset:** Vietnam Provinces Agriculture Master
**Source:** [vn-provinces-agriculture-master](https://huggingface.co/datasets/letrinhan/vn-provinces-agriculture-master)

This dataset serves as the primary source for agricultural data exploration, processing, and Business Intelligence analysis.

## BP1 — Rice sourcing regions

BP1 compares production scale, growth and historical volatility to shortlist rice sourcing locations. It uses NSO PX-Web exports V06.13–V06.15 for 2010–2024, covering 63 historical provinces and seven project regions.

Run from this repository:

```powershell
python -m pip install -r requirements.txt
python src/bp1.py
python -m streamlit run dashboard/app.py
```

The dashboard has four charts: regional share, regional breakdown into provinces, provincial growth and volatility, and regional history. Select **Data and methods** for exact tables and definitions.

On Windows, double-click `run_bp1.cmd` after installing the dependencies. Keep the terminal open while using http://localhost:8501.

- [BP1 structure, outputs and dashboard controls](docs/bp1.md)
- [English Word report](deliverables/report/BP1_Rice_Sourcing_Regions.docx)
- [Vietnamese reference report](deliverables/report/BP1_Danh_gia_vung_thu_mua_lua.docx)
- [Dashboard guide](deliverables/report/BP1_Rice_Sourcing_Dashboard_Guide.pdf)
- [Supporting findings and static figures](deliverables/report/bp1_findings.md)

## Project Structure

```text
vn-agriculture-bi/
│
├── data/                  # Original, cleaned, and aggregated datasets
│   ├── raw/
│   ├── processed/
│   └── analytics/
│
├── src/                   # Ingestion, cleaning, storage, KPIs, and validation
│   ├── bp1.py             # Rebuild BP1 panel, KPIs and static outputs
│   ├── ingest.py
│   ├── preprocess.py
│   ├── storage.py
│   ├── process.py
│   └── validate.py
│
├── dashboard/             # Business Intelligence dashboard
│   ├── app.py             # Main Streamlit dashboard
│   ├── bp1_template.html  # Template for the optional static snapshot
│   └── bp1.html           # Generated snapshot
│
├── docs/                  # Business questions, data definitions, and architecture
│   ├── business_problems.md
│   ├── data_dictionary.md
│   ├── bp1.md             # BP1 technical and usage reference
│   └── architecture.md
│
├── deliverables/          # Final report and presentation slides
│   └── report/            # Word reports, PDF guide, findings and figures
│
├── README.md
├── run_bp1.cmd            # Windows dashboard launcher
├── requirements.txt
└── .gitignore
```


