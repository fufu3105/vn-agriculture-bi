# BP4: Climate, Rice Yield & Production Diagnostics

BP4 is a four-tab historical diagnostic dashboard, not a causal or predictive model. Coverage is 2010-2024: 63 historical provinces and seven project regions, using existing NSO V06.13/V06.14/V06.15 agriculture and NASA POWER weather data.

## Run

```powershell
python -m src.bp4.bi prepare
python -m streamlit run dashboard/app.py
```

If prepared artifacts already exist, only Streamlit is needed. Preparation uses existing processed data and does not rerun Spark source ETL. Additional analytical exports are optional and do not add dashboard sections.

## Four dashboard tabs

| Tab | Content |
|---|---|
| Overview | Regional annual climate lines and a single weather/rice overlay; Measure selects Temperature, Rainfall or both; Average/Anomaly, All Regions/seven regions and Production/Yield choices |
| Climate relationships | Two main scatter plots; regional association dot comparison; region-relative climate-tercile box plot; climate-yield stability matrix. Supporting correlation tables/CSV and one simultaneous lag 0/1/2 heatmap remain |
| Abnormal years | Detrended-deviation heatmap with actual and fitted trend values and same-year climate anomalies in the hover details |
| Diagnostic findings | Three plain-language observations on national production, regional climate-yield relationships, and below-trend yield years; always based on the complete 2010-2024 dataset |

The Analysis period slider and climate reference setting remain available across tabs. Each tab renders only its own charts, following the BP2/BP3 view selector pattern.

Co-movement, monitoring and insight sections are no longer displayed. Optional CLI analyses can be run separately when needed.

## Aggregation, units and time

Regional production sums reported provincial tonnes. Regional yield is total tonnes / total sown hectares (t/ha). National Production retains seven stacked regional bars and the established colors/order. National Yield is now **one actual national yield bar**, total production / total area; regional mode shows actual regional yield. Prior stacked yield contributions were mathematically additive but could be mistaken for actual regional yields.

Weather weights are provincial `rice_area_ha` (annual sown area), changing annually. Missing or incomplete weather is excluded, never zero-filled; at least 90% of regional area must have complete weather. Annual rainfall is accumulated mm, not a sum of regional rainfall depths. Audit checks compare yearly rainfall with sums of monthly rainfall and yearly temperature with day-weighted monthly temperature. Both match within floating-point precision; see `data/analytics/bp4/diagnostic_bi/refinement_audit.json`.

Year-over-year changes require an actual preceding calendar year and positive denominator. Lag alignment uses climate(t-lag) with outcome change(t), never future climate. With complete 2010-2024 coverage there are at most 14 changes and 13 lag-2 pairs. Narrowed windows may have fewer pairs; lagged climate years must also lie inside the analysis window. Precomputed changes can retain their valid preceding-year calculation outside the display window.

Temperature anomaly = annual temperature minus its reference mean (C). Rainfall anomaly = (annual rainfall / positive reference mean - 1) * 100%. Reference period is independent of Analysis period; default 2010-2024 is available project history, **not a conventional long-term climate normal**. At least eight reference years and 90% reference-calendar coverage are required. Invalid/zero rainfall references yield unavailable anomalies. Within one region, Pearson and Spearman are invariant between absolute/anomaly values when the valid pairs are identical.

## Section 2.1 scatter interaction

Both main scatters share one Region highlighting selectbox with All Regions and the seven regions, like the Production comparison selector. All points are shown by default, without OLS lines. Choosing a region enlarges/highlights its points and dims other regions without changing colors. Show regression line optionally draws only that region's descriptive OLS fit; the line remains OLS when Spearman is selected. A valid coefficient/line requires at least eight valid pairs and nonconstant inputs.

Each scatter has variable/unit-specific climate axes. The four summary metrics (method, coefficient, n and direction) appear only when a specific region is selected, with N/A for unavailable results. Point hover includes region, outcome year, climate year, climate value/unit, both yield/production changes, actual selected outcome and area change. Actual outcomes are joined by the outcome year, never the lagged climate year. These are presentation joins only; aggregation, formulas and pipelines are unchanged. Section 2 uses regional annual observations. Statistics and directions are descriptive, not significance or causality claims.

## Filter scope

| Control | Scope |
|---|---|
| Analysis period | The only control in the opening Analysis scope container; sets displayed years in the first three tabs |
| Climate reference | Shared expander below the tab selector; sets anomaly values without refitting the historical detrending benchmark |
| Section 3 outcome | Selects the detrended heatmap measure |
| Supporting lag climate | Selects the Section 2 lag heatmap variable |
| Section 1 comparison/outcome/measure | Local scope; National/seven-region choice independently controls geography |
| Relationship outcome | Section 2, defaults Yield change; switch to Production change |
| Observational unit | Section 2 uses regional annual observations |
| Pearson/Spearman and lag | Correlation/lag-enabled relationship views; descriptive scatter lines remain OLS |
| Stability Matrix | Always regional annual, Yield change, climate anomalies, lag 0 |

Section 2 minimum eight valid annual pairs is technical, not a guarantee of reliable inference. Dot plots show N/A for constant/short inputs. Box terciles are within-region; collapsed quantiles are explicitly unavailable. The retained lag heatmap allows simultaneous comparison of all three lags. Nominal intervals and p/q values in supporting tables do not fully adjust serial dependence.

There is no page-wide region filter. The Section 1 overlay has its own All Regions/region selector, and the main Section 2 scatters have a matching region-highlighting selectbox. Other regional charts show all seven regions.

## Abnormal years

Fitted trend values use the full historical 2010-2024 linear fit, established before display filtering. Percentage deviation is (actual - fitted) / fitted * 100, unavailable if the fitted value is nonpositive. The word **fitted** replaces misleading expected-outcome wording: these are in-sample retrospective benchmarks, not forecasts.

The heatmap keeps cell values, top-to-bottom north-to-south rows, detailed hover and black hover border. It is the final item in Section 3; the former event timeline, investigation detail and case table remain removed.

## Diagnostic findings

Section 4 summarizes three observations from all seven regions over 2010-2024. Its figures stay fixed when dashboard filters change. The summaries describe associations and individual below-trend years, not causes or statistically flagged events.

## Verification

Run the BP4 tests with `python -m unittest discover -s tests -p "test_bp4_*.py" -v`. The dashboard reads the prepared regional Parquet file and does not modify BP1-BP3 or processed sources.
