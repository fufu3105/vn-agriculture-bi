"""One sequential BP4 report: prepared inputs + cached lightweight statistics."""
import sys
from importlib import reload
from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from src.bp4 import bi
from src.bp4.features import OUT, OUTCOMES, CLIMATE, derive, select, reference
from src.bp4 import production_weather
from src.bp4 import event_heatmap as event_charts
from src.bp4 import complementary
from src.bp4 import relationship_view
# This stateless helper can remain imported in a long-running Streamlit process.
# Reload it on page execution so chart edits take effect without a server restart.
production_weather=reload(production_weather)
event_charts=reload(event_charts)
complementary=reload(complementary)
relationship_view=reload(relationship_view)
national_temperature=production_weather.national_temperature
production_temperature_figure=production_weather.production_temperature_figure
REGION_ORDER=reference().region.drop_duplicates().tolist()

SECTIONS = ["Historical Climate & Rice Production Overview", "Climate-Production Diagnostic Relationships",
            "Abnormal Year Investigation", "Diagnostic Findings"]


@st.cache_data(show_spinner=False)
def inputs(version):
    return pd.read_parquet(OUT/"regional.parquet")


@st.cache_data(show_spinner=False, max_entries=16)
def analysis(r,c):
    return bi.relationship_table(r,c)


def chart(fig,key):
    production_weather.order_region_legends(fig,REGION_ORDER)
    fig.update_layout(height=420,margin=dict(l=25,r=20,t=45,b=25),legend_title_text="")
    st.plotly_chart(fig,width="stretch",key=key,config={"displaylogo":False})


def table(frame,name):
    if frame.empty: st.info(bi.INSUFFICIENT); return
    st.dataframe(frame,hide_index=True,width="stretch")
    st.download_button("Download "+name,frame.to_csv(index=False).encode("utf-8-sig"),name+".csv","text/csv",key="csv_"+name)


def section(n,question):
    st.divider(); st.header(f"{n}. {SECTIONS[n-1]}",anchor=f"section-{n}"); st.write(question)


def heat(frame,x,y,value,title,key):
    if frame.empty: st.info(bi.INSUFFICIENT); return
    pivot=frame.pivot_table(index=y,columns=x,values=value,aggfunc="first",dropna=False)
    if pivot.empty or pivot.isna().all().all(): st.info(bi.INSUFFICIENT); return
    chart(px.imshow(pivot,aspect="auto",title=title,color_continuous_scale="RdBu_r",color_continuous_midpoint=0),key)


