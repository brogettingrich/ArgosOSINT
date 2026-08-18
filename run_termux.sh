#!/data/data/com.termux/files/usr/bin/bash
echo "[*] Starting ArgosOSINT on http://127.0.0.1:8500..."
python -m uvicorn app.main:app --host 127.0.0.1 --port 8500