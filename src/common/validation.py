"""Runtime structural checks and non-destructive data-quality warnings."""

from pyspark.sql import functions as F

from src.common.cleaning import MEASUREMENTS

TARGET_TYPES = {"year": "int", "province_id": "int", "province_name": "string", "region": "string",
                **{name: "double" for name in MEASUREMENTS}}


def sample(frame, columns, limit=10):
    return [r.asDict() for r in frame.select(*columns).orderBy(*columns).limit(limit).collect()]


def validate_source_keys(observations):
    bad = observations.filter(F.col("year").isNull() | ~F.col("year").between(1900, 2100)
                              | F.col("province_key").isNull() | (F.col("province_key") == ""))
    if bad.limit(1).count():
        raise ValueError(f"Invalid source province/year key: {sample(bad, ['source_file', 'source_cell', 'year_raw', 'source_province_name'])}")
    duplicates = observations.groupBy("metric", "province_key", "year").count().filter("count > 1")
    if duplicates.limit(1).count():
        raise ValueError(f"Duplicate source keys would cause many-to-many joins: {sample(duplicates, ['metric', 'province_key', 'year', 'count'])}")


def quality_report(panel, observations, reference):
    if dict(panel.dtypes) != TARGET_TYPES or panel.columns != list(TARGET_TYPES):
        raise ValueError(f"Unexpected processed schema: {panel.dtypes}; expected {TARGET_TYPES}")
    if panel.filter(F.col("year").isNull() | F.col("province_name").isNull()
                    | (F.trim(F.col("province_name")) == "")).limit(1).count():
        raise ValueError("Processed dataset contains null/empty province-year keys")

    duplicates = panel.groupBy("province_name", "year").count().filter("count > 1").count()

    if duplicates:
        raise ValueError(f"Processed dataset has {duplicates} duplicate province-year keys")
    identified = panel.filter(F.col("province_id").isNotNull())
    id_duplicates = identified.groupBy("province_id", "year").count().filter("count > 1").count()
    if id_duplicates or identified.filter(F.col("province_id") <= 0).limit(1).count():
        raise ValueError("Processed dataset has duplicate province_id-year keys or nonpositive IDs")
    count = panel.count()
    if not count:
        raise ValueError("No province observations remain after excluding totals")

    missing = panel.agg(*[F.sum(F.col(c).isNull().cast("long")).alias(c) for c in panel.columns]).first().asDict()
    negatives = panel.agg(*[F.sum((F.col(c) < 0).cast("long")).alias(c) for c in MEASUREMENTS]).first().asDict()
    negatives = {k: v or 0 for k, v in negatives.items()}
    invalid = observations.filter("invalid_numeric")
    unmatched = panel.filter(F.col("region").isNull())
    expected = F.col("rice_area_ha") * F.col("rice_yield_ton_ha")
    complete = panel.filter(reduce_and([F.col(c).isNotNull() & (F.col(c) >= 0) for c in MEASUREMENTS]))
    comparison = complete.withColumn("expected_production_ton", expected)
    comparison = comparison.withColumn("difference_ton", F.abs(F.col("rice_production_ton") - expected))
    inconsistent = comparison.filter(F.col("difference_ton") > F.greatest(F.lit(100.0), F.abs(expected) * 0.02))
    keys = observations.select("province_key").distinct()
    absent_reference = reference.join(keys, "province_key", "left_anti")

    report = {
        "record_count": count, "schema": TARGET_TYPES, "duplicate_province_year_count": duplicates,
        "year_coverage": [r.asDict() for r in panel.groupBy("year").count().orderBy("year").collect()],
        "year_min": panel.agg(F.min("year")).first()[0], "year_max": panel.agg(F.max("year")).first()[0],
        "province_count": panel.select("province_name").distinct().count(),
        "province_id_count": identified.select("province_id").distinct().count(),
        "province_id_min": identified.agg(F.min("province_id")).first()[0],
        "province_id_max": identified.agg(F.max("province_id")).first()[0],
        "duplicate_province_id_year_count": id_duplicates,
        "region_count": panel.filter(F.col("region").isNotNull()).select("region").distinct().count(),
        "missing_values": missing, "negative_measurements": negatives,
        "invalid_numeric_count": invalid.count(),
        "invalid_numeric_examples": sample(invalid, ["source_file", "source_sheet", "source_cell", "value_raw"]),
        "unmatched_observation_count": unmatched.count(),
        "unmatched_provinces": sample(unmatched.select("province_name").distinct(), ["province_name"], 100),
        "reference_provinces_without_observations": sample(absent_reference, ["province_name"], 100),
        "consistency": {"rule": "abs(production - area * yield) > max(100 tons, 0.02 * abs(area * yield))",
                        "evaluated_records": complete.count(), "warning_count": inconsistent.count(),
                        "examples": sample(inconsistent, ["year", "province_name", *MEASUREMENTS,
                                                           "expected_production_ton", "difference_ton"])},
        "source_name_mapping": [r.asDict() for r in observations.select("province_key", "source_province_name")
                                .distinct().join(reference, "province_key", "left")
                                .orderBy("province_key", "source_province_name").collect()],
        "warnings": [],
    }
    for label, amount in [("missing measurements", sum(missing[c] for c in MEASUREMENTS)),
                          ("negative measurements (retained)", sum(negatives.values())),
                          ("invalid numerical values (null in output)", report["invalid_numeric_count"]),
                          ("unmatched province observations (retained)", report["unmatched_observation_count"]),
                          ("production consistency deviations", report["consistency"]["warning_count"])]:
        if amount:
            report["warnings"].append(f"{label}: {amount}")
    if report["reference_provinces_without_observations"]:
        report["warnings"].append("Some reference provinces have no source observations; no rows were invented.")
    if missing["province_id"]:
        report["warnings"].append(f"Unmatched observations have null project province_id: {missing['province_id']}")
    return report


def reduce_and(expressions):
    from functools import reduce
    return reduce(lambda a, b: a & b, expressions)
