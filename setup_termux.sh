#!/data/data/com.termux/files/usr/bin/bash
pkg update -y
pkg install -y python sqlite libffi openssl git
pip install -r requirements.txt
chmod +x run_termux.sh
echo "[*] Setup complete! Run ./run_termux.sh to start."