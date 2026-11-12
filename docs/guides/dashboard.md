# Run and extend the dashboard system

[Project overview](../../README.md) | [Environment setup](environment_setup.md)

From the repository root:

```powershell
python -m pip install -r requirements.txt
python -m streamlit run dashboard/app.py --theme.base=configs/config.toml
```

On Windows, `run_bp1.cmd` uses `.venv` when available and starts the shared application. The filename is retained for compatibility, but it opens all four dashboards. It does not build BP1 or any other member's data as a prerequisite.

Build analytics separately when needed:

```powershell
python src/bp1/bp1.py
# Once implemented by their owners:
# python src/bp2/bp2.py
# python src/bp3/bp3.py
# python src/bp4/bp4.py
```

The optional Windows shortcut `run_bp1.cmd --build-bp1` builds BP1 first. The parent PowerShell launcher supports `-BuildBp1`.

Open http://localhost:8501. The homepage links to four dashboards. BP1 is implemented; BP2?BP4 are integration placeholders. The other dashboards remain accessible if BP1's homepage summary is missing, corrupt or has an invalid schema.

## Ownership and integration contract

| BP | Analytics code | Analytics output | Dashboard entry point | Direct URL |
|---|---|---|---|---|
| BP1 | src/bp1/bp1.py | data/analytics/bp1/*.parquet | dashboard/bp1/bp1.py | /bp1 |
| BP2 | src/bp2/ | data/analytics/bp2/*.parquet | dashboard/bp2/bp2.py | /bp2 |
| BP3 | src/bp3/ | data/analytics/bp3/*.parquet | dashboard/bp3/bp3.py | /bp3 |
| BP4 | src/bp4/ | data/analytics/bp4/*.parquet | dashboard/bp4/bp4.py | /bp4 |

Each member can replace their dashboard placeholder and add helpers inside their own `src/bpN/` and `dashboard/bpN/` directories. All four routes are already registered. Page scripts execute when selected; the shell does not import or run every member's dashboard at startup.

Each BP reads cleaned shared data from `data/processed/`, calculates its own features, indicators or models and writes Parquet into its own analytics directory. A dashboard reads only that BP's analytics output. File names and derived schemas belong to the BP owner and should be documented in `docs/bp/bpN.md`.

The coordinator owns `dashboard/app.py`, `dashboard/styles.css`, `configs/config.toml` and shared dependencies in `requirements.txt`. The theme is loaded at startup with `--theme.base=configs/config.toml`; the Windows launchers pass its absolute path automatically. The only shell change needed after integration is changing the BP's readiness flag in `BUSINESS_PROBLEMS` from `False` to `True`; this changes the homepage status, not routing. Members do not need to edit navigation or BP1 to develop their pages.

## Minimal BP2 page example

This example expects a `year` column in the BP2 owner's `production_changes.parquet`. Change the file and schema for the actual analytics output. It is a handoff example, not a completed BP2 analysis.

```python
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
PARQUET = ROOT / "data/analytics/bp2/production_changes.parquet"


@st.cache_data(show_spinner=False)
def load_bp2_data(path, modified_ns, size):
    return pd.read_parquet(path)


st.title("Explaining production changes")
try:
    signature = PARQUET.stat()
    data = load_bp2_data(str(PARQUET), signature.st_mtime_ns, signature.st_size)
    if data.empty or "year" not in data or data["year"].isna().any():
        raise ValueError("The BP2 output needs nonempty data and a valid year column.")
except (OSError, ValueError) as exc:
    st.info("BP2 analytics are not available yet. Build the BP2 data mart first.")
    with st.expander("Data details"):
        st.text(str(exc))
    st.stop()

year = st.selectbox(
    "Year", sorted(data["year"].unique(), reverse=True), key="bp2_year"
)
st.dataframe(data.loc[data["year"] == year], hide_index=True, width="stretch")
```

Apply the same pattern to BP3 and BP4 with their own names, output paths and widget keys.

## Rules that prevent integration conflicts

- Run the shared `dashboard/app.py`; do not call `st.set_page_config`, create another `st.navigation` or modify the common sidebar inside a BP page.
- Keep interface copy in English. The shell loads the green/gold theme and common CSS for every page.
- Resolve data paths from `__file__` rather than the current working directory. For a page at `dashboard/bpN/bpN.py`, `parents[2]` is the repository root.
- Import analytics helpers using names such as `from src.bp2.features import ...`. The shell places the repository root on Python's import path. Avoid ambiguous imports such as `import bp2`.
- Prefix every widget/session key with its BP: `bp2_year`, `bp3_model`, `bp4_region`. Keep analysis-specific state out of other pages.
- Use BP-specific cache function names, and pass the data path and file signature as cache arguments. A parameterless cached reader that depends on a changing global path can serve stale or another page's results.
- Stop only the selected page with a clear message when its data is missing. Do not run ETL/model training automatically on every Streamlit rerun or attempt to build another member's outputs.
- Keep shared province IDs, historical boundaries and standard units: ha, tonnes/ha and tonnes. Format display units explicitly; do not overwrite canonical values or assume all BP tables use the same grain.
- Document each output's keys and schema. Forecast tables should distinguish the forecast year from the training cutoff; weather joins must document their province/year alignment.
- Add Python dependencies to `requirements.txt` through the coordinator; do not install packages from dashboard code.

## Current limits and handoff check

BP2 and BP3 can start from the existing agricultural panel (945 province-year rows, 2010?2024). BP3 must use time-based validation and avoid future leakage. Weather ingestion and processed weather data are still placeholders, so BP4's owner must supply that pipeline and its aligned inputs. Navigation is ready; this does not mean the unfinished analyses or data sources are implemented.

`scripts/build_analytics.py` is currently a placeholder, not an all-BP build command. Run each owner's entry point explicitly until a shared dispatcher is implemented. PostgreSQL is also deferred; dashboards read Parquet directly.

Before marking a BP ready:
1. Run its processing command from the repository root and verify its Parquet outputs.
2. Start `dashboard/app.py`, open that BP from the sidebar and homepage, and check its filters.
3. Switch between all four BP pages and check that their widget values/data do not conflict.
4. Check missing-data behavior in a disposable copy; it must not prevent other pages from opening.
5. Commit the page, helper code, dependency changes and required data outputs together. Git does not transfer untracked files to teammates.
6. Ask the coordinator to update the readiness flag.

Keep the terminal running; press Ctrl+C to stop. Refresh after rebuilding data; cache signatures update when files change.

See [BP1](../bp/bp1.md) for its filters, calculations, schemas and limitations.
