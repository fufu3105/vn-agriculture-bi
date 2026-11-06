@echo off
setlocal
cd /d "%~dp0"
python -m streamlit run dashboard/app.py --server.address=127.0.0.1 --server.port=8501
if errorlevel 1 (
    echo.
    echo Dashboard failed to start. See the error above.
    pause
)
