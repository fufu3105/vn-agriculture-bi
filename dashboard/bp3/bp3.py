"""BP3 Dashboard: Provincial Rice Production Forecasting and Sourcing Scenarios."""

from pathlib import Path
from html import escape
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


ROOT = Path(__file__).resolve().parents[2]
ANALYTICS = ROOT / "data/analytics/bp3"
PROCESSED_AGRI = ROOT / "data/processed/agriculture/rice_province_year/rice_province_year.parquet"
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

REGION_COLORS = {
    "Mekong Delta": "#356859",
    "Red River Delta": "#B29252",
    "North Central Coast": "#6F8391",
    "Northern Midlands & Mountains": "#8D7069",
    "South Central Coast": "#7B8660",
    "Central Highlands": "#9A8D72",
    "Southeast": "#A3B4AC",
}

MODEL_NAMES = {
    "naive": "Naive Baseline (Lag-1)",
    "sma3": "3-Year Moving Avg (SMA-3)",
    "holt": "Damped Holt's Linear",
    "trend": "Linear Trend (5-Year)",
    "component": "Component (Area × Yield)",
}

VIEWS = (
    "Outlook & Forecast",
    "Model Accuracy & Backtest",
    "Sourcing Scenarios",
    "Province Deep Dive",
)


@st.cache_data(show_spinner=False)
def load_bp3_data(analytics_dir_str, signatures):
    """Load the 4 BP3 analytical Parquet tables and processed panel."""
    folder = Path(analytics_dir_str)
    forecast_df = pd.read_parquet(folder / "forecast_next_year.parquet")
    backtest_df = pd.read_parquet(folder / "historical_backtest.parquet")
    performance_df = pd.read_parquet(folder / "model_performance.parquet")
    scenarios_df = pd.read_parquet(folder / "sourcing_scenarios.parquet")
    history_df = pd.read_parquet(PROCESSED_AGRI)

    # Translate region names in memory for presentation
    for df in [forecast_df, backtest_df, performance_df, scenarios_df, history_df]:
        if "region" in df.columns:
            df["region_en"] = df["region"].map(lambda r: REGION_NAMES.get(r, r))

    return forecast_df, backtest_df, performance_df, scenarios_df, history_df


def style_chart(fig, height=360, show_legend=True):
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=10, r=16, t=38, b=16),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Segoe UI, sans-serif", size=12, color="#365345"),
        hoverlabel=dict(bgcolor="#FFFFFF", font_color="#203D32"),
        showlegend=show_legend,
        legend=dict(orientation="h", y=1.03, x=0, yanchor="bottom"),
    )
    fig.update_xaxes(gridcolor="#E9EDE5", zerolinecolor="#84998B")
    fig.update_yaxes(gridcolor="#E9EDE5", zerolinecolor="#84998B")
    return fig


def format_tonnes(tonnes, unit="m"):
    if unit == "m":
        return f"{tonnes / 1e6:,.2f} M tonnes"
    return f"{tonnes / 1e3:,.1f} k tonnes"


def signed_tonnes(tonnes, unit="m"):
    if unit == "m":
        return f"{tonnes / 1e6:+,.2f} M tonnes"
    return f"{tonnes / 1e3:+,.1f} k tonnes"


