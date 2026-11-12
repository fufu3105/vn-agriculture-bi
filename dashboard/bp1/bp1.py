"""BP1 presentation only: read its own Gold Parquet tables, never raw/silver data."""
from html import escape
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

MART = Path(__file__).resolve().parents[2] / "data/analytics/bp1"
REGION_EN = {
    "Đồng bằng sông Cửu Long": "Mekong Delta",
    "Đồng bằng sông Hồng": "Red River Delta",
    "Bắc Trung Bộ": "North Central Coast",
    "Trung du và miền núi phía Bắc": "Northern Midlands & Mountains",
    "Duyên hải Nam Trung Bộ": "South Central Coast",
    "Tây Nguyên": "Central Highlands",
    "Đông Nam Bộ": "Southeast",
}
REGIONS = list(REGION_EN.values())
# Muted forest, wheat, slate and earth tones, consistent across all charts.
COLORS = dict(zip(REGIONS, ["#356859", "#B29252", "#6F8391", "#8D7069", "#7B8660", "#9A8D72", "#A3B4AC"]))
MART_NAMES = ("province_year", "region_year", "national_year", "province_profile_2010_2024")
METRICS = {
    "Production": ("rice_production_ton", 1_000_000, "million tonnes"),
    "Sown area": ("rice_area_ha", 1_000_000, "million ha"),
    "Yield": ("rice_yield_ton_ha", 1, "tonnes/ha"),
}


@st.cache_data(show_spinner=False)
def load_data(versions):
    # File signatures invalidate cached data after rebuilding the mart.
    frames = tuple(pd.read_parquet(MART / f"{name}.parquet") for name in MART_NAMES)
    for frame in frames:
        if "region" in frame:
            frame["region"] = frame["region"].map(REGION_EN)
            if frame["region"].isna().any():
                raise ValueError("An analytics region is missing its English display name.")
    return frames


def chart_style(fig, height=310, legend=False):
    fig.update_layout(
        height=height, margin=dict(l=10, r=15, t=15, b=15),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Segoe UI, sans-serif", size=12, color="#365345"),
        showlegend=legend, hoverlabel=dict(bgcolor="#FFFFFF"),
        legend=dict(title=None, orientation="h", y=-0.22, x=0),
    )
    fig.update_xaxes(gridcolor="#E9EDE5", zeroline=False)
    fig.update_yaxes(gridcolor="#E9EDE5", zeroline=False)
    return fig


def regional_chart(current, metric):
    column, scale, unit = METRICS[metric]
    if metric == "Production":
        current = current.sort_values(column, ascending=False)
        total = current[column].sum()
        fig = go.Figure(go.Pie(
            labels=current["region"], values=current[column] / scale, hole=0.65,
            marker=dict(colors=[COLORS[r] for r in current["region"]], line=dict(color="white", width=3)),
            textinfo="percent", textposition="outside", sort=False,
            hovertemplate="%{label}<br>%{value:,.2f} million tonnes · %{percent}<extra></extra>",
        ))
        fig.add_annotation(text=f"<b>{total / scale:.2f}</b><br>million tonnes", x=0.5, y=0.5,
                           font_size=22, showarrow=False)
        return chart_style(fig, 300)
    current = current.sort_values(column).assign(value=current[column] / scale)
    fig = px.bar(current, x="value", y="region", orientation="h", color="region",
                 color_discrete_map=COLORS, labels={"value": unit, "region": ""})
    fig.update_traces(hovertemplate="%{y}<br>%{x:,.2f} " + unit + "<extra></extra>")
    return chart_style(fig)


def province_chart(current, metric):
    column, scale, unit = METRICS[metric]
    top = current.nlargest(10, column).sort_values(column).assign(value=lambda d: d[column] / scale)
    fig = px.bar(top, x="value", y="province_name", orientation="h", color="region",
                 color_discrete_map=COLORS, labels={"value": unit, "province_name": ""})
    fig.update_traces(hovertemplate="%{y}<br>%{x:,.3f} " + unit + "<extra></extra>", marker_line_width=0)
    return chart_style(fig)


def history_chart(regions, national, metric, region, year):
    column, scale, unit = METRICS[metric]
    if region == "All regions":
        data, color = regions.copy(), "region"
    else:
        data, color = regions.loc[regions["region"] == region].copy(), "region"
    data["value"] = data[column] / scale
    fig = px.line(data, x="year", y="value", color=color, color_discrete_map=COLORS,
                  labels={"year": "", "value": unit, "region": "Region"}, markers=False)
    fig.update_traces(line_width=2.5, hovertemplate="%{x}: %{y:,.2f} " + unit + "<extra>%{fullData.name}</extra>")
    fig.add_vline(x=year, line_width=1, line_dash="dot", line_color="#9C742B")
    fig.update_xaxes(dtick=2, tickformat="d")
    fig.update_layout(hovermode="x unified")
    return chart_style(fig, 330, legend=True)


