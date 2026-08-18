@echo off
echo Starting ArgosOSINT Platform on http://127.0.0.1:8500
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8500 --reload
pause