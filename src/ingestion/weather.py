"""Validated, resumable NASA POWER daily point acquisition."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import threading
import time

import requests

ENDPOINT = "https://power.larc.nasa.gov/api/temporal/daily/point"
UNITS = {"T2M": "C", "PRECTOTCORR": "mm/day"}


def atomic_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def dates_between(start, end):
    return [start + timedelta(days=n) for n in range((end - start).days + 1)]


def validate_payload(payload, params):
    """Validate structure, units, location and exact date keys before cache reuse."""
    header = payload["header"]
    if header["time_standard"] != "LST":
        raise ValueError("NASA returned a different time standard")
    if str(header["start"]) != params["start"] or str(header["end"]) != params["end"]:
        raise ValueError("NASA returned a different date interval")
    fill = header["fill_value"]
    if isinstance(fill, bool) or not isinstance(fill, (float, int)) or not math.isfinite(fill):
        raise ValueError("Invalid NASA fill_value")
    coordinates = payload["geometry"]["coordinates"]
    if abs(coordinates[0] - params["longitude"]) > 0.001 or abs(coordinates[1] - params["latitude"]) > 0.001:
        raise ValueError("Response location does not match requested point")
    expected = {d.strftime("%Y%m%d") for d in dates_between(
        datetime.strptime(params["start"], "%Y%m%d").date(),
        datetime.strptime(params["end"], "%Y%m%d").date())}
    for parameter in UNITS:
        if payload["parameters"][parameter]["units"] != UNITS[parameter]:
            raise ValueError(f"Unexpected units for {parameter}")
        values = payload["properties"]["parameter"][parameter]
        if set(values) != expected:
            raise ValueError(f"Missing/extra date keys for {parameter}")
        for value in values.values():
            if isinstance(value, bool) or not isinstance(value, (int, float, str, type(None))):
                raise ValueError(f"Unsupported daily measurement {value!r}")
    return len(expected)


def plan_requests(provinces, start, end):
    """Deduplicate exact coordinates only; no unverified grid rounding."""
    groups = {}
    for province in provinces:
        for year in range(start.year, end.year + 1):
            first, last = max(start, date(year, 1, 1)), min(end, date(year, 12, 31))
            params = dict(community="AG", parameters="T2M,PRECTOTCORR", format="JSON",
                          **{"time-standard": "LST"}, latitude=province["latitude"], longitude=province["longitude"],
                          start=first.strftime("%Y%m%d"), end=last.strftime("%Y%m%d"))
            key = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()
            item = groups.setdefault(key, {"key": key, "params": params, "provinces": []})
            item["provinces"].append(province)
    return list(groups.values())


class Downloader:
    def __init__(self, config, raw_dir, session_factory=requests.Session, sleep=time.sleep):
        self.config, self.raw_dir = config, raw_dir
        self.session_factory, self.sleep = session_factory, sleep
        self.local = threading.local()
        self.sessions = []
        self.lock = threading.Lock()
        self.last_request = 0.0

    def close(self):
        for session in self.sessions:
            session.close()

    def fetch(self, item):
        path = self.raw_dir / f"{item['key']}.json"
        result = {"request_key": item["key"], "request": item["params"],
                  "provinces": item["provinces"], "filepath": path.as_posix(), "throttled": False}
        if path.is_file():
            try:
                content = path.read_bytes()
                payload = json.loads(content)
                count = validate_payload(payload, item["params"])
                return {**result, "status": "cached", "record_count": count,
                        "sha256": hashlib.sha256(content).hexdigest(), "location": payload["geometry"],
                        "source_header": payload["header"], "download_timestamp": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()}
            except (ValueError, KeyError, TypeError, OSError):
                pass  # An invalid cache entry is downloaded again, never skipped.
        if not hasattr(self.local, "session"):
            self.local.session = self.session_factory()
            with self.lock:
                self.sessions.append(self.local.session)
        last_error = None
        for attempt in range(self.config["retries"] + 1):
            try:
                with self.lock:
                    pause = self.config["request_interval_seconds"] - (time.monotonic() - self.last_request)
                    if pause > 0:
                        self.sleep(pause)
                    self.last_request = time.monotonic()
                response = self.local.session.get(ENDPOINT, params=item["params"], timeout=self.config["timeout_seconds"])
                if response.status_code == 429:
                    result["throttled"] = True
                if response.status_code == 429 or response.status_code >= 500:
                    retry_after = response.headers.get("Retry-After", "0")
                    self.sleep(max(float(retry_after) if retry_after.isdigit() else 0,
                                   self.config["backoff_seconds"] * 2 ** attempt))
                    raise requests.ConnectionError(f"Temporary HTTP {response.status_code}")
                response.raise_for_status()
                payload = response.json()
                count = validate_payload(payload, item["params"])
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary = path.with_suffix(".json.tmp")
                temporary.write_bytes(response.content)
                temporary.replace(path)
                return {**result, "status": "downloaded", "record_count": count,
                        "download_timestamp": datetime.now(timezone.utc).isoformat(),
                        "sha256": hashlib.sha256(response.content).hexdigest(),
                        "location": payload["geometry"], "source_header": payload["header"]}
            except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                if isinstance(exc, requests.HTTPError) and response.status_code < 500 and response.status_code != 429:
                    break
                if attempt < self.config["retries"]:
                    self.sleep(self.config["backoff_seconds"] * 2 ** attempt)
        return {**result, "status": "failed", "error": last_error,
                "download_timestamp": datetime.now(timezone.utc).isoformat(), "record_count": 0}


def collect(plan, config, raw_dir, manifest_path, context):
    # Preserve historical entries for resume and future processing windows.
    previous = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    entries = {entry["request_key"]: entry for entry in previous.get("requests", [])}
    downloader = Downloader(config, raw_dir)
    selected, concurrency = [], config["request_concurrency"]
    try:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            offset = 0
            while offset < len(plan):
                batch = plan[offset:offset + concurrency]
                results = list(pool.map(downloader.fetch, batch))
                for result in results:
                    entries[result["request_key"]] = result
                    selected.append(result)
                    atomic_json(manifest_path, {**context, "requests": list(entries.values())})
                if any(r["throttled"] for r in results):
                    concurrency = 1
                offset += len(batch)
    finally:
        downloader.close()
    return selected


def parse_records(entry):
    payload = json.loads(Path(entry["filepath"]).read_bytes())
    validate_payload(payload, entry["request"])
    variables = payload["properties"]["parameter"]
    rows = []
    for province in entry["provinces"]:
        for day in sorted(variables["T2M"]):
            rows.append((province["province_id"], day,
                         None if variables["T2M"][day] is None else str(variables["T2M"][day]),
                         None if variables["PRECTOTCORR"][day] is None else str(variables["PRECTOTCORR"][day]),
                         float(payload["header"]["fill_value"])))
    return rows
