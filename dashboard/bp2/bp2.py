"""Streamlit page for the BP2 production decomposition."""

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


DATA = Path(__file__).resolve().parents[2] / "data/analytics/bp2/production_changes.parquet"
COMPONENTS = {
    "area_effect_ton": ("Diện tích", "#42B883"),
    "yield_effect_ton": ("Năng suất", "#E4B83F"),
    "residual_change_ton": ("Chênh lệch đối chiếu", "#D78B57"),
}
CHANGE = "production_change_ton"
NATIONAL = "Cả nước"
SURFACE = "#17231C"
TEXT = "#F3F5EA"
MUTED = "#A9B9AB"
GRID = "#304138"


def apply_theme():
    st.markdown(
        """
        <style>
        .stApp, [data-testid="stAppViewContainer"] {
            background: #0D1410;
            color: #F3F5EA;
        }
        [data-testid="stHeader"] {background: #0D1410;}
        [data-testid="stDecoration"] {display: none;}
        .block-container {max-width: 1450px; padding-top: 2.6rem;}
        .stApp h1 {
            color: #F3F5EA;
            font-size: clamp(2rem, 3vw, 2.75rem);
            letter-spacing: -.035em;
            font-weight: 750;
        }
        .stApp h2, .stApp h3 {color: #F3F5EA; letter-spacing: -.025em;}
        .stApp label, .stApp p, .stApp li {color: #DDE7DB;}
        [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {
            color: #A9B9AB;
            opacity: 1;
        }
        div[data-testid="stMetric"] {
            background: #17231C;
            border: 1px solid #304138;
            border-top: 3px solid #F3F5EA;
            border-radius: 10px;
            padding: 1.05rem 1.25rem;
            min-height: 126px;
        }
        div[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"])
            > div:nth-child(2) [data-testid="stMetric"] {border-top-color: #42B883;}
        div[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"])
            > div:nth-child(3) [data-testid="stMetric"] {border-top-color: #E4B83F;}
        div[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"])
            > div:nth-child(4) [data-testid="stMetric"] {border-top-color: #D78B57;}
        div[data-testid="stMetricLabel"] p {color: #A9B9AB; font-weight: 600;}
        div[data-testid="stMetricValue"] {color: #F3F5EA;}
        div[data-testid="stSelectbox"] [role="group"] {
            background: #17231C !important;
            border: 1px solid #3A5342 !important;
        }
        div[data-testid="stSelectbox"] input,
        div[data-testid="stSelectbox"] button {
            color: #F3F5EA !important;
        }
        div[data-testid="stSelectbox"] [role="group"]:focus-within {
            border-color: #E4B83F !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] > div {
            background: #17231C;
            border-color: #304138;
            border-radius: 10px;
        }
        div[data-testid="stExpander"] {
            background: #17231C;
            border-color: #304138;
            border-radius: 10px;
        }
        div[data-testid="stExpander"] summary {color: #F3F5EA;}
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data
def load_data(path, modified_ns):
    return pd.read_parquet(path, engine="pyarrow")


def waterfall(row):
    # Separate traces keep component colors stable across both charts.
    fig = go.Figure()
    running_total = 0.0
    for index, (field, (label, color)) in enumerate(COMPONENTS.items()):
        value = row[field] / 1_000
        next_total = running_total + value
        fig.add_bar(
            x=[label], y=[abs(value)], base=[min(running_total, next_total)],
            width=0.68, name=label, marker_color=color,
            customdata=[value],
            hovertemplate="%{x}<br>%{customdata:+,.2f} nghìn tấn<extra></extra>",
        )
        fig.add_shape(
            type="line", x0=index + 0.34, x1=index + 0.66,
            y0=next_total, y1=next_total,
            line=dict(color="#799080", width=1.5, dash="dot"),
        )
        running_total = next_total

    total = row[CHANGE] / 1_000
    fig.add_bar(
        x=["Thay đổi theo NSO"], y=[abs(total)], base=[min(0, total)],
        width=0.68, name="Thay đổi theo NSO", marker_color=TEXT,
        customdata=[total],
        hovertemplate="%{x}<br>%{customdata:+,.2f} nghìn tấn<extra></extra>",
    )
    fig.update_layout(
        template="plotly_dark", height=375, barmode="overlay",
        margin=dict(l=8, r=12, t=45, b=8),
        legend=dict(orientation="h", x=0, y=1.02, yanchor="bottom"),
        font=dict(color=TEXT), paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        hoverlabel=dict(bgcolor="#23352A", font_color=TEXT),
    )
    fig.update_yaxes(
        title_text="Nghìn tấn", zeroline=True, zerolinecolor="#6C806F",
        gridcolor=GRID, tickfont=dict(color=MUTED),
    )
    fig.update_xaxes(tickfont=dict(color=TEXT))
    return fig


def compare_places(rows, name_col):
    fig = go.Figure()
    for field, (label, color) in COMPONENTS.items():
        fig.add_bar(
            x=rows[field] / 1_000, y=rows[name_col],
            name=label, orientation="h", marker_color=color,
            hovertemplate="%{y}<br>%{x:+,.2f} nghìn tấn",
        )
    fig.add_scatter(
        x=rows[CHANGE] / 1_000, y=rows[name_col],
        name="Thay đổi theo NSO", mode="markers",
        marker=dict(color=TEXT, size=10, symbol="diamond"),
        hovertemplate="%{y}<br>%{x:+,.2f} nghìn tấn",
    )
    fig.update_layout(
        template="plotly_dark",
        barmode="group", height=max(360, 53 * len(rows) + 80),
        legend=dict(orientation="h", x=0, y=1.02, yanchor="bottom"),
        margin=dict(l=0, r=18, t=45, b=8),
        font=dict(color=TEXT), paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        hoverlabel=dict(bgcolor="#23352A", font_color=TEXT),
    )
    fig.update_yaxes(
        automargin=True, autorange="reversed",
        categoryorder="array", categoryarray=rows[name_col].tolist(),
        tickfont=dict(color=TEXT),
    )
    fig.update_xaxes(
        title_text="Nghìn tấn", zeroline=True, zerolinewidth=1,
        zerolinecolor="#6C806F", gridcolor=GRID,
        tickfont=dict(color=MUTED),
    )
    return fig


def show_dashboard():
    st.set_page_config(page_title="BP2 · Biến động sản lượng lúa", layout="wide")
    apply_theme()
    st.title("BP2 · Giải thích biến động sản lượng lúa")
    st.caption("Số liệu NSO theo 63 tỉnh/thành lịch sử, tổng hợp theo 7 vùng của dự án.")

    if not DATA.is_file():
        st.warning("Chưa có dữ liệu BP2. Từ thư mục gốc của repo, chạy `python -m src.bp2.bp2`.")
        return
    data = load_data(DATA, DATA.stat().st_mtime_ns)
    region_names = sorted(data["region"].dropna().unique())
    geography, from_year, to_year = st.columns([2, 1, 1])
    scope = geography.selectbox("Phạm vi", [NATIONAL, *region_names])
    end_options = sorted(int(year) for year in data["year_end"].unique())
    end = to_year.selectbox("Năm so sánh", end_options, index=len(end_options) - 1)
    start_options = sorted(int(year) for year in data.loc[data["year_end"].eq(end), "year_start"].unique())
    start = from_year.selectbox("Năm gốc", start_options, index=len(start_options) - 1)

    period = data.loc[data["year_start"].eq(start) & data["year_end"].eq(end)]
    if scope == NATIONAL:
        summary = period.loc[period["level"].eq("national")].iloc[0]
        detail = period.loc[period["level"].eq("region")]
        name_col, detail_title = "region", "So sánh 7 vùng"
    else:
        region = period.loc[period["region"].eq(scope)]
        summary = region.loc[region["level"].eq("region")].iloc[0]
        detail = region.loc[region["level"].eq("province")]
        name_col, detail_title = "province_name", "So sánh các tỉnh trong vùng"
    detail = detail.sort_values(CHANGE, key=lambda values: values.abs(), ascending=False, kind="stable")

    labels = [("Thay đổi theo NSO", CHANGE)] + [(label, key) for key, (label, _) in COMPONENTS.items()]
    for cell, (label, field) in zip(st.columns(4), labels):
        cell.metric(label, f"{summary[field] / 1_000:+,.2f}", help="Đơn vị: nghìn tấn")
    st.caption(f"Đơn vị nghìn tấn · {scope} · {start} → {end} · {summary['province_count']} tỉnh/thành")

    st.subheader("Phân rã thay đổi sản lượng")
    st.caption("Đọc từ trái sang phải. Màu xác định thành phần; cột đi lên hoặc xuống thể hiện dấu của đóng góp.")
    with st.container(border=True):
        st.plotly_chart(waterfall(summary), key="bp2_waterfall", theme=None, config={"displayModeBar": False})
    st.subheader(detail_title)
    st.caption("Xếp theo độ lớn thay đổi sản lượng. Thanh sang phải là dương, sang trái là âm; hình thoi sáng là tổng theo NSO.")
    with st.container(border=True):
        st.plotly_chart(compare_places(detail, name_col), key="bp2_comparison", theme=None, config={"displayModeBar": False})

    with st.expander("Xem bảng số liệu"):
        columns = {
            name_col: "Địa phương",
            "rice_production_ton_start": f"Sản lượng {start}",
            "rice_production_ton_end": f"Sản lượng {end}",
            **{field: label for label, field in labels},
        }
        table = detail[list(columns)].copy()
        table[list(columns)[1:]] /= 1_000
        st.dataframe(
            table.rename(columns=columns), hide_index=True,
            column_config={
                name: st.column_config.NumberColumn(format="%.2f")
                for name in list(columns.values())[1:]
            },
        )
        st.caption("Đơn vị của các cột số là nghìn tấn.")

    with st.expander("Quy ước màu, cách tính và giới hạn diễn giải"):
        st.markdown(
            "- **Xanh lá · Diện tích:** gợi diện tích đất gieo trồng.\n"
            "- **Vàng lúa · Năng suất:** gợi hạt lúa và kết quả trên mỗi hecta.\n"
            "- **Cam · Chênh lệch đối chiếu:** phần điều chỉnh để khớp sản lượng NSO công bố.\n"
            "- **Trắng ngà · Thay đổi theo NSO:** số tổng được quan sát, không phải một tác nhân thứ tư.\n"
            "- Màu giữ cùng ý nghĩa ở thẻ số liệu và cả hai biểu đồ. Dấu số và chiều cột cho biết tăng hoặc giảm.\n"
            "- **Diện tích** = thay đổi diện tích × năng suất trung bình hai năm.\n"
            "- **Năng suất** = thay đổi năng suất × diện tích trung bình hai năm.\n"
            "- **Chênh lệch đối chiếu** = mức thay đổi của khoảng cách giữa sản lượng công bố "
            "và diện tích × năng suất. Khoảng cách có thể phát sinh do làm tròn số liệu nguồn.\n"
            "- Mỗi thành phần được tính ở cấp tỉnh trước khi cộng lên vùng và cả nước. "
            "Khi hai năm cách nhau nhiều năm, biểu đồ so sánh hai mốc được chọn.\n"
            "- Đây là phân rã số học. Kết quả cho biết đóng góp theo công thức, "
            "không xác định nguyên nhân thực tế. Sản lượng phản ánh nguồn cung tiềm năng.\n"
            "- Nguồn: NSO V06.13, V06.14 và V06.15. Tệp dùng chung không có cột trạng thái công bố."
        )


show_dashboard()
