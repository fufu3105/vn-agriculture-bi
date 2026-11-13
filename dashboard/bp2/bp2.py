"""BP2 presentation. Read the production-change mart from the shared app."""

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


MART = Path(__file__).resolve().parents[2] / "data/analytics/bp2/production_changes.parquet"
NATIONAL = "Vietnam"
REGION_NAMES = {
    "Đồng bằng sông Cửu Long": "Mekong Delta",
    "Đồng bằng sông Hồng": "Red River Delta",
    "Bắc Trung Bộ": "North Central Coast",
    "Trung du và miền núi phía Bắc": "Northern Midlands & Mountains",
    "Duyên hải Nam Trung Bộ": "South Central Coast",
    "Tây Nguyên": "Central Highlands",
    "Đông Nam Bộ": "Southeast",
}
CHANGE = "production_change_ton"
COMPONENTS = {
    "area_effect_ton": ("Sown area", "#287650"),
    "yield_effect_ton": ("Yield", "#AA7C21"),
    "residual_change_ton": ("Reporting difference", "#AC5A38"),
}
INDICATORS = {CHANGE: ("Reported change", "#304D58"), **COMPONENTS}
UNIT = "Thousand tonnes"
VIEWS = ("Overview", "Compare places", "Year by year", "Area vs. yield")
COLUMNS = [
    "year_start", "year_end", "level", "province_name", "region", "province_count",
    "rice_production_ton_start", "rice_production_ton_end", *INDICATORS,
]


@st.cache_data(show_spinner=False)
def load_bp2_data(path, modified_ns, size):
    frame = pd.read_parquet(path, columns=COLUMNS)
    numeric = [
        "year_start", "year_end", "province_count", "rice_production_ton_start",
        "rice_production_ton_end", *INDICATORS,
    ]
    if frame.empty or not all(pd.api.types.is_numeric_dtype(frame[col]) for col in numeric):
        raise ValueError("Expected a nonempty BP2 mart with numeric years and measurements.")
    if frame[numeric].isin([float("inf"), float("-inf")]).any().any() or frame[numeric].isna().any().any():
        raise ValueError("The BP2 mart contains missing or nonfinite measurements.")
    return frame


def style_chart(fig, height):
    fig.update_layout(
        template="plotly_white", height=height,
        margin=dict(l=8, r=14, t=46, b=12),
        legend=dict(orientation="h", x=0, y=1.02, yanchor="bottom"),
        font=dict(family="Segoe UI, sans-serif", size=12, color="#365345"),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(bgcolor="#FFFFFF", font_color="#203D32"),
    )


def signed_tonnes(value):
    return f"{value / 1_000:+,.2f}"


def waterfall(row):
    fig = go.Figure()
    running_total = 0.0
    bar_width = 0.68
    for index, (field, (label, color)) in enumerate(COMPONENTS.items()):
        value = row[field] / 1_000
        next_total = running_total + value
        fig.add_bar(
            x=[label], y=[abs(value)], base=[min(running_total, next_total)],
            width=bar_width, name=label, marker_color=color, customdata=[value],
            hovertemplate="%{x}<br>%{customdata:+,.2f} thousand tonnes<extra></extra>",
        )
        fig.add_shape(
            type="line", x0=index + bar_width / 2, x1=index + 1 - bar_width / 2,
            y0=next_total, y1=next_total,
            line=dict(color="#819587", width=1.5, dash="dot"),
        )
        fig.add_annotation(
            x=label, y=next_total, text=signed_tonnes(row[field]), showarrow=False,
            yshift=12 if value >= 0 else -12, font=dict(color="#203D32"),
        )
        running_total = next_total

    label, color = INDICATORS[CHANGE]
    total = row[CHANGE] / 1_000
    fig.add_bar(
        x=[label], y=[abs(total)], base=[min(0, total)],
        width=bar_width, name=label, marker_color=color, customdata=[total],
        hovertemplate="%{x}<br>%{customdata:+,.2f} thousand tonnes<extra></extra>",
    )
    fig.add_annotation(
        x=label, y=total, text=signed_tonnes(row[CHANGE]), showarrow=False,
        yshift=12 if total >= 0 else -12, font=dict(color="#203D32"),
    )
    style_chart(fig, 370)
    fig.update_layout(barmode="overlay", legend_itemclick=False, legend_itemdoubleclick=False)
    levels = [0, total, *(shape.y0 for shape in fig.layout.shapes)]
    padding = max((max(levels) - min(levels)) * 0.14, 0.01)
    fig.update_yaxes(
        title_text=UNIT, zeroline=True, zerolinecolor="#84998B", gridcolor="#E9EDE5",
        range=[min(levels) - padding, max(levels) + padding],
    )
    return fig