def show_forecast_outlook(forecast_df, scope):
    """Tab 1: 2025 Production Forecast Outlook."""
    if scope == NATIONAL:
        summary_row = forecast_df[forecast_df["level"] == "national"].iloc[0]
        region_rows = forecast_df[forecast_df["level"] == "region"].copy()
        prov_rows = forecast_df[forecast_df["level"] == "province"].copy()
    else:
        summary_row = forecast_df[(forecast_df["level"] == "region") & (forecast_df["region_en"] == scope)].iloc[0]
        region_rows = pd.DataFrame()
        prov_rows = forecast_df[(forecast_df["level"] == "province") & (forecast_df["region_en"] == scope)].copy()

    prev_prod = summary_row["production_actual_prev_ton"]
    base_prod = summary_row["forecast_base_ton"]
    opt_prod = summary_row["forecast_optimistic_ton"]
    pess_prod = summary_row["forecast_pessimistic_ton"]
    chg_ton = summary_row["forecast_change_ton"]
    chg_pct = summary_row["forecast_change_pct"]

    # Top Metric Cards
    cols = st.columns(4)
    cols[0].metric(
        "2025 OUTLOOK (BASE)",
        f"{base_prod / 1e6:.2f}M tonnes",
        delta=f"{chg_pct:+.2f}% vs 2024",
        help="One-year-ahead expected production using optimal model per province.",
        border=True,
    )
    cols[1].metric(
        "2024 ACTUAL LEVEL",
        f"{prev_prod / 1e6:.2f}M tonnes",
        help="National Statistics Office reported production for 2024.",
        border=True,
    )
    cols[2].metric(
        "PESSIMISTIC (LOW SUPPLY)",
        f"{pess_prod / 1e6:.2f}M tonnes",
        delta=f"{(pess_prod - base_prod) / 1e6:.2f}M buffer gap",
        delta_color="inverse",
        help="Conservative lower planning boundary (-1 historical MAE).",
        border=True,
    )
    cols[3].metric(
        "OPTIMISTIC (HIGH SUPPLY)",
        f"{opt_prod / 1e6:.2f}M tonnes",
        delta=f"+{(opt_prod - base_prod) / 1e6:.2f}M upside",
        help="High-supply upside scenario (+1 historical MAE).",
        border=True,
    )

    st.markdown(
        f'<div class="insight"><span>2025 OUTLOOK SUMMARY</span><br>'
        f"For <b>{scope}</b>, expected rice production in 2025 is <b>{base_prod / 1e6:.2f} million tonnes</b>, "
        f"representing a change of <b>{signed_tonnes(chg_ton, 'm')} ({chg_pct:+.2f}%)</b> from 2024. "
        f"Under conservative downside conditions, production could decrease to <b>{pess_prod / 1e6:.2f} million tonnes</b>, "
        f"requiring a supply risk reserve of <b>{(base_prod - pess_prod) / 1e3:,.1f} thousand tonnes</b>.</div>",
        unsafe_allow_html=True,
    )

    col_left, col_right = st.columns(2)

    with col_left, st.container(border=True):
        if scope == NATIONAL and not region_rows.empty:
            st.subheader("Regional Supply Distribution (2025 Forecast)")
            st.caption("Share of expected national rice production across 7 regions.")
            fig_pie = go.Figure(go.Pie(
                labels=region_rows["region_en"],
                values=region_rows["forecast_base_ton"] / 1e6,
                hole=0.6,
                marker=dict(
                    colors=[REGION_COLORS.get(r, "#888888") for r in region_rows["region_en"]],
                    line=dict(color="#FFFFFF", width=2),
                ),
                textinfo="percent+label",
                textposition="outside",
                hovertemplate="%{label}<br>%{value:.2f} million tonnes · %{percent}<extra></extra>",
            ))
            fig_pie.add_annotation(
                text=f"<b>{base_prod / 1e6:.2f}M</b><br>tonnes",
                x=0.5, y=0.5, font_size=20, showarrow=False, font_color="#173F32",
            )
            style_chart(fig_pie, height=380, show_legend=False)
            st.plotly_chart(fig_pie, key="bp3_pie", theme=None, config={"displayModeBar": False})
        else:
            st.subheader("Provinces in Selected Region")
            st.caption(f"Expected production in 2025 across provinces in {scope}.")
            top_prov = prov_rows.sort_values("forecast_base_ton", ascending=True)
            fig_reg_bars = px.bar(
                top_prov,
                x=top_prov["forecast_base_ton"] / 1e3,
                y="province_name",
                orientation="h",
                labels={"x": "Thousand tonnes", "province_name": ""},
                color_discrete_sequence=["#356859"],
            )
            fig_reg_bars.update_traces(
                hovertemplate="%{y}<br>Forecast: %{x:,.1f} k tonnes<extra></extra>"
            )
            style_chart(fig_reg_bars, height=max(360, len(top_prov) * 28 + 60), show_legend=False)
            st.plotly_chart(fig_reg_bars, key="bp3_reg_bars", theme=None, config={"displayModeBar": False})

    with col_right, st.container(border=True):
        st.subheader("Top Producing Provinces (2025 Forecast)")
        st.caption("Largest anticipated volume suppliers in 2025 and comparison vs 2024 actual.")
        top_provinces = prov_rows.nlargest(10, "forecast_base_ton").sort_values("forecast_base_ton", ascending=True)

        fig_top = go.Figure()
        fig_top.add_trace(go.Bar(
            y=top_provinces["province_name"],
            x=top_provinces["production_actual_prev_ton"] / 1e3,
            name="2024 Actual",
            orientation="h",
            marker_color="#9FAFA5",
            hovertemplate="%{y}<br>2024 Actual: %{x:,.1f} k tonnes<extra></extra>",
        ))
        fig_top.add_trace(go.Bar(
            y=top_provinces["province_name"],
            x=top_provinces["forecast_base_ton"] / 1e3,
            name="2025 Forecast",
            orientation="h",
            marker_color="#287650",
            hovertemplate="%{y}<br>2025 Forecast: %{x:,.1f} k tonnes<extra></extra>",
        ))
        style_chart(fig_top, height=380, show_legend=True)
        fig_top.update_layout(barmode="group", xaxis_title="Thousand tonnes")
        st.plotly_chart(fig_top, key="bp3_top_provinces", theme=None, config={"displayModeBar": False})

    # Data Table View
    with st.expander("View 2025 Sourcing Outlook Table"):
        display_cols = [
            "province_name", "region_en", "production_actual_prev_ton",
            "forecast_base_ton", "forecast_optimistic_ton", "forecast_pessimistic_ton",
            "forecast_change_ton", "forecast_change_pct", "risk_tier", "best_model_name",
        ]
        table_df = prov_rows[display_cols].copy()
        table_df.columns = [
            "Province", "Region", "2024 Actual (t)", "2025 Forecast (t)",
            "Optimistic (t)", "Pessimistic (t)", "Change (t)", "Change (%)",
            "Sourcing Tier", "Selected Model",
        ]
        st.dataframe(
            table_df.sort_values("2025 Forecast (t)", ascending=False),
            hide_index=True,
            column_config={
                "2024 Actual (t)": st.column_config.NumberColumn(format="%d"),
                "2025 Forecast (t)": st.column_config.NumberColumn(format="%d"),
                "Optimistic (t)": st.column_config.NumberColumn(format="%d"),
                "Pessimistic (t)": st.column_config.NumberColumn(format="%d"),
                "Change (t)": st.column_config.NumberColumn(format="%+d"),
                "Change (%)": st.column_config.NumberColumn(format="%+.2f%%"),
            },
        )


