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
vn-agriculture-bi/
├── data/                          # Source datasets and analytical outputs
│   ├── raw/                       # Raw data
│   │   ├── agriculture/           
│   │   └── weather/               
│   ├── processed/                 # Cleaned and standardized data
│   │   ├── agriculture/           
│   │   └── weather/               
│   └── analytics/                 # Aggregated tables and KPIs
│       ├── bp1/                   
│       ├── bp2/                   
│       ├── bp3/                  
│       └── bp4/                   
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

