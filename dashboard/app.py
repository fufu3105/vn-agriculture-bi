"""Compact BP1 rice sourcing dashboard (historical 63-province convention)."""

from pathlib import Path
from html import escape

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
FIRST_COMPARISON_YEAR = 2015
REGION_EN = {
    "Đồng bằng sông Cửu Long": "Mekong Delta",
    "Đồng bằng sông Hồng": "Red River Delta",
    "Bắc Trung Bộ": "North Central Coast",
    "Trung du và miền núi phía Bắc": "Northern Midlands & Mountains",
    "Duyên hải Nam Trung Bộ": "South Central Coast",
    "Tây Nguyên": "Central Highlands",
    "Đông Nam Bộ": "Southeast",
}
REGION_ORDER = list(REGION_EN.values())
COLORS = ["#078365", "#2471A3", "#E69F28", "#8856A7", "#D55E64", "#4F9E45", "#6B7785"]
REGION_COLOR = dict(zip(REGION_ORDER, COLORS))
CHART_HEIGHT = 205


@st.cache_data
def load_data():
    panel = pd.read_csv(DATA / "processed" / "rice_province_year.csv")
    regions = pd.read_csv(DATA / "analytics" / "bp1_region_summary.csv")
    panel["region_en"] = panel["region"].map(REGION_EN)
    regions["region_en"] = regions["name"].map(REGION_EN)
    if panel["region_en"].isna().any():
        raise ValueError("A region in the panel is missing from REGION_EN")
    return panel, regions


def finish_chart(fig, *, height=CHART_HEIGHT, legend=False):
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(family="Segoe UI, Arial, sans-serif", size=11, color="#263c3b"),
        showlegend=legend,
        hoverlabel=dict(bgcolor="white", font_size=11),
    )
    return fig


def region_share_chart(regional):
    ordered = regional.set_index("region_en").reindex(REGION_ORDER)
    national = float(ordered["production_thousand_tons"].sum())
    labels = [
        f"{region}  {value / national:.1%}"
        for region, value in ordered["production_thousand_tons"].items()
    ]
    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=ordered["production_thousand_tons"],
            marker=dict(colors=COLORS, line=dict(color="white", width=1)),
            hole=0.48,
            sort=False,
            textinfo="none",
            domain=dict(x=[0.0, 0.51], y=[0, 1]),
            hovertemplate="%{label}<br>%{value:,.0f} thousand tonnes<extra></extra>",
        )
    )
    finish_chart(fig, height=220, legend=True)
    fig.update_layout(
        legend=dict(orientation="v", x=0.54, y=0.95, font_size=11, title=None),
        margin=dict(l=5, r=5, t=5, b=5),
    )
    return fig


