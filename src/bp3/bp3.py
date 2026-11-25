"""Build BP3 forecasting marts and backtest evaluations from shared agriculture panel.

Run: python -m src.bp3.bp3 or python src/bp3/bp3.py.
Outputs:
- data/analytics/bp3/forecast_next_year.parquet
- data/analytics/bp3/historical_backtest.parquet
- data/analytics/bp3/model_performance.parquet
- data/analytics/bp3/sourcing_scenarios.parquet
"""

from pathlib import Path
import json
import tempfile
import unicodedata

import numpy as np
import pandas as pd

from src.bp3.backtest import evaluate_model_performance, run_walk_forward_backtest
from src.bp3.scenarios import generate_forecast_next_year


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
SOURCE = DATA / "processed/agriculture/rice_province_year/rice_province_year.parquet"
REFERENCE = DATA / "vietnam_regions_provinces.json"
OUTPUT_DIR = DATA / "analytics/bp3"
GEOGRAPHY = ["province_id", "province_name", "region"]
METRICS = ["rice_area_ha", "rice_yield_ton_ha", "rice_production_ton"]


def read_panel() -> pd.DataFrame:
    """Read and validate the shared provincial panel against reference metadata."""
    if not REFERENCE.is_file():
        raise FileNotFoundError(f"Missing geographical reference: {REFERENCE}")
    if not SOURCE.is_file():
        raise FileNotFoundError(f"Missing processed agriculture panel: {SOURCE}")

    entries = json.loads(REFERENCE.read_text(encoding="utf-8-sig"))
    records = [
        (unicodedata.normalize("NFC", name.strip()), entry["region_name"].strip())
        for entry in entries
        for name in entry["provinces"]
    ]
    ref_df = pd.DataFrame(records, columns=["province_name", "region"])
    ref_df.insert(0, "province_id", range(1, len(ref_df) + 1))
    if ref_df["province_name"].duplicated().any() or ref_df["region"].nunique() != 7:
        raise ValueError("Reference JSON must have 63 unique provinces in 7 regions")

    panel = pd.read_parquet(SOURCE, columns=["year", *GEOGRAPHY, *METRICS])
    if panel.empty:
        raise ValueError("Shared agricultural panel is empty")

    for col in ["year", "province_id"]:
        if not pd.api.types.is_integer_dtype(panel[col]):
            raise ValueError(f"Column {col} must be integer type")

    if panel[GEOGRAPHY].isna().any().any():
        raise ValueError("Missing values found in geography keys")

    if panel.duplicated(["province_id", "year"]).any():
        raise ValueError("Duplicate (province_id, year) keys detected")

    # Verify against reference
    mapped = panel.merge(ref_df, on=GEOGRAPHY, how="left", indicator=True)
    if mapped["_merge"].ne("both").any():
        raise ValueError("Province records do not match reference geography JSON")

    years = sorted(panel["year"].unique())
    if len(years) < 5 or years != list(range(years[0], years[-1] + 1)):
        raise ValueError(f"Expected continuous chronological years, got {years}")

    for metric in METRICS:
        vals = panel[metric].to_numpy(dtype=float)
        if not np.isfinite(vals).all() or (vals < 0).any():
            raise ValueError(f"Metric {metric} contains non-finite or negative values")

    return panel.sort_values(["province_id", "year"]).reset_index(drop=True)


def build_bp3_marts():
    """Execute complete BP3 pipeline and atomically save analytical Parquets."""
    print("Reading and validating shared provincial panel...")
    panel = read_panel()
    print(f"Panel verified: {len(panel)} records across {panel['year'].min()}–{panel['year'].max()}.")

    print("\nRunning chronological walk-forward backtest (2017–2024)...")
    backtest_df = run_walk_forward_backtest(panel, start_test_year=2017, end_test_year=2024)
    print(f"Backtest complete: {len(backtest_df)} prediction records evaluated.")

    print("\nEvaluating model performance metrics...")
    performance_df = evaluate_model_performance(backtest_df)
    print(f"Model performance computed: {len(performance_df)} metric rows across grains.")

    print("\nGenerating 2025 out-of-sample forecast and sourcing scenarios...")
    forecast_df, scenarios_df = generate_forecast_next_year(
        panel, performance_df, forecast_year=2025, cutoff_year=2024
    )
    print(f"Forecasts generated: {len(forecast_df)} forecast entries, {len(scenarios_df)} regional sourcing rows.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    outputs = {
        "forecast_next_year.parquet": forecast_df,
        "historical_backtest.parquet": backtest_df,
        "model_performance.parquet": performance_df,
        "sourcing_scenarios.parquet": scenarios_df,
    }

    print("\nWriting analytical marts atomically...")
    with tempfile.TemporaryDirectory(dir=OUTPUT_DIR) as tmp_dir:
        tmp_path = Path(tmp_dir)
        for filename, df in outputs.items():
            staging_file = tmp_path / filename
            df.to_parquet(staging_file, index=False)
            target_file = OUTPUT_DIR / filename
            staging_file.replace(target_file)
            print(f"  ✓ Published {target_file.name} ({len(df)} rows)")

    # Read back verification
    print("\nVerifying published marts...")
    for filename in outputs:
        path = OUTPUT_DIR / filename
        verified = pd.read_parquet(path)
        if verified.empty:
            raise ValueError(f"Published mart {filename} is empty!")
        print(f"  ✓ {filename}: Verified readable, {len(verified)} rows, {len(verified.columns)} columns.")

    print("\nBP3 analytics build completed successfully.")


if __name__ == "__main__":
    build_bp3_marts()
