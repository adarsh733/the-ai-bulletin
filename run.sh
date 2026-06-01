#!/bin/bash
echo "========================================================"
echo "       📰 The AI Bulletin - Local Launcher"
echo "========================================================"
echo ""

echo "[1/2] Running the scraper pipeline..."
python3 src/fetch_news.py

echo ""
echo "[2/2] Starting local web server..."
echo "Serving at http://localhost:8000/index.html"

# Detect OS and open browser
if [[ "$OSTYPE" == "darwin"* ]]; then
    open "http://localhost:8000/index.html"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    xdg-open "http://localhost:8000/index.html"
fi

python3 -m http.server 8000
