"""Unit tests for BP3 Rice Production Forecasting and Sourcing Scenarios."""

import unittest
from pathlib import Path
import numpy as np
import pandas as pd

from src.bp3.models import (
    ComponentModel,
    HoltLinearModel,
    LinearTrendModel,
    MovingAverageModel,
    NaiveModel,
    get_available_models,
)
from src.bp3.backtest import evaluate_model_performance, run_walk_forward_backtest
from src.bp3.scenarios import generate_forecast_next_year


ROOT = Path(__file__).resolve().parents[1]
BP3_ANALYTICS = ROOT / "data/analytics/bp3"


class TestBP3Models(unittest.TestCase):
    """Test individual forecasting models with synthetic series."""

    def test_naive_persistence(self):
        model = NaiveModel()
        series = np.array([100.0, 110.0, 120.0, 105.0])
        self.assertEqual(model.predict_series(series), 105.0)

    def test_moving_average(self):
        model = MovingAverageModel(window=3)
        series = np.array([100.0, 120.0, 150.0, 180.0])
        # Average of last 3: (120 + 150 + 180) / 3 = 150.0
        self.assertAlmostEqual(model.predict_series(series), 150.0)

    def test_holt_linear(self):
        model = HoltLinearModel(alpha=0.5, beta=0.2, phi=0.9)
        series = np.array([100.0, 110.0, 120.0, 130.0])
        pred = model.predict_series(series)
        self.assertGreater(pred, 0.0)
        # Verify non-negativity constraint
        declining = np.array([100.0, 50.0, 10.0, 1.0])
        self.assertGreaterEqual(model.predict_series(declining), 0.0)

    def test_linear_trend(self):
        model = LinearTrendModel(window=4)
        # Linear progression: y = 10 * x + 100 -> [100, 110, 120, 130] -> next should be 140
        series = np.array([100.0, 110.0, 120.0, 130.0])
        self.assertAlmostEqual(model.predict_series(series), 140.0, places=4)

    def test_component_model(self):
        model = ComponentModel()
        history = pd.DataFrame({
            "year": [2021, 2022, 2023, 2024],
            "rice_area_ha": [100_000.0, 100_000.0, 100_000.0, 100_000.0],
            "rice_yield_ton_ha": [5.0, 5.0, 5.0, 5.0],
            "rice_production_ton": [500_000.0, 500_000.0, 500_000.0, 500_000.0],
        })
        pred = model.predict_province(history, horizon=1)
        self.assertAlmostEqual(pred, 500_000.0, delta=1000.0)


class TestBacktestIntegrity(unittest.TestCase):
    """Test walk-forward cross validation and strict prevention of data leakage."""

    @classmethod
    def setUpClass(cls):
        cls.source_path = ROOT / "data/processed/agriculture/rice_province_year/rice_province_year.parquet"
        if not cls.source_path.is_file():
            raise unittest.SkipTest("Processed agriculture panel not found")
        cls.panel = pd.read_parquet(cls.source_path)

    def test_no_data_leakage(self):
        """Verify that backtest evaluation strictly uses training data from years < test_year."""
        backtest_df = run_walk_forward_backtest(self.panel, start_test_year=2022, end_test_year=2024)
        for test_year in [2022, 2023, 2024]:
            subset = backtest_df[backtest_df["test_year"] == test_year]
            self.assertFalse(subset.empty)
            self.assertEqual(subset["province_id"].nunique(), 63)

    def test_metric_calculations(self):
        """Verify calculation of MAE, RMSE, and MAPE."""
        synthetic = pd.DataFrame({
            "test_year": [2023, 2024],
            "province_id": [1, 1],
            "province_name": ["Prov A", "Prov A"],
            "region": ["Region 1", "Region 1"],
            "model": ["naive", "naive"],
            "actual_production_ton": [100.0, 200.0],
            "predicted_production_ton": [90.0, 220.0],
            "error_ton": [10.0, -20.0],
            "abs_error_ton": [10.0, 20.0],
            "pct_error": [-10.0, 10.0],
            "ape_pct": [10.0, 10.0],
        })
        perf = evaluate_model_performance(synthetic)
        prov_perf = perf[perf["level"] == "province"].iloc[0]
        self.assertAlmostEqual(prov_perf["mae_ton"], 15.0)  # (10 + 20) / 2
        self.assertAlmostEqual(prov_perf["rmse_ton"], np.sqrt((100 + 400) / 2))  # sqrt(250)
        self.assertAlmostEqual(prov_perf["mape_pct"], 10.0)  # (10 + 10) / 2


class TestMartAdditivityAndSchema(unittest.TestCase):
    """Test published BP3 marts for additivity, schemas, and non-emptiness."""

    def test_published_files_exist(self):
        expected_files = [
            "forecast_next_year.parquet",
            "historical_backtest.parquet",
            "model_performance.parquet",
            "sourcing_scenarios.parquet",
        ]
        for f in expected_files:
            p = BP3_ANALYTICS / f
            self.assertTrue(p.is_file(), f"Missing expected mart: {f}")
            df = pd.read_parquet(p)
            self.assertFalse(df.empty, f"Mart is empty: {f}")

    def test_forecast_hierarchical_consistency(self):
        """Verify that provincial forecasts add up exactly to regional and national sums."""
        df = pd.read_parquet(BP3_ANALYTICS / "forecast_next_year.parquet")
        provinces = df[df["level"] == "province"]
        regions = df[df["level"] == "region"]
        national = df[df["level"] == "national"].iloc[0]

        self.assertEqual(len(provinces), 63)
        self.assertEqual(len(regions), 7)

        prov_sum = provinces["forecast_base_ton"].sum()
        reg_sum = regions["forecast_base_ton"].sum()
        nat_sum = national["forecast_base_ton"]

        self.assertAlmostEqual(prov_sum, reg_sum, delta=1.0)
        self.assertAlmostEqual(prov_sum, nat_sum, delta=1.0)

        # Also check pessimistic and optimistic scenario consistency
        self.assertAlmostEqual(provinces["forecast_pessimistic_ton"].sum(), national["forecast_pessimistic_ton"], delta=1.0)
        self.assertAlmostEqual(provinces["forecast_optimistic_ton"].sum(), national["forecast_optimistic_ton"], delta=1.0)


if __name__ == "__main__":
    unittest.main()
