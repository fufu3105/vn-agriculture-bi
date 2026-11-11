"""Rebuild BP1 rice sourcing analysis from the three NSO PX-Web exports.

Run from the repository root: python src/bp1.py
"""

from __future__ import annotations

import csv
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from xml.sax.saxutils import escape

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "analytics"
FIG = ROOT / "deliverables" / "report" / "figures"
FIELDS = {
    "V06.13": "area_thousand_ha",
    "V06.14": "yield_quintal_per_ha",
    "V06.15": "production_thousand_tons",
}
ALIASES = {
    "Hoà Bình": "Hòa Bình", "Khánh Hoà": "Khánh Hòa",
    "Thanh Hoá": "Thanh Hóa", "Bà Rịa - Vũng Tàu": "Bà Rịa – Vũng Tàu",
    "TP.Hồ Chí Minh": "TP. Hồ Chí Minh",
}
START, END = 2015, 2024


def read_table(code: str):
    path = RAW / f"nso_{code}_2010_2024.xlsx"
    ws = load_workbook(path, read_only=True, data_only=True).active
    rows = list(ws.values)
    years = [int(v) for v in rows[2][1:]]
    assert years == list(range(2010, 2025)), (code, years)
    values = {}
    for row in rows[3:]:
        name = row[0]
        if not name:
            continue
        assert name not in values, (code, name)
        cells = row[1:16]
        assert len(cells) == 15 and all(isinstance(v, (int, float)) for v in cells), (code, name)
        values[name] = dict(zip(years, map(float, cells)))
    return values


def write_csv(path: Path, rows: list[dict], columns: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def fmt(value, digits=1):
    return f"{value:,.{digits}f}"


def svg_bar(path: Path, title: str, rows: list[dict], field: str, unit: str, color="#137a52"):
    width, left, right, top, step = 1060, 285, 100, 100, 44
    height = top + step * len(rows) + 75
    maxv = max(r[field] for r in rows)
    usable = width - left - right
    bits = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            '<rect width="100%" height="100%" fill="#fff"/>',
            f'<text x="32" y="42" font-size="25" font-family="Arial" font-weight="bold" fill="#17352b">{escape(title)}</text>',
            f'<text x="32" y="67" font-size="14" font-family="Arial" fill="#54645d">{escape(unit)}</text>']
    for i, row in enumerate(rows):
        y = top + i * step
        v = row[field]
        w = usable * v / maxv
        bits += [f'<text x="{left-12}" y="{y+21}" text-anchor="end" font-size="15" font-family="Arial" fill="#17352b">{escape(row["name"])}</text>',
                 f'<rect x="{left}" y="{y+5}" width="{w:.1f}" height="25" rx="4" fill="{color}"/>',
                 f'<text x="{left+w+9:.1f}" y="{y+23}" font-size="14" font-family="Arial" fill="#17352b">{fmt(v,0)}</text>']
    bits += ['</svg>']
    path.write_text("\n".join(bits), encoding="utf-8")


