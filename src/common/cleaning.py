"""Shared Spark transformations for the agricultural province-year panel."""

from functools import reduce

from pyspark.sql import functions as F

from src.common.provinces import province_key

AGGREGATE_LABELS = [
    "Cả nước",
    "Đồng bằng sông Hồng",
    "Trung du và miền núi phía Bắc",
    "Bắc Trung Bộ và Duyên hải miền Trung",
    "Bắc Trung Bộ",
    "Duyên hải Nam Trung Bộ",
    "Tây Nguyên",
    "Đông Nam Bộ",
    "Đồng bằng sông Cửu Long",
]
MEASUREMENTS = ["rice_area_ha", "rice_yield_ton_ha", "rice_production_ton"]
MISSING_MARKERS = ["", "..", "...", "…", "-", "—", "na", "n/a", "null"]


def clean_observations(raw):
    """Keep unknown labels; known national/regional totals are explicitly flagged."""
    text = F.lower(F.trim(F.col("value_raw")))
    missing = F.col("value_raw").isNull() | text.isin(MISSING_MARKERS)
    # Accept decimal points, scientific notation, or unambiguous comma thousands.
    numeric = text.rlike(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$")
    grouped = text.rlike(r"^[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?$")
    value = F.when(~missing & (numeric | grouped),
                   F.regexp_replace(text, ",", "").cast("double"))
    frame = (raw.withColumn("year", F.col("year_raw").cast("int"))
             .withColumn("province_key",
                         province_key(F.col("source_province_name")))
             .withColumn("is_aggregate", F.lower(F.trim(F.col("source_province_name")))
                         .isin([label.lower() for label in AGGREGATE_LABELS]))
             .withColumn("source_missing", missing)
             .withColumn("parsed_value", value))
    invalid = (~F.col("source_missing") & (F.col("parsed_value").isNull()
               | F.isnan("parsed_value") | (F.abs(F.col("parsed_value")) == float("inf"))))
    frame = frame.withColumn("invalid_numeric", invalid)
    converted = F.when(~F.col("invalid_numeric"), F.col("parsed_value") * F.col("conversion_factor"))
    overflow = F.abs(converted) == float("inf")
    return (frame.withColumn("invalid_numeric", F.col("invalid_numeric") | F.coalesce(overflow, F.lit(False)))
            .withColumn("value", F.when(~F.col("invalid_numeric"), converted).cast("double")))


def combine_observations(observations, reference):
    """Full joins retain incomplete keys; duplicates must be rejected beforehand."""
    frames = [observations.filter(F.col("metric") == name)
              .select("province_key", "year", F.col("value").alias(name)) for name in MEASUREMENTS]
    panel = reduce(lambda a, b: a.join(b, ["province_key", "year"], "full"), frames)
    names = observations.groupBy("province_key").agg(F.min("source_province_name").alias("source_name"))
    return (panel.join(names, "province_key", "left").join(reference, "province_key", "left")
            .select(F.col("year").cast("int"), "province_id",
                    F.coalesce("province_name", "source_name").alias("province_name"),
                    "region", *MEASUREMENTS))
