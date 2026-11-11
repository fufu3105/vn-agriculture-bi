"""Match historical province labels to the supplied seven-region reference."""

import hashlib
import json
import unicodedata

from pyspark.sql import functions as F


def province_key(column):
    """Accent/case/spacing normalization, without merging administrative units."""
    accented = "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ"
    plain =    "aaaaaaaaaaaaaaaaaeeeeeeeeeeeiiiiiooooooooooooooooouuuuuuuuuuuyyyyyd"
    key = F.translate(F.lower(F.trim(column)), accented, plain)
    key = F.regexp_replace(key, r"[.\-–—]", " ")
    key = F.regexp_replace(key, r"\s+", " ")
    # Both exports and reference explicitly identify this as the same city.
    return F.trim(F.regexp_replace(key, r"^tp\s+", ""))


def load_reference(spark, path):
    if not path.is_file():
        raise ValueError(f"Missing province reference: {path}")
    payload = path.read_bytes()
    entries = json.loads(payload.decode("utf-8-sig"))
    if not isinstance(entries, list) or not entries:
        raise ValueError("Province reference must be a nonempty list of regions")
    records = []
    for entry in entries:
        if (not isinstance(entry, dict) or not isinstance(entry.get("region_name"), str)
                or not entry["region_name"].strip() or not isinstance(entry.get("provinces"), list)
                or not entry["provinces"] or entry.get("total_provinces") != len(entry["provinces"])):
            raise ValueError(f"Invalid region entry or province count: {entry!r}")
        for name in entry["provinces"]:
            if not isinstance(name, str) or not name.strip():
                raise ValueError(f"Invalid province name: {name!r}")

            records.append((unicodedata.normalize("NFC", name.strip()), entry["region_name"].strip(), len(records) + 1))
    reference = spark.createDataFrame(records, "province_name string, region string, province_id int")
    reference = reference.withColumn("province_key", province_key(F.col("province_name")))
    if reference.filter(F.col("province_key") == "").limit(1).count():
        raise ValueError("Province reference contains an empty normalized name")
    ambiguous = reference.groupBy("province_key").count().filter("count > 1").orderBy("province_key").collect()
    if ambiguous:
        raise ValueError(f"Ambiguous province mappings (no automatic resolution): {ambiguous}")
    return reference, {"file": "data/vietnam_regions_provinces.json",
                       "sha256": hashlib.sha256(payload).hexdigest(),
                       "province_count": len(records), "region_count": len(entries),
                       "province_id_assignment": "1-based consecutive IDs in region array order, then province array order; project IDs, not official administrative codes"}
