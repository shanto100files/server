#!/data/data/com.termux/files/usr/bin/bash

# Termux Background Optimizer Script for CinePix Server
echo "=========================================="
echo " CinePix Termux Optimizer & Auto-Restart"
echo "=========================================="

# 1. Enable Wake-Lock so CPU doesn't sleep
echo "[+] Enabling termux-wake-lock..."
termux-wake-lock

echo "[+] Starting server in Auto-Restart mode..."
echo "[+] Press CTRL+C twice quickly to stop completely."
echo "=========================================="

# 2. Infinite Loop for Auto-Restart
while true
do
    echo "[!] Starting Uvicorn Server..."
    # Using slightly reduced workers/connections optimized for mobile CPUs
    python -m uvicorn server:app --host 0.0.0.0 --port 8000 --workers 1 --limit-concurrency 50
    
    echo "[-] Server crashed or stopped. Restarting in 3 seconds..."
    sleep 3
done
