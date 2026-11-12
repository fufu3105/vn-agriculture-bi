"""Build BP1 Parquet marts from the shared processed agriculture panel.

Run: python src/bp1/bp1.py. Never reads raw inputs or writes processed data.
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "data/processed/agriculture/rice_province_year"
OUTPUT = ROOT / "data/analytics/bp1"
METRICS = ["rice_area_ha", "rice_yield_ton_ha", "rice_production_ton"]
COLUMNS = ["year", "province_id", "province_name", "region", *METRICS]
PROFILE_START, PROFILE_END = 2010, 2024


def validate_panel(panel):
    missing = set(COLUMNS) - set(panel.columns)
    if missing:
        raise ValueError(f"Missing processed columns: {sorted(missing)}")
    panel = panel[COLUMNS].copy()
    if panel.empty or panel.isna().any().any():
        raise ValueError("BP1 requires complete province, region and measurement data.")
    for column in ["province_name", "region"]:
        if panel[column].astype(str).str.strip().eq("").any():
            raise ValueError(f"Empty values in {column}")
    for column in ["year", "province_id", *METRICS]:
        if not pd.api.types.is_numeric_dtype(panel[column]) or not np.isfinite(panel[column]).all():
            raise ValueError(f"Invalid numeric values in {column}")
    for column in ["year", "province_id"]:
        if (panel[column] % 1 != 0).any() or (panel[column] <= 0).any():
            raise ValueError(f"Invalid integer keys in {column}")
    if panel.duplicated(["province_id", "year"]).any() or panel.duplicated(["province_name", "year"]).any():
        raise ValueError("Duplicate province-year keys")
    reference = panel[["province_id", "province_name", "region"]].drop_duplicates()
    if reference["province_id"].duplicated().any() or reference["province_name"].duplicated().any():
        raise ValueError("Province identities or region mappings change between years")
    years = sorted(panel["year"].unique())
    if years != list(range(int(years[0]), int(years[-1]) + 1)):
        raise ValueError("Missing statistical years")
    if len(panel) != len(reference) * len(years):
        raise ValueError("Incomplete province-year coverage")
    if panel[METRICS].lt(0).any().any():
        raise ValueError("Negative area, yield or production")
    return panel.sort_values(["province_id", "year"]).reset_index(drop=True)


def aggregate(panel, keys):
    """Sum area/production; area-weight the published provincial yields."""
    data = panel.assign(weighted_yield=panel["rice_area_ha"] * panel["rice_yield_ton_ha"])
    result = data.groupby(keys, as_index=False).agg(
        rice_area_ha=("rice_area_ha", "sum"),
        rice_production_ton=("rice_production_ton", "sum"),
        weighted_yield=("weighted_yield", "sum"),
        province_count=("province_id", "nunique"),
    )
    result["rice_yield_ton_ha"] = result.pop("weighted_yield") / result["rice_area_ha"].replace(0, np.nan)
    return result


def add_features(frame, group):
    """Use only past/current data for annual changes, shares and ranks."""
    frame = frame.sort_values([group, "year"]).copy()
    grouped = frame.groupby(group, sort=False)
    for metric, prefix in zip(METRICS, ["area", "yield", "production"]):
        previous = grouped[metric].shift(1).replace(0, np.nan)
        frame[f"{prefix}_yoy_pct"] = (frame[metric] / previous - 1) * 100
    for metric, prefix in [("rice_production_ton", "production"), ("rice_area_ha", "area")]:
        total = frame.groupby("year")[metric].transform("sum").replace(0, np.nan)
        frame[f"{prefix}_share_pct"] = frame[metric] / total * 100
    frame["production_rank"] = frame.groupby("year")["rice_production_ton"].rank(method="min", ascending=False).astype(int)
    return frame.reset_index(drop=True)


def build_profile(panel):
    """One retrospective profile per province for the fixed 2010–2024 period."""
    history = panel.loc[panel["year"].between(PROFILE_START, PROFILE_END)]
    wide = history.pivot(index="province_id", columns="year", values="rice_production_ton").sort_index()
    if list(wide.columns) != list(range(PROFILE_START, PROFILE_END + 1)) or wide.isna().any().any():
        raise ValueError("The fixed BP1 profile requires complete production history for 2010–2024")
    first = wide[PROFILE_START].replace(0, np.nan)
    cagr = ((wide[PROFILE_END] / first) ** (1 / (PROFILE_END - PROFILE_START)) - 1) * 100
    growth = wide.div(wide.shift(1, axis=1).replace(0, np.nan)).iloc[:, 1:].sub(1).mul(100)
    volatility = growth.std(axis=1, ddof=1).where(growth.notna().all(axis=1))
    profile = history.loc[history["year"] == PROFILE_END,
                          ["province_id", "province_name", "region", "rice_production_ton"]].copy()
    profile["profile_start_year"] = PROFILE_START
    profile["profile_end_year"] = PROFILE_END
    profile["production_cagr_pct"] = profile["province_id"].map(cagr)
    profile["production_yoy_std_pp"] = profile["province_id"].map(volatility)
    return profile.sort_values("province_id").reset_index(drop=True)


def build_marts(panel):
    panel = validate_panel(panel)
    provinces = add_features(panel, "province_id")
    regions = add_features(aggregate(panel, ["region", "year"]), "region")
    national = aggregate(panel, ["year"]).assign(scope="Vietnam")
    national = add_features(national, "scope").drop(columns="scope")
    for column in ["rice_area_ha", "rice_production_ton"]:
        expected = panel.groupby("year")[column].sum().sort_index()
        if not np.allclose(expected, regions.groupby("year")[column].sum().sort_index()):
            raise ValueError(f"Regional {column} totals do not reconcile")
        if not np.allclose(expected, national.set_index("year")[column].sort_index()):
            raise ValueError(f"National {column} totals do not reconcile")
    return {"province_year": provinces, "region_year": regions, "national_year": national,
            "province_profile_2010_2024": build_profile(panel)}


def main():
    if not INPUT.is_dir():
        raise SystemExit("Shared Parquet is missing. Run: python scripts/build_processed.py")
    marts = build_marts(pd.read_parquet(INPUT))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name, frame in marts.items():
        path = OUTPUT / f"{name}.parquet"
        temporary = path.with_suffix(".parquet.tmp")
        frame.to_parquet(temporary, engine="pyarrow", index=False, compression="snappy")
        pd.testing.assert_frame_equal(frame, pd.read_parquet(temporary))
        temporary.replace(path)
        print(f"{path.relative_to(ROOT)}: {len(frame)} rows")
    print("BP1 analytics ready. Start: python -m streamlit run dashboard/app.py")


if __name__ == "__main__":
    main()