def show_model_accuracy(backtest_df, performance_df, scope):
    """Tab 2: Historical Walk-Forward Backtesting & Model Accuracy."""
    st.subheader("Walk-Forward Cross-Validation Performance (2017–2024)")
    st.caption(
        "Each test year was predicted strictly using prior years' data (expanding window). "
        "No future or concurrent data was leaked into model training."
    )

    if scope == NATIONAL:
        perf_subset = performance_df[performance_df["level"] == "national"].copy()
    else:
        perf_subset = performance_df[(performance_df["level"] == "region") & (performance_df["region_en"] == scope)].copy()

    # Scorecard Comparison Table
    scorecard = perf_subset.copy()
    scorecard["Model Display"] = scorecard["model"].map(MODEL_NAMES)
    scorecard["MAE (Tonnes)"] = scorecard["mae_ton"]
    scorecard["RMSE (Tonnes)"] = scorecard["rmse_ton"]
    scorecard["MAPE (%)"] = scorecard["mape_pct"]
    scorecard["Bias (Tonnes)"] = scorecard["bias_ton"]

    # Baseline comparison (vs Naive)
    naive_mae = scorecard.loc[scorecard["model"] == "naive", "mae_ton"].values
    ref_mae = naive_mae[0] if len(naive_mae) > 0 else 1.0
    scorecard["MAE vs Baseline"] = ((scorecard["mae_ton"] / ref_mae) - 1.0) * 100.0

    col_metric, col_table = st.columns([1, 2])
    with col_metric:
        best_row = scorecard.sort_values("mae_ton").iloc[0]
        st.metric(
            "BEST OVERALL MODEL",
            str(best_row["Model Display"]),
            delta=f"{best_row['MAE vs Baseline']:+.1f}% MAE vs Naive",
            delta_color="inverse",
            help="Model with lowest mean absolute error in chronological backtests.",
            border=True,
        )
        st.metric(
            "AGGREGATE ACCURACY (MAPE)",
            f"{best_row['MAPE (%)']:.2f}%",
            help="Mean Absolute Percentage Error at this aggregation level.",
            border=True,
        )
        st.metric(
            "MEAN ABSOLUTE ERROR",
            f"{best_row['MAE (Tonnes)'] / 1e3:,.1f} k tonnes",
            help="Average error magnitude per year.",
            border=True,
        )

    with col_table, st.container(border=True):
        st.markdown("**Model Accuracy Scorecard**")
        st.dataframe(
            scorecard[["Model Display", "MAPE (%)", "MAE (Tonnes)", "RMSE (Tonnes)", "MAE vs Baseline"]].sort_values("MAPE (%)"),
            hide_index=True,
            column_config={
                "MAPE (%)": st.column_config.NumberColumn(format="%.2f%%"),
                "MAE (Tonnes)": st.column_config.NumberColumn(format="%,.0f"),
                "RMSE (Tonnes)": st.column_config.NumberColumn(format="%,.0f"),
                "MAE vs Baseline": st.column_config.NumberColumn(format="%+.1f%%"),
            },
        )

    # Timeline Chart of Backtest Forecast Errors
    with st.container(border=True):
        st.subheader("Historical Forecast Error Progression (2017–2024)")
        st.caption("Comparing actual production against model predictions across each backtest year.")

        if scope == NATIONAL:
            yearly_eval = backtest_df.groupby(["test_year", "model"]).agg(
                actual=("actual_production_ton", "sum"),
                predicted=("predicted_production_ton", "sum"),
            ).reset_index()
        else:
            yearly_eval = backtest_df[backtest_df["region_en"] == scope].groupby(["test_year", "model"]).agg(
                actual=("actual_production_ton", "sum"),
                predicted=("predicted_production_ton", "sum"),
            ).reset_index()

        fig_timeline = go.Figure()
        # Add actual line once
        actual_line = yearly_eval[yearly_eval["model"] == "naive"].sort_values("test_year")
        fig_timeline.add_trace(go.Scatter(
            x=actual_line["test_year"],
            y=actual_line["actual"] / 1e6,
            mode="lines+markers",
            name="Actual NSO Production",
            line=dict(color="#173F32", width=3.5),
            marker=dict(size=8),
            hovertemplate="%{x} Actual: %{y:.2f}M tonnes<extra></extra>",
        ))

        model_palette = {
            "naive": "#708090",
            "sma3": "#B29252",
            "holt": "#287650",
            "trend": "#AC5A38",
            "component": "#4A6FA5",
        }
        for m_key in ["naive", "sma3", "holt", "component"]:
            m_sub = yearly_eval[yearly_eval["model"] == m_key].sort_values("test_year")
            fig_timeline.add_trace(go.Scatter(
                x=m_sub["test_year"],
                y=m_sub["predicted"] / 1e6,
                mode="lines",
                name=MODEL_NAMES.get(m_key, m_key),
                line=dict(color=model_palette.get(m_key, "#888"), width=2, dash="dash" if m_key == "naive" else "solid"),
                hovertemplate=f"%{{x}} {MODEL_NAMES.get(m_key, m_key)}: %{{y:.2f}}M tonnes<extra></extra>",
            ))

        style_chart(fig_timeline, height=380, show_legend=True)
        fig_timeline.update_layout(yaxis_title="Million tonnes", xaxis=dict(dtick=1))
        st.plotly_chart(fig_timeline, key="bp3_timeline", theme=None, config={"displayModeBar": False})

    # Provincial Error Distribution Dot Plot
    with st.container(border=True):
        st.subheader("Provincial Forecast Reliability (MAPE Distribution)")
        st.caption("Mean Absolute Percentage Error by province in 2017–2024 backtests. Lower indicates higher forecasting accuracy.")
        prov_perf = performance_df[performance_df["level"] == "province"].copy()
        if scope != NATIONAL:
            prov_perf = prov_perf[prov_perf["region_en"] == scope]

        best_per_prov = prov_perf[prov_perf["is_best_model"]].sort_values("mape_pct", ascending=True)

        fig_dot = go.Figure()
        fig_dot.add_trace(go.Scatter(
            x=best_per_prov["mape_pct"],
            y=best_per_prov["province_name"],
            mode="markers",
            marker=dict(color="#287650", size=10, line=dict(color="#FFFFFF", width=1)),
            text=best_per_prov["model"].map(MODEL_NAMES),
            hovertemplate="<b>%{y}</b><br>Backtest MAPE: %{x:.2f}%<br>Optimal Model: %{text}<extra></extra>",
        ))
        fig_dot.add_vline(x=5.0, line_dash="dash", line_color="#84998B", annotation_text="5% Benchmark", annotation_position="top right")
        style_chart(fig_dot, height=max(380, len(best_per_prov) * 20 + 80), show_legend=False)
        fig_dot.update_layout(xaxis_title="Backtest MAPE (%)", yaxis=dict(automargin=True))
        st.plotly_chart(fig_dot, key="bp3_dot", theme=None, config={"displayModeBar": False})


