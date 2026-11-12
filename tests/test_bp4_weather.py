"""Offline fixtures and focused Spark checks for BP4 weather ingestion."""

from datetime import date
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.ingestion.weather import Downloader, dates_between, parse_records, plan_requests, validate_payload
from src.bp4.pipeline import ROOT, create_spark, province_reference, read_configuration, run
from src.common.cleaning import add_weather_anomalies, aggregate_weather_period, clean_weather_daily


def fixture(start=date(2020, 2, 1), end=date(2020, 2, 29)):
    days = {d.strftime("%Y%m%d"): 2.0 for d in dates_between(start, end)}
    return {"geometry": {"type": "Point", "coordinates": [105.215, 20.0917]},
            "header": {"fill_value": -999, "time_standard": "LST",
                       "start": start.strftime("%Y%m%d"), "end": end.strftime("%Y%m%d")},
            "parameters": {"T2M": {"units": "C"}, "PRECTOTCORR": {"units": "mm/day"}},
            "properties": {"parameter": {"T2M": days.copy(), "PRECTOTCORR": days.copy()}}}


def province():
    return {"province_id": 26, "latitude": 20.0917, "longitude": 105.215}


class AcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.config = read_configuration(ROOT / "configs/bp4_weather.json")
        self.config.update(retries=1, backoff_seconds=0, request_interval_seconds=0)
        self.item = plan_requests([province()], date(2020, 2, 1), date(2020, 2, 29))[0]

    def test_parser_and_units(self):
        payload = fixture()
        self.assertEqual(validate_payload(payload, self.item["params"]), 29)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "raw.json"
            path.write_text(json.dumps(payload))
            rows = parse_records({"filepath": str(path), "request": self.item["params"], "provinces": [province()]})
            self.assertEqual(len(rows), 29)
            self.assertEqual(rows[-1][:2], (26, "20200229"))
        payload["parameters"]["PRECTOTCORR"]["units"] = "mm/month"
        with self.assertRaisesRegex(ValueError, "units"):
            validate_payload(payload, self.item["params"])

    def test_date_coverage(self):
        payload = fixture()
        del payload["properties"]["parameter"]["T2M"]["20200229"]
        with self.assertRaisesRegex(ValueError, "date keys"):
            validate_payload(payload, self.item["params"])
        payload = fixture()
        payload["properties"]["parameter"]["T2M"]["20200230"] = 1
        with self.assertRaises(ValueError):
            validate_payload(payload, self.item["params"])

    def test_idempotent_cache_and_repair(self):
        response = Mock(status_code=200, headers={})
        response.json.return_value = fixture()
        response.content = json.dumps(fixture()).encode()
        session = Mock()
        session.get.return_value = response
        with tempfile.TemporaryDirectory() as folder:
            downloader = Downloader(self.config, Path(folder), session_factory=lambda: session, sleep=lambda _: None)
            self.assertEqual(downloader.fetch(self.item)["status"], "downloaded")
            self.assertEqual(downloader.fetch(self.item)["status"], "cached")
            self.assertEqual(session.get.call_count, 1)
            (Path(folder) / f"{self.item['key']}.json").write_text('{}')
            self.assertEqual(downloader.fetch(self.item)["status"], "downloaded")
            self.assertEqual(session.get.call_count, 2)
            downloader.close()

    def test_throttling_retry(self):
        throttled = Mock(status_code=429, headers={"Retry-After": "0"})
        success = Mock(status_code=200, headers={}, content=json.dumps(fixture()).encode())
        success.json.return_value = fixture()
        session = Mock()
        session.get.side_effect = [throttled, success]
        with tempfile.TemporaryDirectory() as folder:
            downloader = Downloader(self.config, Path(folder), session_factory=lambda: session, sleep=lambda _: None)
            result = downloader.fetch(self.item)
            self.assertEqual(result["status"], "downloaded")
            self.assertTrue(result["throttled"])
            self.assertEqual(session.get.call_count, 2)
            downloader.close()

    def test_exact_location_deduplication_and_year_chunks(self):
        other = {**province(), "province_id": 57}
        plan = plan_requests([province(), other], date(2022, 1, 1), date(2023, 12, 31))
        self.assertEqual(len(plan), 2)
        self.assertEqual(len(plan[0]["provinces"]), 2)

    def test_coordinate_mapping(self):
        provinces, _ = province_reference(self.config)
        self.assertEqual(len(provinces), 63)
        self.assertEqual([p["province_id"] for p in provinces], list(range(1, 64)))
        self.assertEqual([p["province_name"] for p in provinces if p["province_id"] in [26, 41, 57]],
                         ["Thanh Hóa", "Gia Lai", "An Giang"])
        self.assertEqual(len({p["source_feature_id"] for p in provinces}), 63)

    def test_collection_period_2010_2024(self):
        self.assertEqual(self.config["start"], "2010-01-01")
        self.assertEqual(self.config["end"], "2024-12-31")
        with patch("sys.argv", ["ingest_weather.py", "dry-run", "--start", "2009-01-01"]):
            with self.assertRaisesRegex(ValueError, "2010-01-01"):
                run()

    def test_full_requires_passed_pilot(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch("src.bp4.pipeline.ROOT", Path(folder)), \
                 patch("src.bp4.pipeline.read_configuration", return_value=self.config), \
                 patch("src.bp4.pipeline.province_reference", return_value=([province()], {})), \
                 patch("sys.argv", ["ingest_weather.py", "full"]):
                with self.assertRaisesRegex(ValueError, "pilot"):
                    run()


class ProcessingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark = create_spark()
        cls.config = read_configuration(ROOT / "configs/bp4_weather.json")

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def daily(self, start, end, change=None):
        rows = [(26, d.strftime("%Y%m%d"), "20", "2", -999.0) for d in dates_between(start, end)]
        if change:
            rows = change(rows)
        return clean_weather_daily(self.spark, rows, [26], start, end)

    def test_missing_and_invalid_measurements(self):
        rows = [(26, "20200201", "-999", "-999", -999.0),
                (26, "20200202", "broken", "-1", -999.0)]
        daily = clean_weather_daily(self.spark, rows, [26], date(2020, 2, 1), date(2020, 2, 3)).orderBy("date").collect()
        self.assertEqual([r.data_status for r in daily], ["missing", "invalid", "missing_date"])
        self.assertTrue(all(r.rainfall_mm is None for r in daily))
        self.assertTrue(all(r.temperature_c is None for r in daily))

    def test_duplicate_and_bad_date_detection(self):
        row = (26, "20200201", "20", "2", -999.0)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            clean_weather_daily(self.spark, [row, row], [26], date(2020, 2, 1), date(2020, 2, 1))
        with self.assertRaisesRegex(ValueError, "Invalid daily date"):
            clean_weather_daily(self.spark, [(26, "20200230", "20", "2", -999.0)], [26], date(2020, 2, 1), date(2020, 2, 29))

    def test_monthly_leap_year(self):
        daily = self.daily(date(2020, 2, 1), date(2020, 2, 29))
        result = aggregate_weather_period(daily, self.config, True).first()
        self.assertEqual(result.expected_days, 29)
        self.assertEqual(result.valid_temperature_days, 29)
        self.assertEqual(result.avg_temperature_c, 20)
        self.assertEqual(result.total_rainfall_mm, 58)
        self.assertEqual(result.data_status, "complete")

    def test_incomplete_month_rainfall_null(self):
        daily = self.daily(date(2020, 2, 1), date(2020, 2, 29), lambda rows: rows[:-1])
        result = aggregate_weather_period(daily, self.config, True).first()
        self.assertEqual(result.valid_rainfall_days, 28)
        self.assertIsNone(result.total_rainfall_mm)
        self.assertEqual(result.data_status, "incomplete")
        self.assertEqual(result.avg_temperature_c, 20)

    def test_annual_mean_sum_and_leap_year(self):
        daily = self.daily(date(2020, 1, 1), date(2020, 12, 31))
        result = aggregate_weather_period(daily, self.config, False).first()
        self.assertEqual(result.expected_days, 366)
        self.assertEqual(result.annual_rainfall_mm, 732)
        self.assertEqual(result.avg_temperature_c, 20)

    def test_partial_year(self):
        daily = self.daily(date(2021, 1, 1), date(2021, 2, 1))
        result = aggregate_weather_period(daily, self.config, False).first()
        self.assertEqual(result.expected_days, 365)
        self.assertIsNone(result.annual_rainfall_mm)
        self.assertIsNone(result.avg_temperature_c)

    def test_baseline_and_anomalies(self):
        rows = [(26, 1991, 20.0, 1000.0), (26, 1992, 22.0, 1200.0), (26, 2022, 23.0, 1210.0),
                (57, 2022, 23.0, 1000.0), (41, 1991, 20.0, 0.0), (41, 1992, 22.0, 0.0), (41, 2022, 23.0, 10.0)]
        annual = self.spark.createDataFrame(rows, "province_id int, year int, avg_temperature_c double, annual_rainfall_mm double")
        result = add_weather_anomalies(annual, {**self.config, "baseline_min_years": 2}).filter("year=2022")
        result = {r.province_id: r for r in result.collect()}
        self.assertEqual(result[26].temperature_anomaly_c, 2)
        self.assertAlmostEqual(result[26].rainfall_anomaly_pct, 10)
        self.assertIsNone(result[57].temperature_anomaly_c)
        self.assertIsNone(result[57].rainfall_anomaly_pct)
        self.assertIsNone(result[41].rainfall_anomaly_pct)


if __name__ == "__main__":
    unittest.main()