def place_dot_plot(rows, field):
    fig = go.Figure()
    label, color = INDICATORS[field]
    values = rows[field] / 1_000
    for place, value in zip(rows["place"], values):
        fig.add_shape(
            type="line", x0=0, x1=value, y0=place, y1=place,
            line=dict(color="#A5B5AA", width=2), layer="below",
        )
    fig.add_trace(go.Scatter(
        x=values, y=rows["place"], mode="markers+text", name=label,
        marker=dict(color=color, size=12, line=dict(color="#FFFFFF", width=1)),
        text=rows[field].map(signed_tonnes),
        textposition="middle right",
        customdata=rows[CHANGE] / 1_000,
        hovertemplate=(
            "%{y}<br>%{fullData.name} %{x:+,.2f} thousand tonnes"
            "<br>Reported change %{customdata:+,.2f}<extra></extra>"
        ),
        cliponaxis=False,
    ))
    style_chart(fig, max(340, 42 * len(rows) + 95))
    fig.update_layout(showlegend=False, margin=dict(r=58))
    fig.update_yaxes(automargin=True, autorange="reversed", categoryorder="array", categoryarray=rows["place"].tolist())
    left, right = min(0, values.min()), max(0, values.max())
    padding = max((right - left) * 0.16, 0.01)
    fig.update_xaxes(
        title_text=UNIT, zeroline=True, zerolinecolor="#84998B", gridcolor="#E9EDE5",
        range=[left - padding, right + padding],
    )
    return fig


def annual_heatmap(rows, field):
    matrix = rows.pivot(index="place", columns="year_end", values=field).sort_index().div(1_000)
    scale = max(matrix.abs().max().max(), 0.01)
    labels = matrix.apply(lambda column: column.map(
        lambda value: f"{value:+,.0f}" if abs(value) >= 0.5 else "≈0"
    ))
    fig = go.Figure(go.Heatmap(
        x=matrix.columns.astype(str).tolist(), y=matrix.index.tolist(), z=matrix.to_numpy(),
        zmin=-scale, zmax=scale,
        colorscale=[[0, "#D99B90"], [0.5, "#F5F3EA"], [1, "#8FC5B3"]],
        xgap=2, ygap=2, hoverongaps=False,
        text=labels.to_numpy() if len(matrix) <= 10 and len(matrix.columns) <= 10 else None,
        texttemplate="%{text}" if len(matrix) <= 10 and len(matrix.columns) <= 10 else None,
        textfont=dict(size=10),
        colorbar=dict(title=dict(text=UNIT), orientation="h", x=0.5, y=-0.32, len=0.65, thickness=12),
        hovertemplate="%{y} · %{x} vs prior year<br>%{z:+,.2f} thousand tonnes<extra></extra>",
    ))
    style_chart(fig, max(340, 25 * len(matrix) + 160))
    fig.update_layout(margin=dict(l=8, r=14, t=10, b=110))
    fig.update_xaxes(type="category", tickangle=-40, showgrid=False)
    fig.update_yaxes(autorange="reversed", automargin=True, showgrid=False)
    return fig