def show_sourcing_scenarios(forecast_df, scenarios_df, scope):
    """Tab 3: Sourcing Scenarios & Buffer Planning."""
    st.subheader("Procurement Scenarios & Supply Buffer Allocation")
    st.caption(
        "Prepare contingency supply plans based on empirical forecast error bounds. "
        "Conservative buffers protect against regional crop deficits."
    )

    slider_col, info_col = st.columns([1, 2])
    with slider_col, st.container(border=True):
        buffer_multiplier = st.slider(
            "Scenario Safety Multiplier",
            min_value=0.5,
            max_value=2.0,
            value=1.0,
            step=0.25,
            key="bp3_buffer_mult",
            help="Multiplier applied to historical MAE to adjust scenario bounds.",
        )
        st.caption(f"Currently scaling error margin by **{buffer_multiplier:.2f}×** historical MAE.")

    with info_col, st.container(border=True):
        st.markdown(
            "**Sourcing Risk Principle:** "
            "Downside risk in agricultural supply stems from climatic anomalies, pest outbreaks, and planting decisions. "
            "The **Pessimistic Scenario** represents the conservative expected supply level under adverse conditions. "
            "Procurement managers should maintain secondary supplier agreements equal to the **Downside Gap**."
        )

    # Regional Scenario Comparison Chart
    with st.container(border=True):
        st.subheader("Regional Scenario Funnel (Base vs Pessimistic vs Optimistic)")
        st.caption("Volume range (million tonnes) anticipated across regions in 2025.")

        reg_data = scenarios_df.copy()
        reg_data["pessimistic_m"] = (reg_data["forecast_base_ton"] - reg_data["downside_gap_ton"] * buffer_multiplier) / 1e6
        reg_data["base_m"] = reg_data["forecast_base_ton"] / 1e6
        reg_data["optimistic_m"] = (reg_data["forecast_base_ton"] + reg_data["downside_gap_ton"] * buffer_multiplier) / 1e6

        fig_scen = go.Figure()
        fig_scen.add_trace(go.Bar(
            name="Pessimistic (Lower Bound)",
            x=reg_data["region_en"],
            y=reg_data["pessimistic_m"],
            marker_color="#B44E42",
            hovertemplate="%{x}<br>Pessimistic: %{y:.2f}M tonnes<extra></extra>",
        ))
        fig_scen.add_trace(go.Bar(
            name="Expected Base Outlook",
            x=reg_data["region_en"],
            y=reg_data["base_m"],
            marker_color="#287650",
            hovertemplate="%{x}<br>Base Outlook: %{y:.2f}M tonnes<extra></extra>",
        ))
        fig_scen.add_trace(go.Bar(
            name="Optimistic (Upper Bound)",
            x=reg_data["region_en"],
            y=reg_data["optimistic_m"],
            marker_color="#19765C",
            hovertemplate="%{x}<br>Optimistic: %{y:.2f}M tonnes<extra></extra>",
        ))
        style_chart(fig_scen, height=400, show_legend=True)
        fig_scen.update_layout(barmode="group", yaxis_title="Million tonnes")
        st.plotly_chart(fig_scen, key="bp3_scen", theme=None, config={"displayModeBar": False})

    # Regional Sourcing Allocation Table
    with st.container(border=True):
        st.subheader("Sourcing Strategy by Regional Basket")
        disp_scen = reg_data[[
            "region_en", "sourcing_priority", "base_m", "pessimistic_m",
            "recommended_buffer_pct", "recommendation"
        ]].copy()
        disp_scen.columns = [
            "Region", "Procurement Priority", "Expected Base (M tonnes)",
            "Pessimistic Reserve (M tonnes)", "Buffer Margin (%)", "Strategic Action"
        ]
        st.dataframe(
            disp_scen,
            hide_index=True,
            column_config={
                "Expected Base (M tonnes)": st.column_config.NumberColumn(format="%.2f M"),
                "Pessimistic Reserve (M tonnes)": st.column_config.NumberColumn(format="%.2f M"),
                "Buffer Margin (%)": st.column_config.NumberColumn(format="%.1f%%"),
            },
        )


