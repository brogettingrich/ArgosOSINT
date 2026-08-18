@echo off
echo ============================================================
echo Setting up ArgosOSINT on Windows...
echo ============================================================
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
echo Setup completed! Run run_windows.bat to start.
pause