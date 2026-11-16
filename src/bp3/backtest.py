"""Walk-forward chronological backtesting engine for BP3.

Evaluates forecasting models strictly without lookahead bias across 2017–2024.
Computes evaluation metrics (MAE, RMSE, MAPE, Bias) at province, region, and national grains.
"""

from typing import Dict, List, Tuple
import numpy as np
import pandas as pd

from src.bp3.models import ComponentModel, get_available_models


def run_walk_forward_backtest(
    panel: pd.DataFrame,
    start_test_year: int = 2017,
    end_test_year: int = 2024,
) -> pd.DataFrame:
    """Run chronological walk-forward backtest across test years.

    For each test year T:
    - Training data is strictly data where year < T.
    - Generates 1-step-ahead out-of-sample forecast for each province.
    - Records actual vs predicted values and calculates residual metrics.
    """
    models = get_available_models()
    records = []

    test_years = sorted(
        year for year in panel["year"].unique() if start_test_year <= year <= end_test_year
    )
    if not test_years:
        raise ValueError(f"No test years found in range {start_test_year}..{end_test_year}")

    for test_year in test_years:
        train = panel[panel["year"] < test_year].copy()
        test = panel[panel["year"] == test_year].copy()

        if train.empty or test.empty:
            raise ValueError(f"Empty train or test set for backtest year {test_year}")

        # Group train by province once for efficiency
        train_groups = {pid: grp.sort_values("year") for pid, grp in train.groupby("province_id")}

        for model_key, model in models.items():
            preds = {}
            for pid, history in train_groups.items():
                if isinstance(model, ComponentModel):
                    pred = model.predict_province(history, horizon=1)
                else:
                    y_vals = history["rice_production_ton"].to_numpy(dtype=float)
                    pred = model.predict_series(y_vals, horizon=1)
                preds[pid] = pred

            for _, row in test.iterrows():
                pid = row["province_id"]
                actual = float(row["rice_production_ton"])
                predicted = float(preds.get(pid, np.nan))
                error = actual - predicted
                abs_error = abs(error)
                pct_error = ((predicted / actual) - 1.0) * 100.0 if actual > 0 else 0.0
                ape_pct = (abs_error / actual) * 100.0 if actual > 0 else 0.0

                records.append({
                    "test_year": int(test_year),
                    "province_id": int(pid),
                    "province_name": str(row["province_name"]),
                    "region": str(row["region"]),
                    "model": str(model_key),
                    "actual_production_ton": actual,
                    "predicted_production_ton": predicted,
                    "error_ton": error,
                    "abs_error_ton": abs_error,
                    "pct_error": pct_error,
                    "ape_pct": ape_pct,
                })

    backtest_df = pd.DataFrame(records)
    return backtest_df


def evaluate_model_performance(backtest_df: pd.DataFrame) -> pd.DataFrame:
    """Computes MAE, RMSE, MAPE, and Bias at province, region, and national levels."""
    results = []

    # 1. Province level performance
    prov_grp = backtest_df.groupby(["province_id", "province_name", "region", "model"])
    prov_metrics = prov_grp.agg(
        mae_ton=("abs_error_ton", "mean"),
        rmse_ton=("error_ton", lambda s: float(np.sqrt(np.mean(s ** 2)))),
        mape_pct=("ape_pct", "mean"),
        bias_ton=("error_ton", "mean"),
        test_count=("test_year", "count"),
    ).reset_index()
    prov_metrics["level"] = "province"

    # Identify best model per province by lowest MAE
    best_prov = (
        prov_metrics.sort_values(["province_id", "mae_ton"])
        .groupby("province_id")
        .first()
        .reset_index()
    )
    best_map = set(zip(best_prov["province_id"], best_prov["model"]))
    prov_metrics["is_best_model"] = [
        (pid, m) in best_map for pid, m in zip(prov_metrics["province_id"], prov_metrics["model"])
    ]
    results.append(prov_metrics)

    # 2. Region level performance (aggregated actual vs aggregated prediction per year)
    reg_yearly = backtest_df.groupby(["test_year", "region", "model"]).agg(
        actual_production_ton=("actual_production_ton", "sum"),
        predicted_production_ton=("predicted_production_ton", "sum"),
    ).reset_index()
    reg_yearly["error_ton"] = reg_yearly["actual_production_ton"] - reg_yearly["predicted_production_ton"]
    reg_yearly["abs_error_ton"] = reg_yearly["error_ton"].abs()
    reg_yearly["ape_pct"] = (reg_yearly["abs_error_ton"] / reg_yearly["actual_production_ton"]) * 100.0

    reg_metrics = reg_yearly.groupby(["region", "model"]).agg(
        mae_ton=("abs_error_ton", "mean"),
        rmse_ton=("error_ton", lambda s: float(np.sqrt(np.mean(s ** 2)))),
        mape_pct=("ape_pct", "mean"),
        bias_ton=("error_ton", "mean"),
        test_count=("test_year", "count"),
    ).reset_index()
    reg_metrics["level"] = "region"
    reg_metrics["province_id"] = pd.NA
    reg_metrics["province_name"] = pd.NA

    # Best model per region
    best_reg = (
        reg_metrics.sort_values(["region", "mae_ton"])
        .groupby("region")
        .first()
        .reset_index()
    )
    best_reg_map = set(zip(best_reg["region"], best_reg["model"]))
    reg_metrics["is_best_model"] = [
        (r, m) in best_reg_map for r, m in zip(reg_metrics["region"], reg_metrics["model"])
    ]
    results.append(reg_metrics)

    # 3. National level performance
    nat_yearly = backtest_df.groupby(["test_year", "model"]).agg(
        actual_production_ton=("actual_production_ton", "sum"),
        predicted_production_ton=("predicted_production_ton", "sum"),
    ).reset_index()
    nat_yearly["error_ton"] = nat_yearly["actual_production_ton"] - nat_yearly["predicted_production_ton"]
    nat_yearly["abs_error_ton"] = nat_yearly["error_ton"].abs()
    nat_yearly["ape_pct"] = (nat_yearly["abs_error_ton"] / nat_yearly["actual_production_ton"]) * 100.0

    nat_metrics = nat_yearly.groupby(["model"]).agg(
        mae_ton=("abs_error_ton", "mean"),
        rmse_ton=("error_ton", lambda s: float(np.sqrt(np.mean(s ** 2)))),
        mape_pct=("ape_pct", "mean"),
        bias_ton=("error_ton", "mean"),
        test_count=("test_year", "count"),
    ).reset_index()
    nat_metrics["level"] = "national"
    nat_metrics["region"] = "Vietnam"
    nat_metrics["province_id"] = pd.NA
    nat_metrics["province_name"] = pd.NA

    best_nat_model = nat_metrics.sort_values("mae_ton").iloc[0]["model"]
    nat_metrics["is_best_model"] = nat_metrics["model"] == best_nat_model
    results.append(nat_metrics)

    combined = pd.concat(results, ignore_index=True)
    combined["province_id"] = combined["province_id"].astype("Int32")
    return combined
