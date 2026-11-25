"""BP3 Forecasting Models for Provincial Rice Production using Standard Libraries.

Implements forecasting models using established, industry-standard library dependencies:
- Naive Persistence (Lag-1 baseline) using pandas.Series
- Simple Moving Average (SMA-3) using pandas.Series.rolling
- Damped Holt's Linear Exponential Smoothing using statsmodels.tsa.holtwinters.Holt
- Linear Trend (5-Year) using sklearn.linear_model.LinearRegression
- Component Model (Area x Yield) combining sklearn LinearRegression and statsmodels Holt
"""

import warnings
from typing import Dict
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from statsmodels.tsa.holtwinters import Holt


class NaiveModel:
    """Naive persistence baseline: forecast equals the most recent observed value."""

    name = "naive"
    display_name = "Naive Baseline (Lag-1)"

    def predict_series(self, values: np.ndarray, horizon: int = 1) -> float:
        if len(values) == 0:
            raise ValueError("Cannot predict from empty history")
        return float(pd.Series(values, dtype=float).iloc[-1])


class MovingAverageModel:
    """Simple Moving Average over the past `window` observations using pandas rolling."""

    name = "sma3"
    display_name = "3-Year Moving Average (SMA-3)"

    def __init__(self, window: int = 3):
        self.window = window

    def predict_series(self, values: np.ndarray, horizon: int = 1) -> float:
        if len(values) == 0:
            raise ValueError("Cannot predict from empty history")
        series = pd.Series(values, dtype=float)
        pred = series.rolling(window=self.window, min_periods=1).mean().iloc[-1]
        return float(pred)


class HoltLinearModel:
    """Damped Holt's Linear Exponential Smoothing using statsmodels.tsa.holtwinters.Holt."""

    name = "holt"
    display_name = "Damped Holt's Linear"

    def predict_series(self, values: np.ndarray, horizon: int = 1) -> float:
        n = len(values)
        if n == 0:
            raise ValueError("Cannot predict from empty history")
        if n < 3:
            return float(values[-1])

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore")
            try:
                model = Holt(
                    values.astype(float),
                    damped_trend=True,
                    initialization_method="estimated",
                )
                fitted = model.fit(optimized=True)
                pred = fitted.forecast(horizon)[-1]
            except Exception:
                model = Holt(
                    values.astype(float),
                    damped_trend=True,
                    initialization_method="heuristic",
                )
                fitted = model.fit(optimized=False)
                pred = fitted.forecast(horizon)[-1]

        return float(max(0.0, pred))


class LinearTrendModel:
    """Ordinary Least Squares Linear Trend on recent history window using sklearn.linear_model.LinearRegression."""

    name = "trend"
    display_name = "Linear Trend (5-Year)"

    def __init__(self, window: int = 5):
        self.window = window

    def predict_series(self, values: np.ndarray, horizon: int = 1) -> float:
        n = len(values)
        if n == 0:
            raise ValueError("Cannot predict from empty history")
        if n < 2:
            return float(values[-1])

        k = min(n, self.window)
        y = values[-k:].astype(float)
        X = np.arange(k).reshape(-1, 1)

        model = LinearRegression()
        model.fit(X, y)
        target_X = np.array([[k - 1 + horizon]])
        pred = model.predict(target_X)[0]
        return float(max(0.0, pred))


class ComponentModel:
    """Component Forecasting Model: Area forecast (sklearn) * Yield forecast (statsmodels).

    Forecasts sown area using sklearn LinearRegression and yield using statsmodels Holt's
    Exponential Smoothing, then combines them to produce implied rice production.
    """

    name = "component"
    display_name = "Component Model (Area × Yield)"

    def __init__(self):
        self.area_model = LinearTrendModel(window=5)
        self.yield_model = HoltLinearModel()

    def predict_province(self, history: pd.DataFrame, horizon: int = 1) -> float:
        if history.empty:
            raise ValueError("Cannot predict from empty history")
        sorted_history = history.sort_values("year")
        area_vals = sorted_history["rice_area_ha"].to_numpy(dtype=float)
        yield_vals = sorted_history["rice_yield_ton_ha"].to_numpy(dtype=float)

        pred_area = self.area_model.predict_series(area_vals, horizon)
        pred_yield = self.yield_model.predict_series(yield_vals, horizon)
        return float(max(0.0, pred_area * pred_yield))


def get_available_models():
    """Returns mapping of model identifier to instantiated model instance."""
    return {
        "naive": NaiveModel(),
        "sma3": MovingAverageModel(window=3),
        "holt": HoltLinearModel(),
        "trend": LinearTrendModel(window=5),
        "component": ComponentModel(),
    }
