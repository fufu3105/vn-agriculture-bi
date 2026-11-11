# Agriculture ETL: Raw to Processed

[Project overview](../README.md) | [Environment setup](environment_setup.md)

Complete the environment setup, including Java and the Windows filesystem adapter where applicable, before running this pipeline. Run all commands from the repository root.

Export the three NSO tables linked in the [README dataset section](../README.md#dataset) for 2010–2024 and place the Excel files under `data/raw/agriculture/` with the exact filenames shown. Keep the geographical reference at `data/vietnam_regions_provinces.json`.

```text
data/
├── raw/
│   └── agriculture/
│       ├── nso_V06.13_2010_2024.xlsx
│       ├── nso_V06.14_2010_2024.xlsx
│       └── nso_V06.15_2010_2024.xlsx
└── vietnam_regions_provinces.json
```

Run the shared PySpark ETL:

```powershell
.\.venv\Scripts\python.exe scripts/build_processed.py
```

The pipeline extracts the Excel tables, removes national and regional totals, standardizes province names, joins measurements by province and year, validates the data, and writes:

```text
data/processed/agriculture/
├── rice_province_year/
│   └── rice_province_year.parquet
└── quality_report.json
```

The Parquet file contains `year`, `province_id`, `province_name`, `region`, `rice_area_ha`, `rice_yield_ton_ha`, and `rice_production_ton`. `province_id` follows the province order in the reference JSON. Source units are converted from thousand hectares, quintals/hectare, and thousand tons to hectares, tons/hectare, and tons, respectively; production is read from V06.15 rather than calculated from area and yield.

Check that `quality_report.json` has `status: "completed"`. The verified input files produce 945 records across 63 provinces, seven regions, and 2010–2024.
