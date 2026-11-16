"""BP3 Forecasting Models for Provincial Rice Production.

Implements pure NumPy/Pandas time-series forecasting models:
- Naive Persistence (Lag-1 baseline)
- Simple Moving Average (SMA-3)
- Damped Holt's Linear Exponential Smoothing
- Component Model (Separate Area and Yield forecasts combined as Area * Yield)
- Linear Trend (OLS on recent window)
"""

from typing import Dict, List, Optional
import numpy as np
import pandas as pd


class NaiveModel:
    """Naive persistence baseline: forecast equals the most recent observed value."""

    name = "naive"
    display_name = "Naive Baseline (Lag-1)"

    def predict_series(self, values: np.ndarray, horizon: int = 1) -> float:
        if len(values) == 0:
            raise ValueError("Cannot predict from empty history")
        return float(values[-1])


class MovingAverageModel:
    """Simple Moving Average over the past `window` observations."""

    name = "sma3"
    display_name = "3-Year Moving Average (SMA-3)"

    def __init__(self, window: int = 3):
        self.window = window

    def predict_series(self, values: np.ndarray, horizon: int = 1) -> float:
        if len(values) == 0:
            raise ValueError("Cannot predict from empty history")
        k = min(len(values), self.window)
        return float(np.mean(values[-k:]))


class HoltLinearModel:
    """Damped Holt's Linear Exponential Smoothing with non-negativity constraint."""

    name = "holt"
    display_name = "Damped Holt's Linear"

    def __init__(self, alpha: float = 0.6, beta: float = 0.15, phi: float = 0.85):
        self.alpha = alpha
        self.beta = beta
        self.phi = phi

    def predict_series(self, values: np.ndarray, horizon: int = 1) -> float:
        n = len(values)
        if n == 0:
            raise ValueError("Cannot predict from empty history")
        if n == 1:
            return float(values[0])

        # Initialize level and trend
        level = values[0]
        trend = values[1] - values[0]

        for t in range(1, n):
            prev_level = level
            prev_trend = trend
            level = self.alpha * values[t] + (1 - self.alpha) * (prev_level + self.phi * prev_trend)
            trend = self.beta * (level - prev_level) + (1 - self.beta) * self.phi * prev_trend

        # Forecast h steps ahead with damped trend
        damped_factor = sum(self.phi ** i for i in range(1, horizon + 1))
        forecast = level + damped_factor * trend
        return float(max(0.0, forecast))


class LinearTrendModel:
    """Ordinary Least Squares Linear Trend on recent history window."""

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
        y = values[-k:]
        x = np.arange(k)
        slope, intercept = np.polyfit(x, y, 1)
        # Target step is at index k - 1 + horizon
        pred = slope * (k - 1 + horizon) + intercept
        return float(max(0.0, pred))


class ComponentModel:
    """Component Forecasting Model: Area forecast * Yield forecast.

    Forecasts sown area using SMA-3 and yield using Damped Holt's Exponential Smoothing,
    then combines them to produce implied rice production.
    """

    name = "component"
    display_name = "Component Model (Area × Yield)"

    def __init__(self):
        self.area_model = MovingAverageModel(window=3)
        self.yield_model = HoltLinearModel(alpha=0.5, beta=0.1, phi=0.85)

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
        "holt": HoltLinearModel(alpha=0.6, beta=0.15, phi=0.85),
        "trend": LinearTrendModel(window=5),
        "component": ComponentModel(),
    }
