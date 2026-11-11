"""Build the shared agricultural Parquet panel, independently of BP analytics."""

import argparse
import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
LOG = logging.getLogger("agriculture_etl")


def configure_spark_environment():
    """Check the JVM before Spark starts and resolve the pip distribution directly."""
    import pyspark

    # A project-local ZIP installation needs no administrator rights and does
    # not change the Java used by other applications or terminal sessions.
    local_jvms = sorted((ROOT / ".venv" / "java").glob("*/bin/java.exe")) if os.name == "nt" else []
    if len(local_jvms) > 1:
        raise ValueError("Multiple project-local JDKs found under .venv/java; keep one JDK 17 or 21 there.")
    if local_jvms:
        os.environ["JAVA_HOME"] = str(local_jvms[0].parent.parent)
    java_home = os.environ.get("JAVA_HOME")
    java = str(Path(java_home) / "bin" / ("java.exe" if os.name == "nt" else "java")) if java_home else shutil.which("java")
    if not java or not Path(java).is_file():
        raise ValueError("Java was not found. Install JDK 17 or 21 and set JAVA_HOME to its root directory (not bin).")
    version = subprocess.run([java, "-version"], capture_output=True, text=True, timeout=15)
    description = version.stderr + version.stdout
    match = re.search(r'version "(\d+)', description)
    if version.returncode or not match:
        raise ValueError(f"Cannot determine Java version using {java}: {description.strip()}")
    major = int(match.group(1))
    if major not in {17, 21}:
        raise ValueError(f"Java {major} is selected at {java}. Spark 4.0 requires Java 17 or 21. "
                         "Install one of these JDKs, set JAVA_HOME to its root directory, and rerun. "
                         "Activating the Python environment does not change Java.")
    # Avoid find-spark-home.cmd attempting to execute an unquoted Python path.
    os.environ.setdefault("SPARK_HOME", str(Path(pyspark.__file__).resolve().parent))
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)
    LOG.info("Java %s: %s", major, java)
    return {"java_major": major, "java_executable": java, "pyspark_version": pyspark.__version__}


