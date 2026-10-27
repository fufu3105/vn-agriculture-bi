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

## Project Structure

```text
vn-agri-bi/
│
├── data/                  # Original, cleaned, and aggregated datasets
│   ├── raw/
│   ├── processed/
│   └── analytics/
│
├── notebooks/             # Data exploration and analysis notebooks
│
├── src/                   # Ingestion, cleaning, storage, KPIs, and validation
│   ├── ingest.py
│   ├── preprocess.py
│   ├── storage.py
│   ├── process.py
│   └── validate.py
│
├── dashboard/             # Business Intelligence dashboard
│   └── app.py
│
├── docs/                  # Business questions, data definitions, and architecture
│   ├── business_problems.md
│   ├── data_dictionary.md
│   └── architecture.md
│
├── deliverables/          # Final report and presentation slides
│   ├── report/
│   └── slides/
│
├── README.md
├── requirements.txt
└── .gitignore
```


