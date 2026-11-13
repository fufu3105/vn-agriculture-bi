"""Shared Streamlit shell. Each team member owns dashboard/bpN/bpN.py."""
from pathlib import Path
import sys

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
# BP pages may import their helpers as src.bpN.module regardless of launch cwd.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MART = ROOT / "data/analytics/bp1/national_year.parquet"
st.set_page_config(page_title="Viet Rice · Agriculture BI", page_icon=":material/agriculture:", layout="wide")
st.markdown('<style>' + (ROOT / "dashboard/styles.css").read_text(encoding="utf-8") + '</style>', unsafe_allow_html=True)

BUSINESS_PROBLEMS = [
    ("bp1", "Rice production overview", "DESCRIPTIVE", ":material/eco:",
     "Explore production scale, sown area, yield and trends across provinces and regions.", True),
    ("bp2", "Explaining production changes", "DIAGNOSTIC", ":material/analytics:",
     "Compare how sown area and yield contribute to reported production changes across provinces and regions.", True),
    ("bp3", "Production forecasting", "PREDICTIVE", ":material/trending_up:",
     "Estimate next year’s production and assess forecast accuracy for supply planning.", False),
    ("bp4", "Weather & yield", "DIAGNOSTIC", ":material/partly_cloudy_day:",
     "Examine the relationship between temperature, rainfall and rice yield.", False),
]


@st.cache_data(show_spinner=False)
def load_summary(parquet_path, version):
    frame = pd.read_parquet(parquet_path)
    required = ["year", "rice_production_ton", "rice_area_ha", "rice_yield_ton_ha"]
    if frame.empty or not set(required).issubset(frame.columns):
        raise ValueError("The national summary is empty or its schema is incomplete.")
    if not all(pd.api.types.is_numeric_dtype(frame[column]) for column in required):
        raise ValueError("The national summary contains nonnumeric measurements.")
    summary = frame.sort_values("year").iloc[-1]
    if summary[required].isna().any():
        raise ValueError("The latest national summary has missing measurements.")
    return summary


def home():
    st.markdown('''<div class="hero">
      <div class="eyebrow">VIETNAM AGRICULTURE ANALYTICS</div>
      <h1>From crop data<br>to supply planning.</h1>
      <p>A shared view of rice production in Vietnam. Explore current patterns,
      understand changes and prepare supply plans for the seasons ahead.</p>
      <span class="hero-tag">National Statistics Office · 2010–2024 · 63 historical provinces</span>
    </div>''', unsafe_allow_html=True)
    summary = None
    try:
        if MART.is_file():
            summary = load_summary(str(MART), (MART.stat().st_mtime_ns, MART.stat().st_size))
    except (OSError, ValueError, KeyError):
        st.warning("The BP1 national summary is unavailable. You can still open the other dashboards.")
    if summary is not None:
        st.caption(f"NATIONAL OVERVIEW · {int(summary.year)}")
        cols = st.columns(3)
        cols[0].metric("RICE PRODUCTION", f"{summary.rice_production_ton / 1e6:.2f} million tonnes", border=True)
        cols[1].metric("RICE SOWN AREA", f"{summary.rice_area_ha / 1e6:.2f} million ha", border=True)
        cols[2].metric("WEIGHTED AVERAGE YIELD", f"{summary.rice_yield_ton_ha:.2f} tonnes/ha", border=True)
    elif not MART.is_file():
        st.info("BP1 analytics have not been built yet. The other dashboards remain available; open BP1 for setup instructions.")
    st.subheader("Four perspectives. One supply plan.")
    st.markdown("Start with production patterns, then connect diagnostic analysis, forecasts and weather insights.")
    # A 2×2 grid keeps titles and descriptions readable on laptops.
    for start in (0, 2):
        for col, (key, title, kind, icon, description, ready) in zip(st.columns(2), BUSINESS_PROBLEMS[start:start + 2]):
            with col, st.container(border=True):
                st.markdown(f'<div class="bp-tag">{key.upper()} / {kind}</div>', unsafe_allow_html=True)
                st.subheader(title)
                st.markdown(f'<div class="bp-description">{description}</div>', unsafe_allow_html=True)
                status = "Ready to explore" if ready else "In development"
                st.markdown(f'<div class="bp-status {"ready" if ready else ""}">{status}</div>', unsafe_allow_html=True)
                st.page_link(pages[key], label="Explore dashboard" if ready else "View analysis scope", icon=icon, width="stretch")
    st.markdown('<div class="flow-note">For procurement, supply planning and BI teams. '
                'Reported production represents potential supply; procurement decisions also require price, quality and logistics information.</div>', unsafe_allow_html=True)


home_page = st.Page(home, title="System overview", icon=":material/grid_view:", default=True)
pages = {key: st.Page(f"{key}/{key}.py", title=f"{key.upper()} · {title}", icon=icon, url_path=key)
         for key, title, _, icon, _, _ in BUSINESS_PROBLEMS}
navigation = st.navigation([home_page, *pages.values()], position="hidden")
with st.sidebar:
    st.markdown('''<div class="brand"><div class="brand-mark">♧</div>
      <strong>Viet Rice<span style="color:#E3C46A">.</span></strong>
      <small>AGRICULTURE & SUPPLY</small></div>''', unsafe_allow_html=True)
    st.page_link(home_page, label="System overview", icon=":material/grid_view:")
    st.markdown('<div class="sidebar-section">ANALYTICS WORKSPACE</div>', unsafe_allow_html=True)
    for key, title, _, icon, _, _ in BUSINESS_PROBLEMS:
        st.page_link(pages[key], label=f"{key.upper()} · {title}", icon=icon)
    st.markdown('''<div class="sidebar-source">VIETNAM AGRICULTURE DATA<br>
      2010–2024 · 63 provinces · 7 regions<br>Source: National Statistics Office</div>''', unsafe_allow_html=True)
navigation.run()