def profile_chart(current):
    subset = current.loc[current["rice_production_ton"] >= 500_000].dropna(
        subset=["production_cagr_pct", "production_yoy_std_pp"])
    if subset.empty:
        return None
    fig = px.scatter(
        subset, x="production_yoy_std_pp", y="production_cagr_pct", size="rice_production_ton",
        color="region", color_discrete_map=COLORS, hover_name="province_name", size_max=30,
        labels={"production_yoy_std_pp": "Growth volatility (pp)", "production_cagr_pct": "Production CAGR (%)",
                "rice_production_ton": "2024 production (tonnes)", "region": "Region"},
        hover_data={"production_yoy_std_pp": ":.2f", "production_cagr_pct": ":.2f", "rice_production_ton": ":,.0f"},
    )
    fig.update_traces(marker=dict(line=dict(color="white", width=1), opacity=0.9))
    fig.add_hline(y=0, line_dash="dot", line_color="#AFBEAF")
    return chart_style(fig, 330)


def delta(value):
    return None if pd.isna(value) else f"{value:+.2f}% vs. previous year"


def render():
    try:
        signatures = tuple((p.stat().st_mtime_ns, p.stat().st_size) for p in
                           [MART / f"{name}.parquet" for name in MART_NAMES])
        provinces, regions, national, full_profile = load_data(signatures)
    except (FileNotFoundError, OSError, ValueError) as exc:
        st.error("BP1 analytics could not be loaded. Build the data mart before opening the dashboard.")
        st.code("python src/bp1/bp1.py", language="bash")
        with st.expander("Error details"):
            st.text(str(exc))
        st.stop()

    # Preserve selections when an existing browser session switches to English.
    aliases = {
        "bp1_region": {"Tất cả vùng": "All regions", **REGION_EN},
        "bp1_metric": {"Sản lượng": "Production", "Diện tích": "Sown area", "Năng suất": "Yield"},
        "bp1_view": {"Tổng quan": "Overview", "Dữ liệu & phương pháp": "Data & methods"},
    }
    for key, translations in aliases.items():
        previous = st.session_state.get(key)
        if previous in translations:
            st.session_state[key] = translations[previous]

    st.markdown('<div class="eyebrow">BP1 / DESCRIPTIVE ANALYTICS</div>', unsafe_allow_html=True)
    st.title("Rice production overview")
    st.markdown("Compare production scale, sown area, yield and historical trends to identify potential sourcing regions.")
    with st.container(border=True):
        filters = st.columns([1, 2, 1.3])
        year = filters[0].selectbox("Statistical year", sorted(provinces["year"].unique(), reverse=True), key="bp1_year")
        region = filters[1].selectbox("Analysis scope", ["All regions", *REGIONS], key="bp1_region")
        metric = filters[2].selectbox(
            "Chart metric", list(METRICS), key="bp1_metric",
            help="Production: total harvested paddy rice (tonnes). Sown area: total area planted across cropping seasons (ha). Yield: output per hectare (tonnes/ha).",
        )

    current = provinces.loc[provinces["year"] == year]
    regional = regions.loc[regions["year"] == year]
    if region == "All regions":
        summary = national.loc[national["year"] == year].iloc[0]
    else:
        current = current.loc[current["region"] == region]
        summary = regional.loc[regional["region"] == region].iloc[0]
        full_profile = full_profile.loc[full_profile["region"] == region]
    st.caption(f"{int(year)} · {region} · {len(current)} provinces under historical boundaries")
    cards = st.columns(4)
    cards[0].metric("RICE PRODUCTION", f"{summary.rice_production_ton / 1e6:,.2f} million tonnes", delta(summary.production_yoy_pct), border=True,
                    help="Total harvested paddy rice during the year, measured in tonnes.")
    cards[1].metric("RICE SOWN AREA", f"{summary.rice_area_ha / 1e6:,.2f} million ha", delta(summary.area_yoy_pct), border=True,
                    help="Area planted with rice across all cropping seasons. The same plot is counted again if planted in another season.")
    cards[2].metric("WEIGHTED AVERAGE YIELD", f"{summary.rice_yield_ton_ha:.2f} tonnes/ha", delta(summary.yield_yoy_pct), border=True,
                    help="Harvested output per sown hectare. Regional/national values weight provincial yields by their sown area.")
    cards[3].metric("PROVINCES / CITIES", str(len(current)), "63 historical provinces nationwide", delta_color="off", border=True)

    with st.expander("Production, sown area and yield — what is the difference?"):
        definitions = st.columns(3)
        definitions[0].markdown("**Production · tonnes**\n\nThe total quantity of paddy rice harvested during the year. This describes output volume.")
        definitions[1].markdown("**Sown area · hectares**\n\nThe area planted across all cropping seasons. A 50 ha plot planted twice contributes 100 ha of annual sown area.")
        definitions[2].markdown("**Yield · tonnes per hectare**\n\nThe amount harvested per sown hectare. This describes productivity, rather than total output or land area.")
        st.markdown("**Example:** 100 ha of sown area × 6 tonnes/ha of yield ≈ 600 tonnes of production.")
        st.caption("The relationship is approximate for these published tables because of reporting and rounding differences. Production is kept as officially reported.")

    view = st.segmented_control(
        "View", ["Overview", "Data & methods"],
        default=None if "bp1_view" in st.session_state else "Overview",
        key="bp1_view", label_visibility="collapsed",
    )
    if view == "Data & methods":
        st.subheader("Data for the selected scope")
        table = current[["province_name", "region", *[m[0] for m in METRICS.values()],
                         "production_share_pct", "production_yoy_pct"]].sort_values("rice_production_ton", ascending=False)
        table = table.rename(columns={
            "province_name": "Province / city", "region": "Region", "rice_production_ton": "Production (tonnes)",
            "rice_area_ha": "Sown area (ha)", "rice_yield_ton_ha": "Yield (tonnes/ha)",
            "production_share_pct": "National production share (%)", "production_yoy_pct": "Annual production change (%)",
        })
        st.dataframe(table, hide_index=True, width="stretch")
        st.download_button("Download current table (CSV)", table.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"bp1_{int(year)}.csv", mime="text/csv", icon=":material/download:")
        st.subheader("Fixed production profile · 2010–2024")
        st.caption("All provinces in the selected region are listed. Chart 04 plots only those producing at least 500,000 tonnes in 2024; the statistical-year selector does not change this profile.")
        profile_table = full_profile[["province_name", "region", "rice_production_ton", "production_cagr_pct", "production_yoy_std_pp"]].rename(columns={
            "province_name": "Province / city", "region": "Region", "rice_production_ton": "2024 production (tonnes)",
            "production_cagr_pct": "2010–2024 CAGR (%)", "production_yoy_std_pp": "2010–2024 volatility (pp)",
        }).sort_values("2024 production (tonnes)", ascending=False)
        st.dataframe(profile_table, hide_index=True, width="stretch")
        st.subheader("Methods and limitations")
        st.markdown(
            "- Source: NSO V06.13 (sown area), V06.14 (yield) and V06.15 (production); 2010–2024, covering 63 historical provinces.\n"
            "- Sown area sums all rice cropping seasons within a year. Production comes from the published statistics, rather than area × yield.\n"
            "- Regional and national yields are averages of provincial yields weighted by sown area.\n"
            "- Annual change = (current value / previous value − 1) × 100. Production shares always use the national total.\n"
            "- Chart 04 always uses 2010–2024: CAGR = ((2024 production / 2010 production)^(1/14) − 1) × 100. "
            "Volatility is the sample standard deviation of the 14 annual growth rates from 2011 to 2024. Bubble size and the production threshold use 2024 output.\n"
            "- The statistical-year selector affects the annual KPIs, charts 01–02, the reference line in chart 03 and the annual table. "
            "It does not change chart 04. The region selector applies to both annual results and the fixed production profile.\n"
            "- These indicators describe history and do not establish causes or predict future outcomes. Production represents potential supply, "
            "rather than a guaranteed procurement quantity."
        )
        return

    leader = current.sort_values("rice_production_ton", ascending=False).iloc[0]
    st.markdown(f'<div class="insight"><span>HIGHLIGHT {int(year)}</span><br><strong>{escape(leader.province_name)}</strong> '
                f'leads production in the selected scope with <strong>{leader.rice_production_ton / 1e6:.2f} million tonnes</strong> '
                f'· accounting for {leader.production_share_pct:.2f}% of national production.</div>', unsafe_allow_html=True)
    left, right = st.columns(2)
    with left, st.container(border=True):
        st.subheader("01 · Regional comparison")
        st.caption(f"{metric} in {int(year)} · nationwide comparison")
        st.plotly_chart(regional_chart(regional, metric), width="stretch", config={"displayModeBar": False})
        if metric == "Production":
            st.markdown('<div class="chart-legend">' + ''.join(
                f'<span><i style="background:{COLORS[r]}"></i>{escape(r)}</span>' for r in REGIONS
            ) + '</div>', unsafe_allow_html=True)
    with right, st.container(border=True):
        st.subheader("02 · Leading provinces")
        st.caption(f"Top 10 provinces by {metric.lower()} · {region}")
        st.plotly_chart(province_chart(current, metric), width="stretch", config={"displayModeBar": False})
    left, right = st.columns(2)
    with left, st.container(border=True):
        st.subheader("03 · Historical trends")
        st.caption(f"{metric} · vertical line marks the selected year")
        st.plotly_chart(history_chart(regions, national, metric, region, year), width="stretch", config={"displayModeBar": False})
    with right, st.container(border=True):
        st.subheader("04 · Growth & volatility · 2010–2024")
        st.caption("Fixed full-period analysis · bubble size = 2024 production · minimum 500,000 tonnes in 2024")
        profile = profile_chart(full_profile)
        if profile is None:
            st.info("There is insufficient growth history, or no province meets the production threshold in this scope.")
        else:
            st.plotly_chart(profile, width="stretch", config={"displayModeBar": False})
        st.caption("The year selector does not change this chart. The region selector still applies.")
    st.caption("Source: National Statistics Office of Vietnam · Production indicates potential supply. Supplier selection also requires price, quality and logistics information.")


render()
