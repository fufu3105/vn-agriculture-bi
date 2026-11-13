"""Build BP2 comparisons from the shared provincial Parquet."""

from pathlib import Path
import json
import tempfile
import unicodedata

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
SOURCE = DATA / "processed/agriculture/rice_province_year/rice_province_year.parquet"
REFERENCE = DATA / "vietnam_regions_provinces.json"
OUTPUT = DATA / "analytics/bp2/production_changes.parquet"
GEOGRAPHY = ["province_id", "province_name", "region"]
METRICS = ["rice_area_ha", "rice_yield_ton_ha", "rice_production_ton"]
YEARS = ["year_start", "year_end"]
COMPONENTS = ["area_effect_ton", "yield_effect_ton", "residual_change_ton"]
ADDITIVE = [
    "rice_area_ha_start", "rice_area_ha_end",
    "rice_production_ton_start", "rice_production_ton_end",
    "production_change_ton", *COMPONENTS, "province_count",
]


def read_panel():
    entries = json.loads(REFERENCE.read_text(encoding="utf-8-sig"))
    records = [
        (unicodedata.normalize("NFC", name.strip()), entry["region_name"].strip())
        for entry in entries
        for name in entry["provinces"]
    ]
    reference = pd.DataFrame(records, columns=["province_name", "region"])
    reference.insert(0, "province_id", range(1, len(reference) + 1))
    if reference["province_name"].duplicated().any() or reference["region"].nunique() != 7:
        raise ValueError("Expected unique provinces mapped to seven regions")

    panel = pd.read_parquet(SOURCE, columns=["year", *GEOGRAPHY, *METRICS])
    if panel.empty or not all(pd.api.types.is_integer_dtype(panel[key]) for key in ["year", "province_id"]):
        raise ValueError("Expected nonempty data with integer province and year keys")
    if panel[["year", *GEOGRAPHY]].isna().any().any() or panel.duplicated(["province_id", "year"]).any():
        raise ValueError("Missing geography/year values or duplicate province-year keys")

    # The shared pipeline already normalized names and excluded source totals.
    # Verify every triple against the JSON so unknown rows cannot enter a sum.
    mapped = panel.merge(reference, on=GEOGRAPHY, how="left", indicator=True)
    if mapped["_merge"].ne("both").any():
        raise ValueError("Province ID, name or region disagrees with the historical JSON reference")

    years = sorted(panel["year"].unique())
    if (
        len(years) < 2
        or years != list(range(years[0], years[-1] + 1))
        or not panel.groupby("year").size().eq(len(reference)).all()
    ):
        raise ValueError("Expected at least two consecutive years with full province coverage")
    if not all(pd.api.types.is_numeric_dtype(panel[metric]) for metric in METRICS):
        raise ValueError("Expected numeric area, yield and production in the shared units")
    values = panel[METRICS].to_numpy(dtype=float, na_value=np.nan)
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("Area, yield and production must be finite and nonnegative")
    return panel


def decompose(panel):
    # Pair endpoints within each province. This also supports non-adjacent years.
    pairs = panel.merge(panel, on=GEOGRAPHY, suffixes=("_start", "_end"))
    pairs = pairs.loc[pairs["year_start"] < pairs["year_end"]].copy()
    a0, a1 = (pairs[f"rice_area_ha_{end}"] for end in ("start", "end"))
    y0, y1 = (pairs[f"rice_yield_ton_ha_{end}"] for end in ("start", "end"))
    p0, p1 = (pairs[f"rice_production_ton_{end}"] for end in ("start", "end"))
    pairs["area_effect_ton"] = (a1 - a0) * (y0 + y1) / 2
    pairs["yield_effect_ton"] = (y1 - y0) * (a0 + a1) / 2
    pairs["residual_change_ton"] = (p1 - a1 * y1) - (p0 - a0 * y0)
    pairs["production_change_ton"] = p1 - p0
    pairs["province_count"] = 1

    provinces = pairs[[*YEARS, *GEOGRAPHY, *ADDITIVE]].assign(level="province")
    regions = provinces.groupby([*YEARS, "region"], as_index=False)[ADDITIVE].sum()
    national = provinces.groupby(YEARS, as_index=False)[ADDITIVE].sum()
    result = pd.concat(
        [provinces, regions.assign(level="region"), national.assign(level="national")],
        ignore_index=True,
    )
    result["province_id"] = result["province_id"].astype("Int32")
    result = result[["level", *YEARS, *GEOGRAPHY, *ADDITIVE]]
    if not np.allclose(
        result[COMPONENTS].sum(axis=1), result["production_change_ton"], atol=1e-6, rtol=0
    ):
        raise ValueError("Decomposition does not reconcile with the reported production change")
    return result.sort_values(["year_start", "year_end", "level", "region", "province_id"])


def main():
    result = decompose(read_panel())
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    # Publish a complete snapshot even if a run stops during the write.
    with tempfile.TemporaryDirectory(dir=OUTPUT.parent) as directory:
        staging = Path(directory) / OUTPUT.name
        result.to_parquet(staging, engine="pyarrow", index=False)
        staging.replace(OUTPUT)
    print(f"Wrote {len(result):,} rows to {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
