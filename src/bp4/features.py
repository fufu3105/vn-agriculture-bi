"""Validated, compact BP4 data foundation. No source datasets are overwritten."""
import json
import hashlib
import calendar
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
KEY = ["province_id", "year"]


def reference():
    regions = json.loads((ROOT / "data/vietnam_regions_provinces.json").read_text(encoding="utf-8"))
    rows = [(province, region["region_name"]) for region in regions for province in region["provinces"]]
    if len(rows) != 63 or len(regions) != 7 or len({province for province, _ in rows}) != 63:
        raise ValueError("Expected seven regions and 63 historical provinces")
    return pd.DataFrame([(i, province, region) for i, (province, region) in enumerate(rows, 1)],
                        columns=["province_id", "province_name", "region"])


def validate(frame, keys, numeric):
    required = set(keys + numeric)
    if not required.issubset(frame.columns):
        raise ValueError(f"Missing columns: {sorted(required - set(frame.columns))}")
    result = frame.copy()
    for col in required:
        values = pd.to_numeric(result[col], errors="raise")
        if np.isinf(values.dropna()).any():
            raise ValueError(f"Nonfinite {col}")
        if col in keys:
            if values.isna().any() or values.mod(1).ne(0).any():
                raise ValueError(f"Invalid integer key {col}")
            values = values.astype("int64")
        result[col] = values
    if result.duplicated(keys).any():
        raise ValueError(f"Duplicate keys {keys}")
    if "month" in result and not result.month.between(1, 12).all():
        raise ValueError("Invalid month")
    for col in numeric:
        if ("rainfall" in col or col.startswith("rice_")) and result[col].lt(0).any():
            raise ValueError(f"Negative {col}")
    return result

OUT = ROOT / "data/analytics/bp4/diagnostic_bi"
AGRICULTURE = ROOT / "data/processed/agriculture/rice_province_year/rice_province_year.parquet"
WEATHER = ROOT / "data/processed/weather"
OUTCOMES = {"Yield": "yield_value", "Production": "production_ton"}
CLIMATE = {"Temperature": "temperature_c", "Rainfall": "rainfall_mm"}
UNITS = {"yield_value": "t/ha", "production_ton": "tonnes", "temperature_c": "C", "rainfall_mm": "mm"}


def derive(frame, group, baseline=(2010, 2024), minimum=8):
    """Calendar-safe changes, retrospective residuals and explicit reference coverage."""
    f = frame.sort_values([group, "year"]).copy()
    for col, short in [("yield_value", "yield"), ("production_ton", "production"), ("area_ha", "area")]:
        previous = f.groupby(group)[col].shift()
        consecutive = f.groupby(group).year.diff().eq(1) & previous.gt(0)
        f[short + "_change_pct"] = (f[col] / previous - 1).mul(100).where(consecutive)
        if short != "area":
            f[short + "_trend"] = np.nan
            for _, g in f.groupby(group):
                valid = g.dropna(subset=[col])
                if len(valid) >= minimum and valid.year.nunique() >= minimum:
                    fit = stats.linregress(valid.year, valid[col])
                    f.loc[g.index, short + "_trend"] = fit.intercept + fit.slope * g.year
            f[short + "_deviation"] = f[col] - f[short + "_trend"]
            f[short + "_deviation_pct"] = f[short + "_deviation"].div(f[short + "_trend"].where(f[short + "_trend"].gt(0))).mul(100)
    base = f[f.year.between(*baseline)]
    required = max(minimum, int(np.ceil((baseline[1] - baseline[0] + 1) * .9)))
    for col in CLIMATE.values():
        ref = base.groupby(group)[col].agg(["mean", "count"])
        f[col + "_reference_n"] = f[group].map(ref["count"]).fillna(0).astype(int)
        mean = f[group].map(ref["mean"]).where(f[col + "_reference_n"].ge(required))
        f[col + "_anomaly"] = f[col] - mean if col == "temperature_c" else (f[col] / mean.where(mean.gt(0)) - 1) * 100
    return f


def select(frame, years, regions):
    """An empty region selection deliberately returns no observations."""
    return frame[frame.year.between(*years) & frame.region.isin(regions)].copy()


def weighted_weather(g, col, weights, minimum=.9):
    valid = g[col].notna() & g.data_status.eq("complete") & weights.gt(0)
    total = weights.sum(min_count=len(weights))
    coverage = weights[valid].sum() / total if total > 0 else 0.
    return (float(np.average(g.loc[valid, col], weights=weights[valid])) if coverage >= minimum else np.nan), coverage


