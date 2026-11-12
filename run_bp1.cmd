@echo off
setlocal
cd /d "%~dp0"
set "AGRI_PYTHON=python"
if exist ".venv\Scripts\python.exe" set "AGRI_PYTHON=%~dp0.venv\Scripts\python.exe"
rem Start all dashboards without rebuilding a teammate's analytics.
if /i "%~1"=="--build-bp1" (
    "%AGRI_PYTHON%" src/bp1/bp1.py
    if errorlevel 1 goto failed
)
"%AGRI_PYTHON%" -m streamlit run dashboard/app.py --server.address=127.0.0.1 --server.port=8501
if errorlevel 1 goto failed
exit /b 0
:failed
echo.
echo Could not start the agriculture dashboard. See the error above.
pause
exit /b 1