def show_province_deep_dive(forecast_df, history_df, performance_df, backtest_df):
    """Tab 4: Single-Province Trajectory & 2025 Forecast Funnel."""
    st.subheader("Province Historical Trajectory & 2025 Forecast Funnel")

    provinces = sorted(forecast_df[forecast_df["level"] == "province"]["province_name"].unique())
    selected_province = st.selectbox("Select Province for Deep-Dive Analysis", provinces, key="bp3_deep_prov")

    prov_forecast = forecast_df[forecast_df["province_name"] == selected_province].iloc[0]
    prov_hist = history_df[history_df["province_name"] == selected_province].sort_values("year")
    prov_backtest = backtest_df[backtest_df["province_name"] == selected_province]
    prov_perf = performance_df[(performance_df["province_name"] == selected_province) & (performance_df["is_best_model"])].iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("2025 POINT FORECAST", f"{prov_forecast['forecast_base_ton'] / 1e3:,.1f}k tonnes", border=True)
    c2.metric("EXPECTED CHANGE", f"{prov_forecast['forecast_change_pct']:+.2f}% vs 2024", border=True)
    c3.metric("HISTORICAL BACKTEST MAPE", f"{prov_perf['mape_pct']:.2f}%", border=True)
    c4.metric("OPTIMAL MODEL", MODEL_NAMES.get(prov_forecast["best_model_name"], prov_forecast["best_model_name"]), border=True)

    with st.container(border=True):
        st.subheader(f"Rice Production Trajectory: {selected_province} (2010–2025)")
        st.caption("Historical reported data (2010–2024) with 2025 forecast cone and backtest predictions.")

        fig_traj = go.Figure()

        # Historical Actuals
        fig_traj.add_trace(go.Scatter(
            x=prov_hist["year"],
            y=prov_hist["rice_production_ton"] / 1e3,
            mode="lines+markers",
            name="Actual Production",
            line=dict(color="#173F32", width=3),
            marker=dict(size=7),
            hovertemplate="%{x}: %{y:,.1f} k tonnes<extra></extra>",
        ))

        # 2025 Forecast Cone (Connecting 2024 to 2025)
        x_cone = [2024, 2025, 2025, 2024]
        y_cone = [
            prov_hist.iloc[-1]["rice_production_ton"] / 1e3,
            prov_forecast["forecast_optimistic_ton"] / 1e3,
            prov_forecast["forecast_pessimistic_ton"] / 1e3,
            prov_hist.iloc[-1]["rice_production_ton"] / 1e3,
        ]
        fig_traj.add_trace(go.Scatter(
            x=x_cone, y=y_cone,
            fill="toself",
            fillcolor="rgba(40, 118, 80, 0.15)",
            line=dict(color="rgba(255,255,255,0)"),
            hoverinfo="skip",
            name="2025 Scenario Interval",
        ))

        # 2025 Forecast Point
        fig_traj.add_trace(go.Scatter(
            x=[2024, 2025],
            y=[prov_hist.iloc[-1]["rice_production_ton"] / 1e3, prov_forecast["forecast_base_ton"] / 1e3],
            mode="lines+markers",
            name="2025 Point Forecast",
            line=dict(color="#287650", width=2.5, dash="dash"),
            marker=dict(size=8, symbol="diamond", color="#AA7C21"),
            hovertemplate="%{x} Forecast: %{y:,.1f} k tonnes<extra></extra>",
        ))

        style_chart(fig_traj, height=420, show_legend=True)
        fig_traj.update_layout(yaxis_title="Thousand tonnes", xaxis=dict(dtick=1))
        st.plotly_chart(fig_traj, key="bp3_traj", theme=None, config={"displayModeBar": False})

    # Drivers: Sown Area and Yield Trends
    col_a, col_y = st.columns(2)
    with col_a, st.container(border=True):
        st.subheader("Cultivated Area Trend (ha)")
        fig_area = px.line(
            prov_hist, x="year", y=prov_hist["rice_area_ha"] / 1e3,
            markers=True, labels={"y": "Thousand ha", "year": ""},
            color_discrete_sequence=["#287650"]
        )
        style_chart(fig_area, height=280, show_legend=False)
        st.plotly_chart(fig_area, key="bp3_area", theme=None, config={"displayModeBar": False})

    with col_y, st.container(border=True):
        st.subheader("Yield Trend (tonnes/ha)")
        fig_yield = px.line(
            prov_hist, x="year", y="rice_yield_ton_ha",
            markers=True, labels={"rice_yield_ton_ha": "Tonnes/ha", "year": ""},
            color_discrete_sequence=["#AA7C21"]
        )
        style_chart(fig_yield, height=280, show_legend=False)
        st.plotly_chart(fig_yield, key="bp3_yield", theme=None, config={"displayModeBar": False})