def province_flow_chart(current, region_en):
    """Readable region-to-province flow with labels outside the ribbons."""
    chosen = current.loc[current["region_en"] == region_en].sort_values(
        "production_thousand_tons", ascending=False
    )
    if chosen.empty:
        raise ValueError(f"No province data for {region_en}")
    top = chosen.head(5)
    other = float(chosen.iloc[5:]["production_thousand_tons"].sum())
    names = top["province"].tolist() + (["Other provinces"] if other > 0 else [])
    values = top["production_thousand_tons"].astype(float).tolist() + ([other] if other > 0 else [])
    total = float(chosen["production_thousand_tons"].sum())
    if abs(sum(values) - total) > 0.01:
        raise ValueError("Sankey values do not reconcile with regional production")
    count = len(names)
    fig = go.Figure()
    source_top = 0.86
    source_span = 0.72
    max_value = max(values)
    for index, (name, value) in enumerate(zip(names, values)):
        share = value / total
        source_bottom = source_top - source_span * share
        center = 0.86 - index * (0.72 / (count - 1)) if count > 1 else 0.50
        half_height = 0.047 * value / max_value
        target_top = center + half_height
        target_bottom = center - half_height
        path = (
            f"M 0.14,{source_top:.5f} "
            f"C 0.35,{source_top:.5f} 0.53,{target_top:.5f} 0.72,{target_top:.5f} "
            f"L 0.72,{target_bottom:.5f} "
            f"C 0.53,{target_bottom:.5f} 0.35,{source_bottom:.5f} 0.14,{source_bottom:.5f} Z"
        )
        fig.add_shape(
            type="path", path=path, xref="x", yref="y",
            fillcolor="rgba(7, 131, 101, 0.20)", line=dict(width=0),
            layer="below",
        )
        fig.add_shape(
            type="rect", x0=0.72, x1=0.74, y0=target_bottom, y1=target_top,
            fillcolor="#2F806E" if index < 5 else "#93A39E",
            line=dict(width=0),
        )
        fig.add_annotation(
            x=0.76, y=center, xanchor="left", yanchor="middle", showarrow=False,
            text=f"<b>{escape(name)}</b><br>{value:,.0f} kt",
            align="left", font=dict(size=12, color="#173C34"),
        )
        fig.add_trace(go.Scatter(
            x=[0.73], y=[center], mode="markers",
            marker=dict(size=16, color="rgba(0,0,0,0)"),
            hovertemplate=f"{escape(name)}<br>{value:,.0f} thousand tonnes<extra></extra>",
            showlegend=False,
        ))
        source_top = source_bottom
    fig.add_shape(
        type="rect", x0=0.12, x1=0.14, y0=0.14, y1=0.86,
        fillcolor=REGION_COLOR[region_en], line=dict(width=0),
    )
    fig.add_annotation(
        x=0.11, y=0.50, xanchor="right", yanchor="middle", showarrow=False,
        text="<b>Total</b>", font=dict(size=11, color="#173C34"),
    )
    fig.add_annotation(
        x=0.12, y=0.94, xanchor="left", yanchor="middle", showarrow=False,
        text=f"<b>{total / 1000:,.2f} Mt</b>", font=dict(size=13, color="#173C34"),
    )
    finish_chart(fig, height=220)
    fig.update_layout(
        xaxis=dict(range=[0, 1], visible=False, fixedrange=True),
        yaxis=dict(range=[0, 1], visible=False, fixedrange=True),
        margin=dict(l=6, r=6, t=2, b=2),
        meta=dict(region=region_en, total_thousand_tons=total, destinations=dict(zip(names, values))),
    )
    return fig


def profile_window_start(year):
    return max(int(year) - 9, 2010)


def province_profile_data(panel, year):
    """Use only years through the selected year for a trailing provincial profile."""
    start = profile_window_start(year)
    if year - start < 2:
        raise ValueError("At least two annual changes are needed for volatility")
    wide = (
        panel.loc[panel["year"].between(start, year)]
        .pivot(index=["province", "region_en"], columns="year", values="production_thousand_tons")
    )
    expected_years = list(range(start, year + 1))
    if list(wide.columns) != expected_years or wide.isna().any().any():
        raise ValueError("Provincial production history is incomplete")
    annual_growth = wide.pct_change(axis=1, fill_method=None).iloc[:, 1:] * 100
    output = pd.DataFrame(
        {
            "province": wide.index.get_level_values("province"),
            "region_en": wide.index.get_level_values("region_en"),
            "production_thousand_tons": wide[year].to_numpy(),
            "cagr_pct": (wide[year].to_numpy() / wide[start].to_numpy())
            ** (1 / (year - start)) * 100 - 100,
            "yoy_sd_pct_points": annual_growth.std(axis=1, ddof=1).to_numpy(),
        }
    )
    return output.sort_values("production_thousand_tons", ascending=False).reset_index(drop=True)


def province_profile_chart(profile):
    subset = profile.loc[profile["production_thousand_tons"] >= 500].copy()
    fig = px.scatter(
        subset,
        x="yoy_sd_pct_points",
        y="cagr_pct",
        size="production_thousand_tons",
        color="region_en",
        color_discrete_map=REGION_COLOR,
        hover_name="province",
        hover_data={
            "region_en": True,
            "production_thousand_tons": ":,.0f",
            "yoy_sd_pct_points": ":.1f",
            "cagr_pct": ":.1f",
        },
        labels={
            "region_en": "Region",
            "production_thousand_tons": "Production (thousand tonnes)",
            "yoy_sd_pct_points": "Growth volatility (pp)",
            "cagr_pct": "CAGR (%)",
        },
        size_max=24,
    )
    finish_chart(fig)
    fig.update_xaxes(title="Growth volatility (pp)", zeroline=False)
    fig.update_yaxes(title="CAGR (%)", zeroline=True, zerolinecolor="#B8CAC4")
    fig.update_layout(margin=dict(l=34, r=8, t=5, b=38))
    return fig