def prepare():
    ref = reference()
    a = validate(pd.read_parquet(AGRICULTURE), KEY, ["rice_production_ton", "rice_area_ha", "rice_yield_ton_ha"])
    w = validate(pd.read_parquet(WEATHER / "weather_yearly/weather_yearly.parquet"), KEY, ["avg_temperature_c", "yearly_rainfall_mm"])
    m = validate(pd.read_parquet(WEATHER / "weather_monthly/weather_monthly.parquet"), KEY + ["month"], ["avg_temperature_c", "total_rainfall_mm"])
    for label,source in [("yearly",w),("monthly",m)]:
        required={"data_status","valid_temperature_days","valid_rainfall_days","expected_days"}
        if not required.issubset(source): raise ValueError(f"Missing {label} completeness indicators")
        expected=source.apply(lambda row: calendar.monthrange(int(row.year),int(row.month))[1] if label=="monthly" else 366 if calendar.isleap(int(row.year)) else 365,axis=1)
        valid=source.expected_days.eq(expected) & source.valid_temperature_days.eq(expected) & source.valid_rainfall_days.eq(expected)
        source.loc[~valid,"data_status"]="incomplete"
    for label, source in [("agriculture", a), ("yearly weather", w), ("monthly weather", m)]:
        if not source.province_id.isin(ref.province_id).all():
            raise ValueError(f"Unknown historical province in {label}")
    mapped = a.merge(ref, on="province_id", suffixes=("", "_ref"), validate="many_to_one")
    if any(not mapped[col].eq(mapped[col + "_ref"]).all() for col in ["region", "province_name"]):
        raise ValueError("Historical names or region mapping do not match the 63-province reference")
    grid = pd.MultiIndex.from_product([ref.province_id, range(2010, 2025)], names=KEY).to_frame(index=False)
    p = grid.merge(a, on=KEY, how="left", validate="one_to_one").drop(columns=["region", "province_name"])
    p = p.merge(ref, on="province_id").merge(w, on=KEY, how="left", validate="one_to_one")
    p = p.rename(columns={"rice_area_ha": "area_ha", "rice_production_ton": "production_ton", "rice_yield_ton_ha": "reported_yield_ton_ha", "avg_temperature_c": "temperature_c", "yearly_rainfall_mm": "rainfall_mm"})
    p["yield_value"] = p.production_ton / p.area_ha.where(p.area_ha.gt(0))
    p["source_yield_difference_ton_ha"] = p.yield_value - p.reported_yield_ton_ha
    p["complete"] = p[["area_ha", "production_ton", "temperature_c", "rainfall_mm"]].notna().all(axis=1) & p.data_status.eq("complete")
    p.loc[~p.data_status.eq("complete"), ["temperature_c", "rainfall_mm"]] = np.nan
    rows = []
    for (region, year), g in p.groupby(["region", "year"]):
        area, production = g.area_ha.sum(min_count=len(g)), g.production_ton.sum(min_count=len(g))
        row = dict(region=region, year=year, area_ha=area, production_ton=production,
                   yield_value=production / area if area > 0 else np.nan, province_n=len(g), complete=g.complete.all())
        for col in CLIMATE.values():
            row[col], row[col + "_coverage"] = weighted_weather(g, col, g.area_ha)
        rows.append(row)
    r = pd.DataFrame(rows)
    # Monthly input is joined to a complete province-month calendar; missing rows remain visible.
    mg = pd.MultiIndex.from_product([ref.province_id, range(2010, 2025), range(1, 13)], names=KEY + ["month"]).to_frame(index=False)
    monthly = mg.merge(m, on=KEY + ["month"], how="left", validate="one_to_one").merge(p[KEY + ["region", "area_ha"]], on=KEY, validate="many_to_one")
    monthly = monthly.rename(columns={"avg_temperature_c": "temperature_c", "total_rainfall_mm": "rainfall_mm"})
    mr = []
    for (region, year, month), g in monthly.groupby(["region", "year", "month"]):
        row = dict(region=region, year=year, month=month)
        for col in CLIMATE.values():
            row[col], row[col + "_coverage"] = weighted_weather(g, col, g.area_ha)
        mr.append(row)
    audit = {"built_utc": datetime.now(timezone.utc).isoformat(), "period": [2010, 2024], "reference_period": [2010, 2024],
             "province_rows": len(p), "regional_rows": len(r), "monthly_rows": len(monthly), "regions": r.region.nunique(),
             "missing_province_values": p.isna().sum().astype(int).to_dict(), "incomplete_province_years": int((~p.complete).sum()),
             "incomplete_province_months": int((~monthly.data_status.eq("complete")).sum()),
             "duplicate_keys": 0, "mapping": "63 historical provinces / 7 project regions; not current administrative boundaries",
             "units": UNITS, "sources": {"agriculture": "NSO V06.13, V06.14, V06.15", "weather": "NASA POWER T2M and PRECTOTCORR; one point per province"},
             "notes": ["Available period replaces requested 2009-2023 and 1991-2020 baseline; no extrapolation.", "Retrospective detrending is not a forecast.", "Regional yield = total tonnes / total hectares. Provincial yield is derived consistently; reported NSO yield retained for rounding audit.", "Annual sown-area weather weights are a proxy, not measured crop exposure."]}
    audit["source_sha256"] = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in
                              [AGRICULTURE, WEATHER/"weather_yearly/weather_yearly.parquet", WEATHER/"weather_monthly/weather_monthly.parquet", ROOT/"data/vietnam_regions_provinces.json"]}
    audit["nonconsecutive_regional_steps"] = int(r.sort_values(["region","year"]).groupby("region").year.diff().dropna().ne(1).sum())
    audit["regional_checks"] = []
    for region,g in r.groupby("region"):
        for col in ["yield_value","production_ton",*CLIMATE.values()]:
            s=g[col].dropna();lo,hi=s.quantile([.25,.75]);iqr=hi-lo
            audit["regional_checks"].append(dict(region=region,indicator=col,n=len(s),zero_variance=s.nunique()<2,
                                                 iqr_outliers=int((s.lt(lo-1.5*iqr)|s.gt(hi+1.5*iqr)).sum())))
    OUT.mkdir(parents=True, exist_ok=True)
    for name, frame in [("province", derive(p, "province_id")), ("regional", derive(r, "region"))]:
        frame.to_parquet(OUT / (name + ".parquet"), index=False)
    (OUT / "quality_report.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return audit
