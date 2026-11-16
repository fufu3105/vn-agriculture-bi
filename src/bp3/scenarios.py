"""BP3 Sourcing Scenarios & 2025 Out-of-sample Forecast Generation.

Generates next-year (2025) production outlook using data available at cutoff (2024).
Builds sourcing scenarios (Base, Optimistic, Pessimistic) grounded in empirical
historical forecast error distributions for supply chain contingency planning.
"""

from typing import Dict, Tuple
import numpy as np
import pandas as pd

from src.bp3.models import ComponentModel, get_available_models


def generate_forecast_next_year(
    panel: pd.DataFrame,
    performance_df: pd.DataFrame,
    forecast_year: int = 2025,
    cutoff_year: int = 2024,
    error_multiplier: float = 1.0,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Generates 2025 provincial forecasts and sourcing scenarios.

    Returns:
    - forecast_table: Hierarchical table (province, region, national) with base,
      optimistic, and pessimistic scenario bounds.
    - sourcing_scenarios: Region-level procurement summary with buffer recommendations.
    """
    models = get_available_models()
    cutoff_data = panel[panel["year"] <= cutoff_year].copy()
    prev_actuals = panel[panel["year"] == cutoff_year].set_index("province_id")

    # Map each province to its best model and historical MAE from backtest
    prov_perf = performance_df[performance_df["level"] == "province"]
    best_models = (
        prov_perf[prov_perf["is_best_model"]]
        .set_index("province_id")[["model", "mae_ton", "mape_pct"]]
        .to_dict("index")
    )

    prov_records = []
    for pid, history in cutoff_data.groupby("province_id"):
        hist_sorted = history.sort_values("year")
        prov_info = hist_sorted.iloc[-1]
        pname = str(prov_info["province_name"])
        region = str(prov_info["region"])

        # Actual production in cutoff year
        prev_actual = float(prev_actuals.loc[pid, "rice_production_ton"])

        # Determine best model and its error bounds
        best_info = best_models.get(pid, {"model": "naive", "mae_ton": 0.05 * prev_actual, "mape_pct": 5.0})
        best_model_key = best_info["model"]
        mae_ton = float(best_info["mae_ton"])
        mape_pct = float(best_info["mape_pct"])

        # Run all models to store candidate predictions
        model_preds = {}
        for m_key, model in models.items():
            if isinstance(model, ComponentModel):
                pred = model.predict_province(hist_sorted, horizon=1)
            else:
                y_vals = hist_sorted["rice_production_ton"].to_numpy(dtype=float)
                pred = model.predict_series(y_vals, horizon=1)
            model_preds[f"pred_{m_key}_ton"] = float(pred)

        base_forecast = model_preds[f"pred_{best_model_key}_ton"]
        scenario_buffer = mae_ton * error_multiplier
        optimistic = base_forecast + scenario_buffer
        pessimistic = max(0.0, base_forecast - scenario_buffer)
        change_ton = base_forecast - prev_actual
        change_pct = (change_ton / prev_actual * 100.0) if prev_actual > 0 else 0.0

        # Classify supply reliability tier
        if base_forecast >= 500_000:
            if mape_pct <= 6.0:
                risk_tier = "Core Stable Supplier"
            else:
                risk_tier = "High-Volume Volatile"
        elif base_forecast >= 100_000:
            risk_tier = "Moderate Supply"
        else:
            risk_tier = "Minor / Local"

        prov_records.append({
            "level": "province",
            "year": int(forecast_year),
            "cutoff_year": int(cutoff_year),
            "province_id": int(pid),
            "province_name": pname,
            "region": region,
            "production_actual_prev_ton": prev_actual,
            "forecast_base_ton": base_forecast,
            "forecast_optimistic_ton": optimistic,
            "forecast_pessimistic_ton": pessimistic,
            "forecast_change_ton": change_ton,
            "forecast_change_pct": change_pct,
            "historical_mae_ton": mae_ton,
            "historical_mape_pct": mape_pct,
            "best_model_name": best_model_key,
            "risk_tier": risk_tier,
            **model_preds,
        })

    prov_df = pd.DataFrame(prov_records)

    # Aggregate to Regional level
    numeric_sums = [
        "production_actual_prev_ton", "forecast_base_ton",
        "forecast_optimistic_ton", "forecast_pessimistic_ton",
        "forecast_change_ton", "historical_mae_ton",
        *(f"pred_{m}_ton" for m in models),
    ]
    reg_df = prov_df.groupby("region", as_index=False)[numeric_sums].sum()
    reg_df["level"] = "region"
    reg_df["year"] = int(forecast_year)
    reg_df["cutoff_year"] = int(cutoff_year)
    reg_df["province_id"] = pd.NA
    reg_df["province_name"] = pd.NA
    reg_df["forecast_change_pct"] = (reg_df["forecast_change_ton"] / reg_df["production_actual_prev_ton"]) * 100.0
    reg_df["historical_mape_pct"] = (reg_df["historical_mae_ton"] / reg_df["forecast_base_ton"]) * 100.0
    reg_df["best_model_name"] = "hierarchical_sum"
    reg_df["risk_tier"] = "Regional Pool"

    # Aggregate to National level
    nat_dict = {col: prov_df[col].sum() for col in numeric_sums}
    nat_dict.update({
        "level": "national",
        "year": int(forecast_year),
        "cutoff_year": int(cutoff_year),
        "province_id": pd.NA,
        "province_name": pd.NA,
        "region": "Vietnam",
        "forecast_change_pct": (nat_dict["forecast_change_ton"] / nat_dict["production_actual_prev_ton"]) * 100.0,
        "historical_mape_pct": (nat_dict["historical_mae_ton"] / nat_dict["forecast_base_ton"]) * 100.0,
        "best_model_name": "hierarchical_sum",
        "risk_tier": "National Total",
    })
    nat_df = pd.DataFrame([nat_dict])

    combined_forecast = pd.concat([prov_df, reg_df, nat_df], ignore_index=True)
    combined_forecast["province_id"] = combined_forecast["province_id"].astype("Int32")

    # Build sourcing_scenarios table for procurement planning
    sourcing_records = []
    for region_name, grp in prov_df.groupby("region"):
        total_prev = grp["production_actual_prev_ton"].sum()
        total_base = grp["forecast_base_ton"].sum()
        total_pess = grp["forecast_pessimistic_ton"].sum()
        total_opt = grp["forecast_optimistic_ton"].sum()
        downside_gap = total_base - total_pess
        buffer_pct = (downside_gap / total_base) * 100.0 if total_base > 0 else 0.0

        if total_base >= 10_000_000:
            priority = "Priority 1 (Primary Supply Hub)"
            rec = "Core sourcing basket; maintain forward multi-month contracts with primary mills."
        elif total_base >= 4_000_000:
            priority = "Priority 2 (Secondary Sourcing Hub)"
            rec = "Strategic secondary volume; establish flexible supplier agreements."
        elif total_base >= 1_000_000:
            priority = "Priority 3 (Supplementary Regional Supply)"
            rec = "Opportunistic local sourcing; adjust purchases based on spot harvest prices."
        else:
            priority = "Priority 4 (Deficit / Local Area)"
            rec = "Limited procurement viability; prioritize local processing only."

        sourcing_records.append({
            "region": region_name,
            "province_count": len(grp),
            "production_actual_prev_ton": total_prev,
            "forecast_base_ton": total_base,
            "scenario_pessimistic_ton": total_pess,
            "scenario_optimistic_ton": total_opt,
            "downside_gap_ton": downside_gap,
            "recommended_buffer_pct": buffer_pct,
            "sourcing_priority": priority,
            "recommendation": rec,
        })

    sourcing_scenarios = pd.DataFrame(sourcing_records).sort_values(
        "forecast_base_ton", ascending=False
    ).reset_index(drop=True)

    return combined_forecast, sourcing_scenarios
