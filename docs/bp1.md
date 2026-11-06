# BP1 Rice sourcing regions

BP1 shortlists locations for supplier assessment using production scale, historical growth and volatility. The main application is `dashboard/app.py`; the Word reports explain the business question, methods, findings and limitations.

## Where each part belongs

| Location | Purpose | Maintenance |
|---|---|---|
| `data/raw/nso_V06.*_2010_2024.xlsx` | Three retained NSO workbooks | Source inputs; preserve originals |
| `data/raw/vietnam_regions_provinces.json` | Team mapping of 63 provinces into seven regions | Source input |
| `src/bp1.py` | Read, normalize, validate and calculate BP1 outputs | Edit analysis here |
| `data/processed/rice_province_year.csv` | 945 province–year records | Generated |
| `data/analytics/bp1_*` | Two KPI CSVs and dashboard JSON | Generated |
| `dashboard/app.py` | Main interactive dashboard | Edit application here |
| `dashboard/bp1_template.html` | Optional static dashboard template | Edit template here |
| `dashboard/bp1.html` | Optional static snapshot | Generated; not the four-chart Streamlit application |
| `deliverables/report/` | Vietnamese and English Word reports, PDF guide and supporting findings | Update when findings or application behavior change |
| `deliverables/report/figures/` | Three static SVGs used in supporting findings | Generated |

Keep the existing separation by responsibility. BP1 filenames identify its data products without adding a second copy of the data or extra nested folders. Store shared business questions and column definitions in `business_problems.md` and `data_dictionary.md`; this page holds BP1 run instructions and controls.

## Run from the repository root

```powershell
python -m pip install -r requirements.txt
python src/bp1.py
python -m streamlit run dashboard/app.py
```

On Windows, `run_bp1.cmd` also starts the dashboard from any working directory. Install the requirements first and keep the terminal open while using http://localhost:8501.

The data build checks the 15 years, province coverage, complete numeric source cells, unique province mapping, 945 output rows, and provincial production totals against the published national row with a tolerance below 3 thousand tonnes per year. It then rebuilds the panel, KPI summaries, JSON, three SVGs and HTML snapshot. It does not regenerate Word reports or the PDF guide.

## Read the live dashboard

| Chart | Business question | How to read it |
|---|---|---|
| 1 Regional share | Which region has the greatest scale? | Doughnut shares for the selected year; national total in million tonnes |
| 2 Production flow to provinces | Which provinces contribute most within a region? | Five largest provinces plus Other provinces; labels in thousand tonnes (kt); statistical components rather than shipments |
| 3 Provincial profile | How do scale, growth and fluctuation compare? | x = annual growth SD in percentage points; y = CAGR in %; bubble size = selected-year production |
| 4 Regional production across years | Has the regional production pattern changed? | Seven regional time series in million tonnes, always 2010–2024 |

The **Year** selector above chart 1 offers 2015–2024 and changes charts 1–3. The **Region** selector above chart 2 changes only chart 2. Chart 3 uses `max(2010, selected_year - 9)` through the selected year and plots only provinces with at least 500 thousand tonnes in that year. For 2024 the window is 2015–2024; for 2015 it is 2010–2015.

**Data and methods** contains a fixed 2024 regional benchmark and a provincial table for the selected year, including all 63 provinces. Regional CAGR and volatility come from summed regional production, not averages of provincial KPIs.

## Reports and supporting figures

- [Vietnamese report](../deliverables/report/BP1_Danh_gia_vung_thu_mua_lua.docx) and [English report](../deliverables/report/BP1_Rice_Sourcing_Regions.docx): the same four-part reading flow, covering question and methods, findings, dashboard interpretation, and recommendations with limits.
- [PDF dashboard guide](../deliverables/report/BP1_Rice_Sourcing_Dashboard_Guide.pdf): retained visual explanation of the four-chart dashboard.
- [Supporting findings](../deliverables/report/bp1_findings.md): fixed 2024 analysis and three static figures. These figures have their own layout; the static scatter uses x = CAGR and y = volatility on a log scale. Follow its labels rather than transferring the live dashboard's axes.

The report benchmarks and generated KPI summaries stay at 2024 and 2015–2024. Only the live provincial profile recalculates with the year selector. Production describes local output and does not establish available procurement quantities, future risk or causes.