def render():
    st.markdown('<div class="eyebrow">BP3 / PREDICTIVE ANALYTICS</div>', unsafe_allow_html=True)
    st.title("Rice production forecasting & sourcing outlook")
    st.markdown("Estimate next year’s provincial production and evaluate backtest accuracy to prepare risk-adjusted supply sourcing scenarios.")

    try:
        paths = [
            ANALYTICS / "forecast_next_year.parquet",
            ANALYTICS / "historical_backtest.parquet",
            ANALYTICS / "model_performance.parquet",
            ANALYTICS / "sourcing_scenarios.parquet",
        ]
        signatures = tuple((p.stat().st_mtime_ns, p.stat().st_size) for p in paths)
        forecast_df, backtest_df, performance_df, scenarios_df, history_df = load_bp3_data(
            str(ANALYTICS), signatures
        )
    except (OSError, ValueError, KeyError) as exc:
        st.warning("BP3 analytics marts could not be loaded. Please build the BP3 data from repository root.")
        st.code("python -m src.bp3.bp3", language="powershell")
        with st.expander("Diagnostic details"):
            st.text(str(exc))
        return

    # Scope Selection (National vs Region)
    regions = sorted(
        forecast_df[forecast_df["level"] == "region"]["region_en"].unique(),
        key=lambda r: list(REGION_NAMES.values()).index(r) if r in REGION_NAMES.values() else 99,
    )
    with st.container(border=True):
        scope = st.selectbox(
            "Geographic Analysis Scope",
            [NATIONAL, *regions],
            key="bp3_scope",
        )

    view = st.segmented_control(
        "Dashboard View",
        VIEWS,
        default=VIEWS[0],
        key="bp3_view",
        label_visibility="collapsed",
        width="stretch",
    )

    if view == "Outlook & Forecast":
        show_forecast_outlook(forecast_df, scope)
    elif view == "Model Accuracy & Backtest":
        show_model_accuracy(backtest_df, performance_df, scope)
    elif view == "Sourcing Scenarios":
        show_sourcing_scenarios(forecast_df, scenarios_df, scope)
    else:
        show_province_deep_dive(forecast_df, history_df, performance_df, backtest_df)

    with st.expander("Methodology, Models & Procurement Interpretation"):
        st.markdown(
            "- **Walk-forward Backtesting (2017–2024):** Models are evaluated across 8 sequential test years. "
            "For each year T, training data is strictly limited to prior years (≤ T-1), preventing lookahead bias.\n"
            "- **Candidate Models:**\n"
            "  1. *Naive Baseline (Lag-1):* Direct persistence ($y_{T-1}$).\n"
            "  2. *3-Year Moving Average (SMA-3):* Rolling 3-year mean.\n"
            r"  3. *Damped Holt's Linear:* Level and trend exponential smoothing with damped extrapolation ($\phi = 0.85$).\n"
            "  4. *Component Model (Area × Yield):* Forecasts sown area and yield separately before multiplying.\n"
            "  5. *Linear Trend:* 5-year OLS linear extrapolation.\n"
            "- **Sourcing Scenarios:** Derived from empirical provincial forecast errors (MAE). "
            "The Pessimistic scenario represents conservative availability for supply chain buffer sizing.\n"
            "- **Data Foundation:** Historical provincial panel 2010–2024 (NSO tables V06.13, V06.14, V06.15) for 63 provinces."
        )


render()
