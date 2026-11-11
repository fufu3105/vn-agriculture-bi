"""Extract the inspected NSO Excel exports; all analytical work is done in Spark."""

import hashlib
import re
import unicodedata
from pathlib import Path
from openpyxl import load_workbook


SOURCES = {
    "V06.13": ("rice_area_ha", "Diện tích gieo trồng lúa cả năm", "thousand hectares", 1000.0),
    "V06.14": ("rice_yield_ton_ha", "Năng suất gieo trồng lúa cả năm", "quintals/hectare", 0.1),
    "V06.15": ("rice_production_ton", "Sản lượng lúa cả năm", "thousand tons", 1000.0),
}


def extract_workbooks(root: Path):
    """Return long records plus source metadata, without assuming tidy source rows."""
    records, metadata = [], []
    for table, (metric, title, unit, factor) in SOURCES.items():
        path = root / "data" / "raw" / "agriculture" / f"nso_{table}_2010_2024.xlsx"
        
        if not path.is_file():
            raise ValueError(f"Missing input workbook: {path}")
        with path.open("rb") as stream:
            checksum = hashlib.file_digest(stream, "sha256").hexdigest()
        
        book = load_workbook(path, read_only=True, data_only=False)
        
        try:
            if book.sheetnames != [table]:
                raise ValueError(f"{path.name}: expected exactly the sheet {table}; got {book.sheetnames}")
            
            sheet = book[table]
            rows = list(sheet.iter_rows())
            if len(rows) < 4 or not str(rows[0][0].value).startswith(title):
                raise ValueError(f"{path.name}: unexpected title or missing data rows")
            if any(c.value is not None for c in rows[0][1:] + rows[1]) or rows[2][0].value is not None:
                raise ValueError(f"{path.name}: metadata/header layout changed; inspect rows 1–3")
            
            years = [str(c.value).strip() for c in rows[2][1:]]
            if not years or any(not re.fullmatch(r"\d{4}", y) or not 1900 <= int(y) <= 2100 for y in years):
                raise ValueError(f"{path.name}: invalid year headers: {years}")
            if len(set(years)) != len(years):
                raise ValueError(f"{path.name}: duplicate year columns")
            
            names = []
            for row in rows[3:]:
                if not isinstance(row[0].value, str) or not row[0].value.strip():
                    raise ValueError(f"{path.name}: missing geographical name at {row[0].coordinate}")
                name = unicodedata.normalize("NFC", row[0].value.strip())
                names.append(name)
                for year, cell in zip(years, row[1:]):
                    value = cell.value
                    if cell.data_type in {"f", "e"} or isinstance(value, bool) or (
                        value is not None and not isinstance(value, (int, float, str))
                    ):
                        raise ValueError(f"{path.name}:{cell.coordinate}: unsupported cell {value!r}")
                    records.append((year, name, metric, None if value is None else str(value),
                                    factor, path.name, table, cell.coordinate))
            metadata.append({
                "file": path.relative_to(root).as_posix(), "sha256": checksum,
                "sheet": table, "range": f"A1:{rows[-1][-1].coordinate}",
                "title": rows[0][0].value, "year_header_row": 3,
                "years": sorted(map(int, years)), "geographical_rows": len(names),
                "source_names": names, "metric": metric,
                "workbook_unit_declaration": None, "conversion_source_unit": unit,
                "conversion_factor": factor,
            })
        finally:
            book.close()

    return records, metadata


def to_spark(spark, records):
    return spark.createDataFrame(records, "year_raw string, source_province_name string, "
                                 "metric string, value_raw string, conversion_factor double, "
                                 "source_file string, source_sheet string, source_cell string")