def driver_quadrants(rows):
    fig = go.Figure()
    x = rows["area_effect_ton"] / 1_000
    y = rows["yield_effect_ton"] / 1_000
    opposite = x.mul(y).lt(0)
    label_places = set(rows.loc[rows[CHANGE].abs().nlargest(3).index, "place"])
    if opposite.any():
        label_places.add(rows.loc[rows.loc[opposite, CHANGE].abs().idxmax(), "place"])
    xlim = max(x.abs().max() * 1.28, 1)
    ylim = max(y.abs().max() * 1.28, 1)
    for name, xpositive, ypositive in (
        ("Both add", True, True), ("Area offsets yield", True, False),
        ("Yield offsets area", False, True), ("Both reduce", False, False),
    ):
        fig.add_shape(
            type="rect", x0=0 if xpositive else -xlim, x1=xlim if xpositive else 0,
            y0=0 if ypositive else -ylim, y1=ylim if ypositive else 0,
            fillcolor="#EDF5EA" if xpositive and ypositive else "#FBF0E9" if not xpositive and not ypositive else "#F8F5E8",
            line_width=0, layer="below",
        )
        fig.add_annotation(
            x=xlim * (0.68 if xpositive else -0.68),
            y=ylim * (0.88 if ypositive else -0.88),
            text=name, showarrow=False, font=dict(size=11, color="#64766B"),
        )
    for direction, color, mask in (
        ("Reported increase", "#19765C", rows[CHANGE].gt(0)),
        ("Reported decrease", "#B44E42", rows[CHANGE].lt(0)),
        ("No reported change", "#596A68", rows[CHANGE].eq(0)),
    ):
        subset = rows.loc[mask]
        if subset.empty:
            continue
        fig.add_trace(go.Scatter(
            x=subset["area_effect_ton"] / 1_000,
            y=subset["yield_effect_ton"] / 1_000,
            mode="markers+text", name=direction,
            marker=dict(color=color, size=13, line=dict(color="#FFFFFF", width=1.5)),
            text=subset["place"].where(subset["place"].isin(label_places), ""),
            textposition="top center", cliponaxis=False,
            customdata=subset[["place", CHANGE, "residual_change_ton"]].to_numpy(),
            hovertemplate=(
                "%{customdata[0]}<br>Sown area %{x:+,.2f} thousand tonnes"
                "<br>Yield %{y:+,.2f} thousand tonnes"
                "<br>Reporting difference %{customdata[2]:+,.0f} tonnes"
                "<br>Reported change %{customdata[1]:+,.0f} tonnes<extra></extra>"
            ),
        ))
    style_chart(fig, 520)
    fig.update_layout(margin=dict(l=10, r=20, t=55, b=20))
    fig.update_xaxes(
        title_text=f"Sown area contribution · {UNIT.lower()}",
        range=[-xlim, xlim], zeroline=True, zerolinecolor="#287650", zerolinewidth=2,
        gridcolor="#E5EAE4",
    )
    fig.update_yaxes(
        title_text=f"Yield contribution · {UNIT.lower()}",
        range=[-ylim, ylim], zeroline=True, zerolinecolor="#AA7C21", zerolinewidth=2,
        gridcolor="#E5EAE4",
    )
    return fig


def show_summary(summary):
    metric_styles = "".join(
        f'.st-key-bp2_metrics [data-testid="stColumn"]:nth-child({index}) '
        f'[data-testid="stMetric"] {{border-top: 3px solid {color};}}'
        for index, (_, color) in enumerate(INDICATORS.values(), start=1)
    )
    st.html(f"<style>{metric_styles}</style>")
    with st.container(key="bp2_metrics"):
        for cell, (field, (label, _)) in zip(st.columns(4), INDICATORS.items()):
            explanation = (
                "Difference between reported production and area × yield at the end, "
                "minus that same difference at the start. This reconciles the three "
                "contributions to the NSO total; it is not a third production driver."
                if field == "residual_change_ton" else UNIT
            )
            cell.metric(label, signed_tonnes(summary[field]), border=True, help=explanation)


def show_period_breakdown(summary, start, end):
    before = summary["rice_production_ton_start"] / 1_000
    after = summary["rice_production_ton_end"] / 1_000
    st.markdown(
        f"Reported production went from **{before:,.2f}** in {start} to **{after:,.2f}** in {end} "
        f"thousand tonnes. **{signed_tonnes(summary[CHANGE])} thousand tonnes** is the difference."
    )
    with st.container(border=True):
        st.subheader("Production change breakdown")
        st.caption(
            "Read left to right. Green is the area contribution, gold is the yield contribution, "
            "clay is the reporting difference, and slate is the NSO total. "
            "Each floating bar starts where the previous contribution ended."
        )
        st.plotly_chart(waterfall(summary), key="bp2_waterfall", theme=None, config={"displayModeBar": False})
        st.info(
            f"Why is the reporting difference {signed_tonnes(summary['residual_change_ton'])}? "
            "NSO publishes production, sown area and yield separately, so reported production "
            "does not always equal area × yield exactly. The difference between those two figures "
            f"changed by {signed_tonnes(summary['residual_change_ton'])} thousand tonnes "
            f"from {start} to {end}. It closes the arithmetic: "
            f"{signed_tonnes(summary['area_effect_ton'])} "
            f"{signed_tonnes(summary['yield_effect_ton'])} "
            f"{signed_tonnes(summary['residual_change_ton'])} = "
            f"{signed_tonnes(summary[CHANGE])} thousand tonnes (before display rounding). "
            "It is a reporting adjustment, not a separate cause."
        )