def regional_history_chart(panel):
    annual = (
        panel.groupby(["year", "region_en"], as_index=False)["production_thousand_tons"]
        .sum()
    )
    annual["production_million_tons"] = annual["production_thousand_tons"] / 1000
    fig = px.line(
        annual,
        x="year",
        y="production_million_tons",
        color="region_en",
        category_orders={"region_en": REGION_ORDER},
        color_discrete_map=REGION_COLOR,
        markers=False,
        custom_data=["region_en"],
    )
    fig.update_traces(
        line_width=2.5,
        hovertemplate="%{customdata[0]} · %{x}<br>%{y:,.2f} million tonnes<extra></extra>",
    )
    finish_chart(fig, height=165)
    fig.update_layout(
        margin=dict(l=33, r=6, t=5, b=30),
        hovermode="x unified",
    )
    fig.update_xaxes(title=None, dtick=2, tickformat="d", showgrid=False)
    fig.update_yaxes(title="Million tonnes", gridcolor="#EDF2F0", zeroline=False)
    return fig


def region_legend_html():
    items = "".join(
        f'<span><i style="background:{REGION_COLOR[region]}"></i>{escape(region)}</span>'
        for region in REGION_ORDER
    )
    return f'<div class="region-key">{items}</div>'


st.set_page_config(page_title="BP1 · Rice sourcing regions", layout="wide")
st.markdown(
    """<style>
    header[data-testid="stHeader"] {display: none !important;}
    .block-container {max-width: 1550px; padding: .6rem 1rem .5rem;}
    h1 {font-size: 1.5rem !important; line-height: 1.25 !important; padding: 0 !important; margin: 0 !important;}
    div[data-testid="stVerticalBlock"] {gap: .55rem;}
    div[data-testid="stMarkdownContainer"]:has(h1) {margin-bottom: 0 !important;}
    div[data-testid="stMarkdownContainer"]:has(.chart-title) {margin-bottom: 0 !important;}
    .chart-title {font-size: .91rem; font-weight: 700; color: #173c34; line-height: 1.25; margin: .1rem 0 .25rem;}
    .chart-hint {font-size:.72rem; font-weight:400; color:#536963; margin-left:.45rem;}
    .region-key {display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:2px 7px; margin:0 .35rem .15rem;}
    .region-key span {display:flex; align-items:center; font-size:10px; line-height:1.25; color:#263c3b; white-space:nowrap;}
    .region-key i {display:inline-block; width:14px; height:3px; margin-right:5px; flex:none;}
    @media (max-width: 900px) {
      .block-container {padding-top: .8rem;}
      .region-key {grid-template-columns:repeat(2,minmax(0,1fr)); gap:3px 6px;}
      .region-key span {font-size:11px; white-space:normal;}
    }
    </style>""",
    unsafe_allow_html=True,
)

panel, regions = load_data()
year_options = [
    int(y) for y in sorted(panel["year"].unique(), reverse=True)
    if y >= FIRST_COMPARISON_YEAR
]
if st.session_state.get("bp1_year") not in year_options:
    st.session_state["bp1_year"] = year_options[0]
if st.session_state.get("bp1_region") not in REGION_ORDER:
    st.session_state["bp1_region"] = REGION_ORDER[0]
st.title("BP1 · Rice sourcing regions")
view = st.segmented_control(
    "View", ["Dashboard", "Data and methods"], default="Dashboard",
    label_visibility="collapsed",
)

