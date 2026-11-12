"""Shared Spark transformations for agriculture and weather datasets."""

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


def clean_weather_daily(spark, records, province_ids, start, end):
    raw = spark.createDataFrame(records, "province_id int, date_raw string, temperature_raw string, rainfall_raw string, fill_value double")
    raw = raw.withColumn("date", F.to_date(F.try_to_timestamp("date_raw", F.lit("yyyyMMdd"))))
    if raw.filter(F.col("date").isNull() | ~F.col("province_id").isin(province_ids)).limit(1).count():
        raise ValueError("Invalid daily date or province identifier")
    if raw.groupBy("province_id", "date").count().filter("count > 1").limit(1).count():
        raise ValueError("Duplicate province-date observations")
    if raw.filter(~F.col("date").between(start.isoformat(), end.isoformat())).limit(1).count():
        raise ValueError("Daily observation outside configured window")
    for variable in ["temperature", "rainfall"]:
        number = F.expr(f"try_cast({variable}_raw as double)")
        missing = F.col(f"{variable}_raw").isNull() | (number == F.col("fill_value"))
        invalid = number.isNull() | F.isnan(number) | (F.abs(number) == float("inf"))
        if variable == "rainfall":
            invalid = invalid | (number < 0)
        status = F.when(missing, "missing").when(invalid, "invalid").otherwise("valid")
        raw = raw.withColumn(f"{variable}_status", status)
        raw = raw.withColumn("temperature_c" if variable == "temperature" else "rainfall_mm",
                             F.when(status == "valid", number).cast("double"))
    calendar = spark.range(1).select(F.explode(F.sequence(F.lit(start), F.lit(end))).alias("date"))
    provinces = spark.createDataFrame([(p,) for p in province_ids], "province_id int")
    result = provinces.crossJoin(calendar).join(raw, ["province_id", "date"], "left")
    status = (F.when(F.col("date_raw").isNull(), "missing_date")
              .when((F.col("temperature_status") == "invalid") | (F.col("rainfall_status") == "invalid"), "invalid")
              .when((F.col("temperature_status") == "missing") | (F.col("rainfall_status") == "missing"), "missing")
              .otherwise("complete"))
    return result.select("province_id", "date", F.year("date").alias("year"), F.month("date").alias("month"),
                         "temperature_c", "rainfall_mm", status.alias("data_status"))


def aggregate_weather_period(daily, config, monthly):
    keys = ["province_id", "year"] + (["month"] if monthly else [])
    result = daily.groupBy(*keys).agg(F.avg("temperature_c").alias("temperature_mean"),
        F.sum("rainfall_mm").alias("rainfall_sum"), F.count("temperature_c").alias("valid_temperature_days"),
        F.count("rainfall_mm").alias("valid_rainfall_days"), F.count("date").alias("observed_days"))
    if monthly:
        expected = F.dayofmonth(F.last_day(F.make_date("year", "month", F.lit(1))))
    else:
        expected = F.datediff(F.make_date(F.col("year") + 1, F.lit(1), F.lit(1)), F.make_date("year", F.lit(1), F.lit(1)))
    result = result.withColumn("expected_days", expected)
    temperature_ok = F.col("valid_temperature_days") / F.col("expected_days") >= config["temperature_min_fraction"]
    rainfall_ok = F.col("valid_rainfall_days") / F.col("expected_days") >= config["rainfall_min_fraction"]
    status = F.when((F.col("valid_temperature_days") == F.col("expected_days")) &
                    (F.col("valid_rainfall_days") == F.col("expected_days")), "complete").otherwise("incomplete")
    return result.select(*keys, F.when(temperature_ok, F.col("temperature_mean")).alias("avg_temperature_c"),
        F.when(rainfall_ok, F.col("rainfall_sum")).alias("total_rainfall_mm" if monthly else "annual_rainfall_mm"),
        "valid_temperature_days", "valid_rainfall_days", "expected_days", status.alias("data_status"))


def add_weather_anomalies(annual, config):
    baseline = annual.filter(F.col("year").between(config["baseline_start"], config["baseline_end"]))
    baseline = baseline.groupBy("province_id").agg(
        F.avg("avg_temperature_c").alias("baseline_temperature_c"),
        F.avg("annual_rainfall_mm").alias("baseline_rainfall_mm"),
        F.count("avg_temperature_c").alias("baseline_temperature_years"),
        F.count("annual_rainfall_mm").alias("baseline_rainfall_years"))
    result = annual.join(baseline, "province_id", "left")
    enough_temperature = F.col("baseline_temperature_years") >= config["baseline_min_years"]
    enough_rain = (F.col("baseline_rainfall_years") >= config["baseline_min_years"]) & (F.col("baseline_rainfall_mm") > 0)
    return result.withColumn("temperature_anomaly_c", F.when(enough_temperature,
        F.col("avg_temperature_c") - F.col("baseline_temperature_c"))).withColumn("rainfall_anomaly_pct", F.when(enough_rain,
        (F.col("annual_rainfall_mm") - F.col("baseline_rainfall_mm")) / F.col("baseline_rainfall_mm") * 100))