def svg_scatter(path: Path, rows: list[dict]):
    # Percentage changes on tiny production bases can dominate both axes.
    rows=[r for r in rows if r["production_2024_thousand_tons"]>=500]
    width, height = 1100, 720
    x0, y0, x1, y1 = 105, 110, 900, 590
    xs = [r["cagr_pct"] for r in rows]
    ys = [r["yoy_sd_pct_points"] for r in rows]
    xmin, xmax = min(xs)-0.6, max(xs)+0.6
    ymax = max(ys)*1.12
    def sy(value):
        return y1-math.log1p(value)/math.log1p(ymax)*(y1-y0)
    top = sorted(rows, key=lambda r:r["production_2024_thousand_tons"], reverse=True)[:10]
    top_names = {r["name"] for r in top}
    label_offsets={"Kiên Giang":(-35,-23),"Long An":(20,25),"An Giang":(18,18),
                   "Thanh Hóa":(15,25),"Trà Vinh":(15,-14)}
    bits = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            '<rect width="100%" height="100%" fill="#fff"/>',
            '<text x="40" y="45" font-size="25" font-family="Arial" font-weight="bold" fill="#17352b">Quy mô, tăng trưởng và biến động sản lượng theo tỉnh</text>',
            '<text x="40" y="72" font-size="14" font-family="Arial" fill="#54645d">Chỉ hiển thị tỉnh đạt ít nhất 500 nghìn tấn năm 2024; bảng bên dưới có đủ 63 tỉnh</text>',
            f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="#52645b"/>',
            f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" stroke="#52645b"/>']
    xzero = x0+(0-xmin)/(xmax-xmin)*(x1-x0)
    bits.append(f'<line x1="{xzero:.1f}" y1="{y0}" x2="{xzero:.1f}" y2="{y1}" stroke="#9aa7a0" stroke-dasharray="5,5"/>')
    for tick in range(math.floor(xmin), math.ceil(xmax)+1, 2):
        x=x0+(tick-xmin)/(xmax-xmin)*(x1-x0)
        bits.append(f'<text x="{x:.1f}" y="{y1+24}" text-anchor="middle" font-size="12" font-family="Arial">{tick}%</text>')
    for tick in [0,2,5,10,20,50,100]:
        if tick>ymax: continue
        y=sy(tick)
        bits += [f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" stroke="#e6ece8"/>',
                 f'<text x="{x0-10}" y="{y+4:.1f}" text-anchor="end" font-size="12" font-family="Arial">{tick}</text>']
    for r in sorted(rows,key=lambda q:q["production_2024_thousand_tons"]):
        x=x0+(r["cagr_pct"]-xmin)/(xmax-xmin)*(x1-x0)
        y=sy(r["yoy_sd_pct_points"])
        radius=4+12*math.sqrt(r["production_2024_thousand_tons"]/max(q["production_2024_thousand_tons"] for q in rows))
        fill="#137a52" if r["name"] in top_names else "#95b9a6"
        bits.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" fill="{fill}" fill-opacity="0.76" stroke="#fff"><title>{escape(r["name"])}: {fmt(r["production_2024_thousand_tons"])} nghìn tấn; CAGR {fmt(r["cagr_pct"])}%; SD tăng trưởng {fmt(r["yoy_sd_pct_points"])} điểm %</title></circle>')
        if r["name"] in label_offsets:
            dx,dy=label_offsets[r["name"]]
            bits.append(f'<text x="{x+dx:.1f}" y="{y+dy:.1f}" font-size="12" font-family="Arial" fill="#17352b">{escape(r["name"])}</text>')
    bits += [f'<text x="{(x0+x1)/2}" y="{height-50}" text-anchor="middle" font-size="15" font-family="Arial">CAGR sản lượng 2015–2024 (%)</text>',
             f'<text x="30" y="{(y0+y1)/2}" transform="rotate(-90 30 {(y0+y1)/2})" text-anchor="middle" font-size="15" font-family="Arial">Độ lệch chuẩn tăng trưởng năm (điểm %)</text>', '</svg>']
    path.write_text("\n".join(bits),encoding="utf-8")