if view == "Dashboard":
    left_top, right_top = st.columns(2)
    with left_top:
        with st.container(border=True):
            year = st.selectbox(
                "Year", year_options,
                index=year_options.index(st.session_state["bp1_year"]),
                label_visibility="collapsed", key="bp1_year_widget",
            )
            st.session_state["bp1_year"] = int(year)
            current = panel.loc[panel["year"] == year].copy()
            regional = (
                current.groupby("region_en", as_index=False)["production_thousand_tons"]
                .sum()
                .sort_values("production_thousand_tons", ascending=False)
            )
            national = float(regional["production_thousand_tons"].sum())
            st.markdown(
                f'<div class="chart-title">1 · Regional share · {national / 1000:,.2f} Mt</div>',
                unsafe_allow_html=True,
            )
            st.plotly_chart(region_share_chart(regional), width="stretch", config={"displayModeBar": False})
    with right_top:
        with st.container(border=True):
            flow_region = st.selectbox(
                "Region", REGION_ORDER,
                index=REGION_ORDER.index(st.session_state["bp1_region"]),
                label_visibility="collapsed", key="bp1_region_widget",
            )
            st.session_state["bp1_region"] = flow_region
            st.markdown(
                f'<div class="chart-title">2 · Production flow to provinces · {year}</div>',
                unsafe_allow_html=True,
            )
            st.plotly_chart(province_flow_chart(current, flow_region), width="stretch", config={"displayModeBar": False})

    left_bottom, right_bottom = st.columns(2)
    with left_bottom:
        with st.container(border=True):
            profile_start = profile_window_start(year)
            profile = province_profile_data(panel, year)
            st.markdown(
                f'<div class="chart-title">3 · Provincial profile · {profile_start}–{year}'
                '<span class="chart-hint">size = production · x = volatility · y = CAGR</span></div>',
                unsafe_allow_html=True,
            )
            st.plotly_chart(province_profile_chart(profile), width="stretch", config={"displayModeBar": False})
    with right_bottom:
        with st.container(border=True):
            st.markdown(
                '<div class="chart-title">4 · Regional production across years · 2010–2024</div>',
                unsafe_allow_html=True,
            )
            st.plotly_chart(regional_history_chart(panel), width="stretch", config={"displayModeBar": False})
            st.markdown(region_legend_html(), unsafe_allow_html=True)
if view == "Data and methods":
    selected_year = st.session_state["bp1_year"]
    profile_start = profile_window_start(selected_year)
    profile = province_profile_data(panel, selected_year)
    st.markdown(
        "**Read the charts.** The pie compares the selected year's seven-region shares. "
        "The flow splits one region into its five largest provinces and the remainder; "
        "line width is proportional to production. In chart 3, bubble size is the selected "
        "year's production, the vertical axis is annualized growth (CAGR), and the "
        "horizontal axis is the standard deviation of annual growth rates. It plots "
        "provinces producing at least 500 thousand tonnes in the selected year. "
        "The line chart compares all seven regions in absolute production across 2010–2024. "
        "Colors identify the same regions in charts 1, 3 and 4. Hover for exact values."
    )
    st.markdown(
        "**Units and scope.** The pie and line chart show million tonnes; the flow labels "
        "use thousand tonnes (kt). CAGR and volatility are descriptive historical measures; "
        "they are not forecasts. The year selector changes charts 1, 2, and 3. "
        f"Chart 3 currently uses {profile_start}–{selected_year}: the latest ten years "
        "available up to the selected year, or all available years since 2010. "
        "The year selector starts in 2015 so that volatility has at least five annual "
        "growth observations. Chart 4 always shows 2010–2024. "
        "The source is NSO PX-Web tables V06.13, V06.14 and V06.15, joined to the "
        "team's seven-region JSON. Values are provincial totals and may differ slightly "
        "from national published totals because of rounding."
    )
    st.markdown(
        "**Decision boundary.** Production is potential supply, not procurement availability. "
        "Historical boundaries follow the supplied seven-region mapping. Final sourcing "
        "choices require supplier, price, quality, and logistics information."
    )
    st.markdown("**Regional benchmark, 2024**")
    region_table = regions[
        ["region_en", "production_2024_thousand_tons", "share_2024_pct", "cagr_pct", "yoy_sd_pct_points"]
    ].rename(columns={
        "region_en": "Region",
        "production_2024_thousand_tons": "2024 production (thousand tonnes)",
        "share_2024_pct": "2024 national share (%)",
        "cagr_pct": "2015–2024 CAGR (%)",
        "yoy_sd_pct_points": "Growth volatility (pp)",
    })
    st.dataframe(region_table, hide_index=True, width="stretch")
    st.markdown(f"**Provincial profile, {profile_start}–{selected_year} (all 63 provinces)**")
    province_table = profile.rename(columns={
        "province": "Province", "region_en": "Region",
        "production_thousand_tons": f"{selected_year} production (thousand tonnes)",
        "cagr_pct": f"{profile_start}–{selected_year} CAGR (%)",
        "yoy_sd_pct_points": "Growth volatility (pp)",
    })
    st.dataframe(province_table, hide_index=True, width="stretch")
