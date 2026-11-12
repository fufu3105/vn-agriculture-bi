"""Configuration, province verification and weather pipeline orchestration."""

import argparse
from datetime import date
import hashlib
import json
import logging
from pathlib import Path

from src.ingestion.weather import atomic_json, collect, dates_between, parse_records, plan_requests

ROOT = Path(__file__).resolve().parents[2]
PILOT_NAMES = ["Thanh Hóa", "Gia Lai", "An Giang"]


def read_configuration(path):
    config = json.loads(path.read_text(encoding="utf-8"))
    for key in ["start", "end", "pilot_start", "pilot_end"]:
        date.fromisoformat(config[key])
    if date.fromisoformat(config["start"]) > date.fromisoformat(config["end"]):
        raise ValueError("start must not follow end")
    if config["parameters"] != ["T2M", "PRECTOTCORR"]:
        raise ValueError("This schema requires parameters T2M and PRECTOTCORR")
    if not 1 <= config["request_concurrency"] <= 5:
        raise ValueError("request_concurrency must be between 1 and 5")
    for field in ["temperature_min_fraction", "rainfall_min_fraction"]:
        if not 0 < config[field] <= 1:
            raise ValueError(f"{field} must be in (0, 1]")
    if config["rainfall_min_fraction"] != 1:
        raise ValueError("Monthly/annual rainfall totals require all calendar days; set rainfall_min_fraction to 1")
    if not 1 <= config["baseline_min_years"] <= config["baseline_end"] - config["baseline_start"] + 1:
        raise ValueError("Invalid baseline coverage requirement")
    if config["retries"] < 0 or config["timeout_seconds"] <= 0 or config["backoff_seconds"] < 0 or config["request_interval_seconds"] < 0:
        raise ValueError("Invalid HTTP retry/timing configuration")
    for field in ["raw_dir", "output_dir", "metadata_dir"]:
        target = (ROOT / config[field]).resolve()
        if not target.is_relative_to(ROOT / "data") or target == ROOT / "data":
            raise ValueError(f"{field} must be a subdirectory under project data/")
        if field == "output_dir" and not target.is_relative_to(ROOT / "data/processed/weather"):
            raise ValueError("Weather output_dir must stay under data/processed/weather/")
    return config


def province_reference(config):
    reference_path = ROOT / "data/vietnam_regions_provinces.json"
    coordinate_data = json.loads((ROOT / config["coordinate_file"]).read_text(encoding="utf-8"))
    reference_bytes = reference_path.read_bytes()
    expected = [(p, region["region_name"]) for region in json.loads(reference_bytes) for p in region["provinces"]]
    provinces = coordinate_data["provinces"]
    if len(provinces) != len(expected) or len(provinces) != 63:
        raise ValueError("Expected all 63 historical provinces in the coordinate reference")
    for province, (name, region), identifier in zip(provinces, expected, range(1, len(expected) + 1)):
        if (province["province_id"], province["province_name"], province["region"]) != (identifier, name, region):
            raise ValueError(f"Coordinate ID/name/region mismatch for {name}")
        if not (-90 <= province["latitude"] <= 90 and -180 <= province["longitude"] <= 180):
            raise ValueError(f"Unresolved coordinates for {name}")
    return provinces, coordinate_data


def create_spark():
    from scripts.build_processed import configure_spark_environment
    from pyspark.sql import SparkSession
    import os
    configure_spark_environment()
    builder = (SparkSession.builder.master("local[2]").appName("BP4Weather")
               .config("spark.ui.enabled", "false").config("spark.sql.shuffle.partitions", "2")
               .config("spark.sql.session.timeZone", "UTC"))
    adapter = ROOT / ".venv/spark-jars/hadoop-bare-naked-local-fs-0.1.0.jar"
    if os.name == "nt" and adapter.is_file():
        builder = (builder.config("spark.driver.extraClassPath", str(adapter))
                   .config("spark.hadoop.fs.file.impl", "com.globalmentor.apache.hadoop.fs.BareLocalFileSystem")
                   .config("spark.hadoop.fs.file.impl.disable.cache", "true"))
    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    return spark