def main():
    regions=json.loads((RAW/"vietnam_regions_provinces.json").read_text(encoding="utf-8"))
    assert len(regions)==7 and sum(len(r["provinces"]) for r in regions)==63
    mapping={p:r["region_name"] for r in regions for p in r["provinces"]}
    assert len(mapping)==63
    tables={code:read_table(code) for code in FIELDS}
    assert len({tuple(t) for t in tables.values()})==1, "NSO location labels differ"
    source_names={n for n in tables["V06.15"] if n in mapping or ALIASES.get(n) in mapping}
    assert len(source_names)==63, f"Mapped {len(source_names)} provinces"
    assert len({ALIASES.get(n,n) for n in source_names})==63
    panel=[]
    for source_name in sorted(source_names):
        name=ALIASES.get(source_name,source_name)
        for year in range(2010,2025):
            row={"province":name,"region":mapping[name],"year":year}
            row.update({field:tables[code][source_name][year] for code,field in FIELDS.items()})
            panel.append(row)
    assert len(panel)==945
    by_year=defaultdict(float)
    for row in panel: by_year[row["year"]]+=row["production_thousand_tons"]
    national=tables["V06.15"]["CẢ NƯỚC"]
    gaps={y:by_year[y]-national[y] for y in by_year}
    assert max(abs(v) for v in gaps.values())<3, gaps
    write_csv(ROOT/"data"/"processed"/"rice_province_year.csv",panel,
              ["province","region","year",*FIELDS.values()])
    grouped=defaultdict(dict)
    for row in panel: grouped[row["province"]][row["year"]]=row
    summaries=[]
    for name, series in grouped.items():
        values=[series[y]["production_thousand_tons"] for y in range(START,END+1)]
        changes=[100*(b/a-1) for a,b in zip(values,values[1:])]
        assert all(v>0 for v in values)
        summaries.append({"name":name,"region":series[END]["region"],
            "production_2024_thousand_tons":values[-1],
            "share_2024_pct":100*values[-1]/by_year[END],
            "cagr_pct":100*((values[-1]/values[0])**(1/(END-START))-1),
            "yoy_sd_pct_points":statistics.stdev(changes),
            "largest_yoy_decline_pct":min(changes),
            "production_2015_thousand_tons":values[0]})
    summaries.sort(key=lambda r:r["production_2024_thousand_tons"],reverse=True)
    region_rows=[]
    for region in [r["region_name"] for r in regions]:
        subset=[r for r in panel if r["region"]==region]
        annual={y:sum(r["production_thousand_tons"] for r in subset if r["year"]==y) for y in range(START,END+1)}
        changes=[100*(annual[y]/annual[y-1]-1) for y in range(START+1,END+1)]
        region_rows.append({"name":region,"province_count":len({r["province"] for r in subset}),
            "production_2024_thousand_tons":annual[END],"share_2024_pct":100*annual[END]/by_year[END],
            "cagr_pct":100*((annual[END]/annual[START])**(1/(END-START))-1),
            "yoy_sd_pct_points":statistics.stdev(changes),"largest_yoy_decline_pct":min(changes)})
    region_rows.sort(key=lambda r:r["production_2024_thousand_tons"],reverse=True)
    OUT.mkdir(parents=True,exist_ok=True)
    write_csv(OUT/"bp1_province_summary.csv",summaries,list(summaries[0]))
    write_csv(OUT/"bp1_region_summary.csv",region_rows,list(region_rows[0]))
    FIG.mkdir(parents=True,exist_ok=True)
    svg_bar(FIG/"bp1_region_production_2024.svg","Sản lượng lúa theo vùng, 2024",region_rows,"production_2024_thousand_tons","Nghìn tấn; vùng theo quy ước 63 tỉnh của nhóm")
    svg_bar(FIG/"bp1_top15_provinces_2024.svg","15 tỉnh có sản lượng lúa cao nhất, 2024",summaries[:15],"production_2024_thousand_tons","Nghìn tấn")
    svg_scatter(FIG/"bp1_province_growth_volatility.svg",summaries)
    dashboard={"regions":region_rows,"provinces":summaries,"annual":panel,"national_2024":by_year[END]}
    (OUT/"bp1_dashboard_data.json").write_text(json.dumps(dashboard,ensure_ascii=False),encoding="utf-8")
    template=(ROOT/"dashboard"/"bp1_template.html").read_text(encoding="utf-8")
    (ROOT/"dashboard"/"bp1.html").write_text(
        template.replace("__DATA__",json.dumps({k:v for k,v in dashboard.items() if k!="annual"},ensure_ascii=False).replace("</","<\\/")),
        encoding="utf-8")
    print(json.dumps({"national_2024_thousand_tons":by_year[END],"max_national_reconciliation_gap_thousand_tons":max(abs(v) for v in gaps.values()),"top_regions":region_rows[:3],"top_provinces":summaries[:10]},ensure_ascii=False,indent=2))


if __name__ == "__main__":
    # Windows terminals may default to an encoding without Vietnamese glyphs.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
