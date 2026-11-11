# Data Directory

## Directory Layout

| Directory | Purpose |
|-----------|---------|
| `raw/agriculture/` | Original agricultural datasets. |
| `raw/weather/` | Original weather datasets. |
| `processed/agriculture/` | Cleaned agricultural datasets. |
| `processed/weather/` | Cleaned weather datasets. |
| `processed/reference/` | Shared reference tables and geographic mappings. |
| `analytics/bp1/` | Analytical outputs for business problem 1. |
| `analytics/bp2/` | Analytical outputs for business problem 2. |
| `analytics/bp3/` | Analytical outputs for business problem 3. |
| `analytics/bp4/` | Analytical outputs for business problem 4. |


## BP1 rice panel

`data/processed/rice_province_year.csv` has one row per province and year (2010–2024). `province` and `region` are names under the historical 63-province and team seven-region conventions. `year` is an integer. `area_thousand_ha` is annual rice sown area, `yield_quintal_per_ha` is annual rice yield, and `production_thousand_tons` is annual rice production. Source tables: NSO PX-Web V06.13, V06.14, and V06.15, respectively.

`bp1_province_summary.csv` and `bp1_region_summary.csv` report `production_2024_thousand_tons`, `share_2024_pct`, `cagr_pct` (2015–2024, 9 intervals), `yoy_sd_pct_points` (sample standard deviation of annual percentage changes 2016–2024), and `largest_yoy_decline_pct` (minimum annual percentage change). Regional production is summed from provinces; regional yields are not summed.