def render():
    st.markdown('<div class="eyebrow">BP4 / DIAGNOSTIC ANALYTICS</div>',unsafe_allow_html=True)
    st.title("Climate, Rice Yield & Production Diagnostics")
    st.write("Investigating historical climate conditions, agricultural production variation, and regional yield variation in Vietnam.")
    paths=[OUT/"regional.parquet"]
    if not all(path.exists() for path in paths):
        st.info("Build the prepared BP4 data before opening this report."); st.code("python -m src.bp4.bi prepare"); return
    raw=inputs(tuple(p.stat().st_mtime_ns for p in paths))
    c=bi.config(); regions=REGION_ORDER
    with st.container(border=True):
        st.subheader("Analysis scope")
        years=st.slider("Analysis period",2010,2024,(2010,2024),key="bp4_years")
    st.markdown(" | ".join(f"[{i}. {name}](#section-{i})" for i,name in enumerate(SECTIONS,1)))
    section(1,"Explore climate, rice yield and production over time before investigating their relationships.")
    baseline=st.slider("Historical climate reference period",2010,2024,(2010,2024),key="bp4_reference")
    r=select(derive(raw,"region",baseline,c["minimum_n"]),years,regions)
    if r.empty: st.info(bi.INSUFFICIENT); return
    a,d,e=st.columns(3)
    a.metric("Selected region-years",len(r)); d.metric("Complete region-years",f"{r.complete.mean():.0%}"); e.metric("Supported climate references",f"{r[['temperature_c_anomaly','rainfall_mm_anomaly']].notna().all(axis=1).mean():.0%}")

    st.subheader("1.1 Rainfall & Temperature Change")
    weather_change_form=st.selectbox("Weather trend measure",["Actual values","Anomalies"],key="bp4_weather_change_form")
    weather_change_anomaly=weather_change_form=="Anomalies"
    for weather_name,col in CLIMATE.items():
        metric=col+"_anomaly" if weather_change_anomaly else col
        unit=("%" if weather_change_anomaly else "mm") if weather_name=="Rainfall" else "C"
        label=(weather_name+" anomaly") if weather_change_anomaly else ("Annual rainfall" if weather_name=="Rainfall" else "Average temperature")
        if r[metric].notna().any():
            fig=px.line(r.sort_values(["region","year"]),x="year",y=metric,color="region",markers=True,
                        labels={"year":"Year",metric:label+" ("+unit+")"},title=label+" by year")
            fig.update_xaxes(dtick=1)
            if weather_change_anomaly: fig.add_hline(y=0,line_dash="dot",line_color="gray")
            chart(fig,"weather_change_"+weather_name.lower())
        else:
            st.info(weather_name+": Insufficient Evidence for the selected reference period.")
    # st.caption("These lines show changes over time using annual sown-area-weighted regional weather. Temperature uses C and annual rainfall uses mm. Anomalies follow the selected historical reference: temperature difference in C, rainfall difference in percent. The charts follow Analysis period and Regions independently of the agricultural outcome and climate selectors.")

    st.subheader("1.2 Weather vs Rice Production & Yield")
    overlay_outcome=st.selectbox("Climate comparison outcome",["Production","Yield"],key="bp4_overlay_outcome")
    if overlay_outcome=="Yield":
        st.info("Yield uses yield_value (t/ha). National yield = total production / total sown area. National yield is shown as one actual yield bar per year, not stacked regional contributions.")
    st.subheader("Weather vs Rice "+overlay_outcome)
    a,d,e=st.columns(3)
    measure_option=a.selectbox("Measure",["Rainfall and Temperature","Rainfall","Temperature"],key="bp4_overlay_measure")
    measures=["Temperature","Rainfall"] if measure_option=="Rainfall and Temperature" else [measure_option]
    production_scope=d.selectbox("Production comparison",["All Regions",*REGION_ORDER],key="bp4_overlay_scope")
    value_mode=e.selectbox("Weather values",["Average","Anomaly"],key="bp4_overlay_value_mode")
    use_anomaly=value_mode=="Anomaly"
    national=production_scope=="All Regions"
    if national:
        production=raw[raw.year.between(*years)]
        temperatures=production_weather.national_temperature(raw,baseline,c["minimum_n"])
        rainfall=production_weather.national_rainfall(raw,baseline,c["minimum_n"])
        temperatures=temperatures[temperatures.year.between(*years)]
        rainfall=rainfall[rainfall.year.between(*years)]
    else:
        production=derive(raw[raw.region.eq(production_scope)],"region",baseline,c["minimum_n"])
        production=production[production.year.between(*years)]
        temperatures=rainfall=production
    for label,values,col in [("Temperature",temperatures,"temperature_c"),("Rainfall",rainfall,"rainfall_mm")]:
        if label in measures and not values[col+("_anomaly" if use_anomaly else "")].notna().any():
            st.info(label+" is unavailable for this reference period; agricultural bars remain visible.")
    if len(measures)==2:
        fig=production_weather.production_both_weather_figure(production,temperatures,rainfall,
               use_anomaly,use_anomaly,national,overlay_outcome)
    else:
        measure=measures[0]
        fig=production_temperature_figure(production,temperatures if measure=="Temperature" else rainfall,
               use_anomaly,national,climate=measure,outcome=overlay_outcome)
    chart(fig,"production_weather_overlay")
    # st.caption("Measure offers Rainfall and Temperature, Rainfall, or Temperature. Average shows annual mean temperature (C) and annual rainfall (mm), spatially weighted by sown area. Anomaly uses the selected historical reference: temperature difference (C), rainfall difference (%). Separate right axes are used when both measures are selected. Bars show actual Production (tonnes) or Yield (t/ha); National yield is a single total-production / total-area bar. The comparison follows Analysis period and its own National/region selector. Co-movement does not establish causation.")

    section(2,"Are climate conditions associated with production/yield changes, including lagged and nonlinear patterns?")
    unit="regional annual"
    rel=analysis(r,c)
    relationship_label=st.radio("Relationship outcome",["Yield change (%)","Production change (%)"],horizontal=True,key="bp4_relationship_outcome")
    relationship_change="yield_change_pct" if relationship_label=="Yield change (%)" else "production_change_pct"
    a,d,e=st.columns(3)
    form=a.selectbox("Climate representation",["Anomaly","Absolute"],key="bp4_form")
    method=d.selectbox("Correlation method",["Pearson","Spearman"],key="bp4_method")
    lag=e.selectbox("Climate lag (years)",[0,1,2],key="bp4_lag")
    source=r; group="region"
    
    # st.caption(f"Unit: {unit}. Climate(t-{lag}) aligned by calendar year to outcome(t); no future weather. Lag patterns are not proof of delayed agronomic effects.")
    st.subheader("2.1 Main Climate-Outcome Relationships")
    available=[v for v in REGION_ORDER if v in source.region.unique()]
    highlight_mode=st.selectbox("Region highlighting",["All Regions",*available],key="bp4_scatter_highlight")
    highlighted_region=None if highlight_mode=="All Regions" else highlight_mode
    show_regression=st.checkbox("Show regression line",value=False,key="bp4_scatter_regression",disabled=highlighted_region is None)
    # st.caption("All observations remain visible. A specific region highlights its points and enables its optional OLS line. OLS is a descriptive linear fit even when Spearman is selected; it is not a forecast or causal effect.")
    for name,col in CLIMATE.items():
        scatter=relationship_view.aligned_observations(source,col+"_anomaly" if form=="Anomaly" else col,relationship_change,lag,group)
        fig,summary=relationship_view.scatter_view(scatter,name,form,relationship_change,method,highlighted_region,show_regression,c["minimum_n"])
        chart(fig,"relationship_"+name)
        if highlighted_region is not None:
            columns=st.columns(4)
            columns[0].metric("Correlation method",method)
            columns[1].metric("Coefficient",f"{summary['coefficient']:+.3f}" if pd.notna(summary['coefficient']) else "N/A")
            columns[2].metric("Valid observations (n)",summary['n'])
            columns[3].metric("Relationship direction",summary['direction'])
        if highlighted_region is None:st.caption("Select a region to inspect its correlation statistics.")
        elif pd.isna(summary['coefficient']):st.info(name+": N/A - insufficient valid pairs or a constant input. No regression line is drawn.")
        else:st.caption(f"{highlighted_region} | {unit} | lag {lag}. Direction follows the coefficient sign, not a significance claim. Serial dependence limits inference.")
    
    st.subheader("2.2 Regional Climate Sensitivity Comparison")
    st.write("Compare observed climate-outcome associations across regions, not causal sensitivity.")
    # st.caption(f"Regional annual observations only, independent of the pooled/province selector. Outcome: {relationship_label}; {form}; {method}; lag {lag}. Minimum eight annual pairs is a technical requirement, not a reliability guarantee.")
    regional_associations=complementary.associations(r,relationship_change,form,method,lag,max(8,c["minimum_n"]))
    chart(complementary.association_figure(regional_associations,[v for v in REGION_ORDER if v in regions]),"extra_regional_associations")
    # st.caption("Positive coefficients indicate higher climate values accompanying higher outcome changes; negative coefficients indicate the opposite. Near zero means weak linear (Pearson) or monotonic (Spearman) association. N/A denotes too few valid pairs or constant input. No significance or confidence interval is claimed here.")
    with st.expander("Regional association sample sizes and unavailable results"):
        table(regional_associations,"extra_regional_associations")

    st.subheader("2.3 Yield Changes Under Different Climate Conditions" if relationship_change=="yield_change_pct" else "2.3 Production Changes Under Different Climate Conditions")
    box_climate=st.selectbox("Distribution climate",list(CLIMATE),key="bp4_extra_box_climate")
    box_points,box_summary,box_quality=complementary.terciles(r,box_climate,relationship_change,form,lag,max(8,c["minimum_n"]))
    chart(complementary.distribution_figure(box_points,box_summary,relationship_change,box_climate),"extra_climate_distribution")
    # st.caption(f"Regional annual data; {form}, lag {lag}; outcome: {relationship_label}. Terciles use each region's valid climate observations. Values equal to a threshold enter the lower category; collapsed thresholds produce an explicit unavailable region. Low/High are relative climate levels, not good/bad weather. Boxes: median, Q1/Q3 and observed whisker limits within 1.5 IQR. All points, including outliers, are shown; sparse/constant categories show points without a box. No independent-sample significance claim is made.")
    if box_quality.status.ne("Available").any():st.warning("Some regions cannot support distinct climate terciles; inspect the quality table below.")
    if box_summary.n.lt(5).any():st.warning("Some categories have fewer than five observations; distributions are exploratory.")
    with st.expander("Climate-category statistics, thresholds and data quality"):
        table(box_summary,"extra_box_statistics");table(box_quality,"extra_box_quality")

    st.subheader("2.4 Regional Climate-Yield Stability Matrix")
    stability_climate=st.selectbox("Stability climate",list(CLIMATE),key="bp4_extra_stability_climate")
    stable=complementary.stability(r,stability_climate,max(8,c["minimum_n"]))
    chart(complementary.stability_figure(stable,stability_climate),"extra_stability_matrix")
    if stable.quadrant.ne(bi.INSUFFICIENT).sum()<2:st.info("Fewer than two supported regions: cross-region quadrant comparison is unavailable for this selection.")
    # st.caption("Always regional annual, lag 0, anomaly-based climate variability and Yield change (%), independently of other outcome/method/lag choices. X: sample SD of annual climate anomalies; Y: sample SD of yield changes on the same valid years. Bubble area: mean actual annual production over the analysis period. Bubble-size legend shows supply scale. Dotted medians recalculate over valid displayed regions; values equal to a median enter Low. Quadrants are relative descriptions, not resilience/vulnerability classes.")
    if stable.status.ne("Available").any() or stable.quadrant.eq(bi.INSUFFICIENT).any():st.warning("Some regions have insufficient paired years, reference coverage or production data; they are listed below rather than treated as low variability.")
    # st.caption("Agricultural practices, irrigation, geography, technology, cultivated area and other factors can influence these patterns. Low historical yield variability only identifies candidates for further supplier assessment.")
    with st.expander("Stability metrics and unavailable regions"):
        table(stable,"extra_stability_metrics")

    with st.expander("Lag comparison and supporting correlation statistics"):
        climate=st.selectbox("Climate variable",list(CLIMATE),key="bp4_climate")
        rr=rel[rel.form.eq(form)&rel.method.eq(method)&rel.outcome.eq(relationship_change)]
        heat(rr[rr.climate.eq(climate)],"lag","region","coefficient","Calendar-aligned lag associations","lag_correlation")
        table(rr,"relationship_tests")
        st.caption("Nominal confidence intervals/p-values assume independence; temporal dependence limits inference. The lag heatmap compares all three calendar lags simultaneously.")
    # st.caption("Temperature anomaly = difference from reference mean (C); rainfall anomaly = percent of reference mean. Fisher-z nominal intervals (rank approximation for Spearman) assume independence, not corrected for serial/pooled province dependence. Holm q covers all regional/climate/form/outcome/lag/method tests in the selected unit. Production = area x yield in stored units; hover shows all three changes. Climate tercile intervals are nominal t intervals; sparse bins are explicit.")

    section(3,"Review agricultural deviations from the retrospective historical trend alongside annual climate conditions.")
    outcome=st.selectbox("Agricultural outcome",list(OUTCOMES),key="bp4_outcome")
    st.markdown("""<style>
    .st-key-bp4_heatmap_hover .scatterlayer .point:hover {
        stroke: #111 !important;
        stroke-width: 3px !important;
        cursor: pointer;
    }
    </style>""",unsafe_allow_html=True)
    with st.container(key="bp4_heatmap_hover"):
        st.plotly_chart(event_charts.event_heatmap(r,outcome),width="stretch",key="bp4_event_heatmap",
                        config={"displaylogo":False})

    section(4,"Three observations from the complete 2010-2024 historical dataset.")
    st.subheader("4.1 Production rose while rice area fell")
    st.write("From 2010 to 2024, national rice production rose by about 8.6%, while sown area fell by 4.8% and yield rose by 14.1%. When production changes, examine both yield and area.")
    st.subheader("4.2 Climate-yield patterns differ by region")
    st.write("For same-year rainfall anomaly and yield change, the Pearson correlation is about -0.52 in the Northern Midlands and Mountains, -0.50 in the Red River Delta, and near zero in the Mekong Delta. Each region has only 14 yearly changes. These patterns call for regional follow-up, not a national conclusion about rainfall effects.")
    st.subheader("4.3 Below-trend yield occurred under different weather conditions")
    st.write("In 2017, Red River Delta yield was 5.65% below its fitted trend, with rainfall 20.95% above its reference. In 2016, Central Highlands yield was 5.37% below trend with rainfall 33.45% above reference; Mekong Delta yield was 4.59% below trend with rainfall 9.72% below reference. Check seasonal weather, irrigation, rice area, pests, and farming practices for each case.")


render()