def write_report(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def name_parquet_part(spark, directory):
    """Give the single local part a stable name, moving its checksum with it."""
    parts = sorted(directory.glob("part-*.parquet"))
    if len(parts) != 1:
        raise ValueError(f"Expected one generated Parquet part in {directory}; found {len(parts)}")
    target = directory / "rice_province_year.parquet"
    if target.exists():
        raise ValueError(f"Unexpected existing output file after Spark overwrite: {target}")
    jpath = spark._jvm.org.apache.hadoop.fs.Path
    # Hadoop Path(String) expects an unescaped path, including literal spaces.
    source = jpath(parts[0].as_posix())
    filesystem = source.getFileSystem(spark.sparkContext._jsc.hadoopConfiguration())
    # ChecksumFileSystem.rename also moves the associated .crc sidecar.
    if not filesystem.rename(source, jpath(target.as_posix())):
        raise ValueError(f"Cannot rename generated Parquet part to {target}")
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unit-evidence", default="Data owner confirmed on 2026-11-11: V06.13 thousand hectares; V06.14 quintals/hectare; V06.15 thousand tons.",
                        help="Source-unit confirmation retained in the quality report; defaults to the data owner's confirmation on 2026-11-11.")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    output = ROOT / "data/processed/agriculture"
    report = {"status": "failed", "sources": [], "unit_evidence": args.unit_evidence,
              "output": "data/processed/agriculture/rice_province_year/"}
    spark = None
    try:
        from src.ingestion.agriculture import extract_workbooks, to_spark

        LOG.info("Extracting and inspecting the three local NSO workbooks")
        records, report["sources"] = extract_workbooks(ROOT)
        if not args.unit_evidence or not args.unit_evidence.strip():
            raise ValueError("The workbooks contain NO unit declarations. Confirm V06.13=thousand ha, "
                             "V06.14=quintals/ha, V06.15=thousand tons against the source, then rerun "
                             "with --unit-evidence 'source citation or data-owner confirmation'. No conversion was applied.")
        from pyspark.sql import SparkSession
        from src.common.cleaning import clean_observations, combine_observations
        from src.common.provinces import load_reference
        from src.common.validation import quality_report, sample, validate_source_keys

        report["runtime"] = configure_spark_environment()
        LOG.info("Starting Spark in local[2] mode")
        builder = (SparkSession.builder.master("local[2]").appName("AgricultureRawToProcessed")
                 .config("spark.sql.shuffle.partitions", "2").config("spark.ui.enabled", "false")
                 .config("spark.sql.session.timeZone", "UTC"))
        adapter = ROOT / ".venv/spark-jars/hadoop-bare-naked-local-fs-0.1.0.jar"
        if os.name == "nt" and adapter.is_file():
            # Pure Java local I/O avoids requiring native Hadoop Windows tools.
            # local[2] executes in the driver JVM. Avoid spark.jars here: its
            # dependency-copy step itself invokes the missing Windows chmod tool.
            builder = (builder.config("spark.driver.extraClassPath", str(adapter))
                       .config("spark.hadoop.fs.file.impl", "com.globalmentor.apache.hadoop.fs.BareLocalFileSystem")
                       .config("spark.hadoop.fs.file.impl.disable.cache", "true"))
            report["runtime"]["local_filesystem_adapter"] = adapter.name
        spark = builder.getOrCreate()
        spark.sparkContext.setLogLevel("WARN")
        reference, report["reference"] = load_reference(spark, ROOT / "data/vietnam_regions_provinces.json")
        cleaned = clean_observations(to_spark(spark, records)).cache()
        totals = cleaned.filter("is_aggregate")
        report["excluded_aggregate_observations"] = totals.count()
        report["excluded_aggregate_rows"] = sample(totals.select("source_file", "source_province_name").distinct(),
                                                   ["source_file", "source_province_name"], 100)
        observations = cleaned.filter("not is_aggregate").cache()
        LOG.info("Validating source keys before joining measurements")
        validate_source_keys(observations)
        panel = combine_observations(observations, reference).cache()
        report["quality"] = quality_report(panel, observations, reference)
        report["sample_records"] = sample(panel, panel.columns, 5)
        LOG.info("Writing validated panel to %s", output / "rice_province_year")
        panel.coalesce(1).sortWithinPartitions("province_name", "year").write.mode("overwrite").parquet(
            str(output / "rice_province_year"))
        parquet_file = name_parquet_part(spark, output / "rice_province_year")
        report["parquet_file"] = parquet_file.relative_to(ROOT).as_posix()
        saved = spark.read.parquet(str(parquet_file))
        if saved.count() != report["quality"]["record_count"] or saved.dtypes != panel.dtypes:
            raise ValueError("Parquet read-back schema/count differs from validated output")
        saved.printSchema()
        saved.orderBy("province_name", "year").show(5, truncate=False)
        report["status"] = "completed"
        q = report["quality"]
        LOG.info("Completed: %s records, years %s–%s, %s provinces, %s regions", q["record_count"],
                 q["year_min"], q["year_max"], q["province_count"], q["region_count"])
        LOG.info("Quality: %s duplicate keys, %s missing measurements, %s unmatched observations, "
                 "%s invalid numbers, %s consistency warnings", q["duplicate_province_year_count"],
                 sum(q["missing_values"][c] for c in ("rice_area_ha", "rice_yield_ton_ha", "rice_production_ton")),
                 q["unmatched_observation_count"], q["invalid_numeric_count"], q["consistency"]["warning_count"])
        for warning in q["warnings"]:
            LOG.warning(warning)
        return 0
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        report["output_note"] = "This run did not complete. Any existing Parquet must not be attributed to this run."
        LOG.error("ETL failed: %s", report["error"])
        if isinstance(exc, ModuleNotFoundError):
            LOG.error("Install project dependencies with this interpreter: %s -m pip install -r requirements.txt", sys.executable)
        if "getSubject is not supported" in str(exc):
            report["required_fix"] = "Use JDK 17 or 21, set JAVA_HOME to its installation directory, and rerun this entry point. The current JVM cannot run Hadoop UserGroupInformation."
            LOG.error(report["required_fix"])
        return 1
    finally:
        try:
            if spark is not None:
                spark.stop()
        finally:
            write_report(output / "quality_report.json", report)


if __name__ == "__main__":
    sys.exit(main())
