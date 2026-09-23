#!/bin/bash
# Auto-restart wrapper for galaxy server
while true; do
    echo "[$(date)] Starting galaxy server..."
    python3 /opt/data/galaxy-view/server.py
    echo "[$(date)] Server died, restarting in 2s..."
    sleep 2
done