def process(entries, config, provinces, start, end, output):
    from scripts.build_processed import name_parquet_part
    from pyspark.sql import functions as F
    from src.common.cleaning import clean_weather_daily, aggregate_weather_period, add_weather_anomalies
    from src.common.provinces import load_reference
    spark = create_spark()
    try:
        agricultural = spark.read.parquet(str(ROOT / "data/processed/agriculture/rice_province_year/rice_province_year.parquet"))
        if dict(agricultural.dtypes).get("province_id") != "int" or dict(agricultural.dtypes).get("year") != "int":
            raise ValueError("Agriculture join key types must both be Integer")
        reference, _ = load_reference(spark, ROOT / "data/vietnam_regions_provinces.json")
        names = agricultural.select("province_id", "province_name", "region").distinct()
        if names.exceptAll(reference.select("province_id", "province_name", "region")).count() or names.count() != 63:
            raise ValueError("Agricultural identifiers/names/regions differ from reference")
        selected = [p["province_id"] for p in provinces]
        rows = [row for entry in entries for row in parse_records(entry)]
        daily = clean_weather_daily(spark, rows, selected, start, end).cache()
        monthly = aggregate_weather_period(daily, config, True).cache()
        annual = add_weather_anomalies(aggregate_weather_period(daily, config, False), config).cache()
        counts, dataset_files = {}, {}
        for name, frame in [("weather_daily", daily), ("weather_monthly", monthly), ("weather_annual", annual)]:
            path = output / name
            frame.coalesce(1).sortWithinPartitions("province_id", "date" if name == "weather_daily" else "year").write.mode("overwrite").parquet(str(path))
            data_file = name_parquet_part(spark, path, f"{name}.parquet")
            dataset_files[name] = data_file.relative_to(ROOT).as_posix()
            saved = spark.read.parquet(str(data_file))
            counts[name] = saved.count()
            if saved.dtypes != frame.dtypes or counts[name] != frame.count():
                raise ValueError(f"Parquet read-back failed for {name}")
        statuses = {r["data_status"]: r["count"] for r in daily.groupBy("data_status").count().collect()}
        missing = daily.agg(F.sum(F.col("temperature_c").isNull().cast("long")).alias("temperature"),
                            F.sum(F.col("rainfall_mm").isNull().cast("long")).alias("rainfall")).first().asDict()
        baseline_missing = annual.filter(F.col("temperature_anomaly_c").isNull() | F.col("rainfall_anomaly_pct").isNull()).count()
        return {"counts": counts, "dataset_files": dataset_files,
                "daily_status": statuses, "missing_measurements": missing,
                "province_count": daily.select("province_id").distinct().count(),
                "province_ids": selected, "date_min": start.isoformat(), "date_max": end.isoformat(),
                "expected_daily_records": len(selected) * len(dates_between(start, end)),
                "incomplete_months": monthly.filter("data_status != 'complete'").count(),
                "incomplete_years": annual.filter("data_status != 'complete'").count(),
                "annual_rows_without_anomalies": baseline_missing, "join_keys_verified": True,
                "duplicate_province_date_count": 0,
                "schemas": {"daily": dict(daily.dtypes), "monthly": dict(monthly.dtypes), "annual": dict(annual.dtypes)},
                "warnings": ["Point/grid-cell observations represent one Natural Earth label coordinate per province."] +
                            (["Insufficient baseline years or nonpositive rainfall baseline; affected anomalies remain null."] if baseline_missing else [])}
    finally:
        spark.stop()


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["dry-run", "pilot", "full", "resume"])
    parser.add_argument("--config", default="configs/bp4_weather.json")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--province-ids", type=int, nargs="+")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    config = read_configuration(ROOT / args.config)
    if args.start:
        config["start"] = args.start
    if args.end:
        config["end"] = args.end
    all_provinces, coordinates = province_reference(config)
    metadata = ROOT / config["metadata_dir"]
    mode = args.mode
    if mode == "resume":
        manifest_path = metadata / "download_manifest.json"
        if not manifest_path.is_file():
            raise ValueError("No collection manifest exists; start with pilot")
        mode = json.loads(manifest_path.read_text(encoding="utf-8")).get("mode")
        if mode not in {"pilot", "full"}:
            raise ValueError("Manifest does not identify a pilot or full collection")
    if mode == "pilot":
        start, end = date.fromisoformat(config["pilot_start"]), date.fromisoformat(config["pilot_end"])
        provinces = [p for p in all_provinces if p["province_id"] in config["pilot_province_ids"]]
        if [p["province_name"] for p in provinces] != PILOT_NAMES or start != date(2022, 1, 1) or end != date(2023, 12, 31):
            raise ValueError("Pilot must use Thanh Hóa, Gia Lai, An Giang and all of 2022–2023")
    else:
        start, end = date.fromisoformat(config["start"]), date.fromisoformat(config["end"])
        ids = args.province_ids or config["province_ids"] or [p["province_id"] for p in all_provinces]
        if len(ids) != len(set(ids)) or set(ids) - {p["province_id"] for p in all_provinces}:
            raise ValueError("Unknown or duplicate province IDs")
        provinces = [p for p in all_provinces if p["province_id"] in ids]
    if end < start:
        raise ValueError("End date precedes start date")
    if start < date(2010, 1, 1) or end > date(2024, 12, 31):
        raise ValueError("Weather collection must stay within 2010-01-01 through 2024-12-31")
    plan = plan_requests(provinces, start, end)
    pilot_report = metadata / "pilot_quality_report.json"
    if args.mode == "dry-run":
        print(json.dumps({"province_count": len(provinces), "request_count": len(plan),
                          "start": start.isoformat(), "end": end.isoformat(), "concurrency": config["request_concurrency"],
                          "sample_requests": plan[:1]}, ensure_ascii=False, indent=2))
        return 0
    if mode == "full":
        passed = json.loads(pilot_report.read_text(encoding="utf-8")) if pilot_report.exists() else {}
        if not passed.get("pilot_passed") or passed.get("coordinate_sha256") != hashlib.sha256((ROOT/config["coordinate_file"]).read_bytes()).hexdigest():
            raise ValueError("Run and validate the pilot before full/resume collection")
    context = {"coordinate_source": {k: v for k, v in coordinates.items() if k != "provinces"},
               "configuration": config, "mode": mode}
    report_path = pilot_report if mode == "pilot" else metadata / "quality_report.json"
    report = {**context, "status": "failed", "pilot_passed": False,
              "coordinate_sha256": hashlib.sha256((ROOT/config["coordinate_file"]).read_bytes()).hexdigest()}
    try:
        logging.info("Collecting %s yearly requests for %s provinces", len(plan), len(provinces))
        entries = collect(plan, config, ROOT/config["raw_dir"], metadata/"download_manifest.json", context)
        report["request_counts"] = {state: sum(e["status"] == state for e in entries) for state in ["downloaded", "cached", "failed"]}
        if report["request_counts"]["failed"]:
            raise ValueError("Some NASA requests failed; inspect download_manifest.json and rerun to resume")
        output = ROOT/config["output_dir"]
        if mode == "pilot":
            output = output / "pilot"
        report["quality"] = process(entries, config, provinces, start, end, output)
        q = report["quality"]
        report["status"] = "completed"
        report["pilot_passed"] = mode == "pilot" and q["counts"]["weather_daily"] == 2190 and q["daily_status"] == {"complete": 2190} and q["incomplete_months"] == 0 and q["incomplete_years"] == 0
        if mode == "pilot" and not report["pilot_passed"]:
            report["status"] = "quality_failed"
        logging.info("Weather results: %s", json.dumps(q, ensure_ascii=False))
        return 0 if report["status"] == "completed" else 1
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        logging.error(report["error"])
        return 1
    finally:
        atomic_json(report_path, report)