def show_place_comparison(rows, place_type, start, end):
    with st.container(border=True):
        st.subheader(f"Compare {place_type.lower()}s")
        rank_by = st.selectbox(
            "Rank by magnitude", list(INDICATORS),
            format_func=lambda field: INDICATORS[field][0], key="bp2_rank_by",
        )
        ranked = rows.sort_values(rank_by, key=lambda values: values.abs(), ascending=False, kind="stable")
        largest = ranked.iloc[0]
        st.markdown(
            f"**{largest['place']}** has the largest change by magnitude for "
            f"**{INDICATORS[rank_by][0].lower()}** ({signed_tonnes(largest[rank_by])} thousand tonnes)."
        )
        st.caption("Each dot is one place. Left of zero means a decrease; right means an increase. The line shows distance from zero.")
        st.plotly_chart(
            place_dot_plot(ranked, rank_by),
            key="bp2_comparison", theme=None, config={"displayModeBar": False},
        )
    with st.expander("View ranked data table"):
        columns = {
            "rice_production_ton_start": f"Production in {start}",
            "rice_production_ton_end": f"Production in {end}",
            **{field: label for field, (label, _) in INDICATORS.items()},
        }
        table = ranked[list(columns)].div(1_000).rename(columns=columns)
        table.insert(0, place_type, ranked["place"])
        st.dataframe(
            table, hide_index=True,
            column_config={label: st.column_config.NumberColumn(format="%.2f") for label in columns.values()},
        )
        st.caption("All numeric columns are in thousand tonnes.")


def show_annual_history(place_history, place_type, start, end, context_start):
    if place_history.empty:
        st.info("Annual comparisons are unavailable for this scope.")
        return
    with st.container(border=True):
        st.subheader("Where and when did changes occur?")
        field = st.selectbox(
            "Map colors by", list(INDICATORS),
            format_func=lambda key: INDICATORS[key][0], key="bp2_heatmap_indicator",
        )
        largest = place_history.loc[place_history[field].abs().idxmax()]
        st.markdown(
            f"The strongest cell is **{largest['place']} in {int(largest['year_end'])}** "
            f"({signed_tonnes(largest[field])} thousand tonnes vs. the previous year)."
        )
        st.caption(
            f"Rows are {place_type.lower()}s; columns are years. Each cell compares that year with "
            f"the year immediately before it. Showing {context_start + 1}–{end}; "
            f"the selected {start}→{end} comparison remains in the cards above. "
            "Up to five earlier years provide context when the selected pair is short. "
            "Red means a decrease, pale means near zero, and teal means an increase."
        )
        st.plotly_chart(
            annual_heatmap(place_history, field), key="bp2_annual_heatmap", theme=None,
            config={"displayModeBar": False},
        )


def show_area_vs_yield(rows, place_type):
    fields = ("area_effect_ton", "yield_effect_ton")
    area, yield_effect = (rows[field] for field in fields)
    opposite = (area.gt(0) & yield_effect.lt(0)) | (area.lt(0) & yield_effect.gt(0))
    with st.container(border=True):
        st.subheader("Do area and yield reinforce or offset each other?")
        st.markdown(
            f"Area and yield contributions have opposite signs in **{int(opposite.sum())} of {len(rows)} {place_type.lower()}s**."
        )
        if opposite.any():
            example = rows.loc[opposite].sort_values(CHANGE, key=lambda values: values.abs(), ascending=False).iloc[0]
            st.caption(
                f"{example['place']} is one example. Sown area contributes {signed_tonnes(example[fields[0]])} "
                f"and yield contributes {signed_tonnes(example[fields[1]])} thousand tonnes."
            )
        st.caption(
            "Each point is one place. Right/left means area adds/reduces; up/down means yield adds/reduces. "
            "Opposite-sign quadrants show one contribution offsetting the other. "
            "Point color shows whether total reported production rose (teal) or fell (red)."
        )
        st.plotly_chart(driver_quadrants(rows), key="bp2_drivers", theme=None, config={"displayModeBar": False})
        st.caption("Only the largest movements and one offsetting example are labeled to keep the chart readable. Hover over any point for its place and exact values.")


