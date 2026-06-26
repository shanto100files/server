#!/data/data/com.termux/files/usr/bin/bash

# Termux Background Optimizer & Auto-Deploy Script for CinePix
echo "=========================================="
echo " CinePix Termux Optimizer & Auto-Deploy"
echo "=========================================="

# 1. Enable Wake-Lock so CPU doesn't sleep
echo "[+] Enabling termux-wake-lock..."
termux-wake-lock

echo "[+] Starting server in Auto-Deploy mode..."
echo "[+] Press CTRL+C multiple times quickly to stop completely."
echo "=========================================="

# 2. Background Auto-Deploy Poller
# This loop checks GitHub every 5 minutes. If new code is found, 
# it pulls it and kills the server to force a restart.
(
    while true; do
        sleep 300  # Check every 5 minutes (300 seconds)
        
        # Fetch latest changes from remote without applying them
        git fetch origin main >/dev/null 2>&1
        
        # Check if local head is different from remote head
        LOCAL=$(git rev-parse HEAD)
        REMOTE=$(git rev-parse origin/main)
        
        if [ "$LOCAL" != "$REMOTE" ]; then
            echo "[Auto-Deploy] New update found on GitHub! Downloading..."
            git pull origin main >/dev/null 2>&1
            echo "[Auto-Deploy] Update successful. Restarting server..."
            
            # Kill the running uvicorn process
            pkill -f "uvicorn server:app"
        fi
    done
) &  # Run this poller in the background

# Save the poller PID so we can kill it later if needed
POLLER_PID=$!

# Trap CTRL+C to kill the background poller when the script stops
trap "echo 'Stopping auto-deploy...'; kill $POLLER_PID 2>/dev/null; exit" SIGINT SIGTERM

# 3. Infinite Loop for Auto-Restart
while true
do
    echo "[!] Starting Uvicorn Server..."
    python -m uvicorn server:app --host 0.0.0.0 --port 8000 --workers 1 --limit-concurrency 50
    
    echo "[-] Server stopped or crashed. Restarting in 3 seconds..."
    sleep 3
done