def render():
    st.markdown('<div class="eyebrow">BP2 / DIAGNOSTIC ANALYTICS</div>', unsafe_allow_html=True)
    st.title("Explaining production changes")
    st.markdown("Compare how changes in sown area and yield contribute to the difference in reported rice production between two years.")
    try:
        signature = MART.stat()
        data = load_bp2_data(str(MART), signature.st_mtime_ns, signature.st_size)
    except (OSError, ValueError) as exc:
        st.warning("BP2 analytics could not be loaded. Rebuild the BP2 data from the repository root.")
        st.code("python -m src.bp2.bp2", language="powershell")
        with st.expander("Data details"):
            st.text(str(exc))
        return

    regions = sorted(
        data.loc[data["level"].eq("region"), "region"].dropna().unique(),
        key=lambda region: REGION_NAMES.get(region, region),
    )
    with st.container(border=True):
        geography, base_year, comparison_year = st.columns([2, 1, 1])
        scope = geography.selectbox(
            "Analysis scope", [NATIONAL, *regions],
            format_func=lambda region: REGION_NAMES.get(region, region), key="bp2_scope",
        )
        end_years = sorted(data["year_end"].unique(), reverse=True)
        end = comparison_year.selectbox("Comparison year", end_years, key="bp2_year_end")
        start_years = sorted(data.loc[data["year_end"].eq(end), "year_start"].unique(), reverse=True)
        start = base_year.selectbox("Base year", start_years, key="bp2_year_start")

    if scope == NATIONAL:
        summary_rows = data.loc[data["level"].eq("national")]
        place_rows = data.loc[data["level"].eq("region")].copy()
        place_rows["place"] = place_rows["region"].replace(REGION_NAMES)
        place_type = "Region"
    else:
        region = data.loc[data["region"].eq(scope)]
        summary_rows = region.loc[region["level"].eq("region")]
        place_rows = region.loc[region["level"].eq("province")].assign(place=lambda rows: rows["province_name"])
        place_type = "Province"

    summaries = summary_rows.loc[summary_rows["year_start"].eq(start) & summary_rows["year_end"].eq(end)]
    detail = place_rows.loc[place_rows["year_start"].eq(start) & place_rows["year_end"].eq(end)]
    if len(summaries) != 1 or detail.empty:
        st.warning("This selection is incomplete in the BP2 data. Rebuild it with `python -m src.bp2.bp2`.")
        return
    summary = summaries.iloc[0]
    st.caption(f"{REGION_NAMES.get(scope, scope)} · {start} → {end} · {summary['province_count']} historical provinces · {UNIT}")
    show_summary(summary)
    view = st.segmented_control(
        "Dashboard view", VIEWS, default=VIEWS[0], key="bp2_view",
        label_visibility="collapsed", width="stretch", required=True,
    )

    if view == "Overview":
        show_period_breakdown(summary, start, end)
    elif view == "Compare places":
        show_place_comparison(detail, place_type, start, end)
    elif view == "Year by year":
        first_year = int(data["year_start"].min())
        context_start = min(start, max(first_year, end - 6))
        annual = data["year_end"].sub(data["year_start"]).eq(1) & data["year_end"].between(context_start + 1, end)
        show_annual_history(
            place_rows.loc[annual], place_type, start, end, context_start,
        )
    else:
        show_area_vs_yield(detail, place_type)

    with st.expander("Colors, calculation and interpretation"):
        st.markdown(
            "- **Forest green · Sown area.** Change in area multiplied by average yield across the two years.\n"
            "- **Rice gold · Yield.** Change in yield multiplied by average sown area across the two years.\n"
            "- **Clay · Reporting difference.** The change in (reported production − area × yield) "
            "between the two years. It reconciles the arithmetic and is not an additional production driver. "
            "Published figures may differ because of rounding or reporting conventions; the dashboard "
            "does not identify the exact source of that difference.\n"
            "- **Slate · Reported change.** Difference between the two NSO production values. "
            "The three terms sum to this total. On the time map only, red/teal indicate negative/positive "
            "values rather than the measure type. On the quadrant plot, they indicate the direction "
            "of reported production change.\n\n"
            "BP2 calculates each component by province before summing across the seven project regions "
            "and the country. It compares the selected endpoints, including when years are several years apart. "
            "The calculation quantifies arithmetic contributions. Establishing causes requires separate evidence. "
            "Reported production indicates potential supply.\n\n"
            "Source tables V06.13, V06.14 and V06.15 from the National Statistics Office of Vietnam."
        )


render()
