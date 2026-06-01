@echo off
echo ========================================================
echo        📰 The AI Bulletin - Local Launcher
echo ========================================================
echo.

echo [1/2] Running the scraper pipeline...
python src/fetch_news.py

echo.
echo [2/2] Starting local web server...
echo Serving at http://localhost:8000/index.html
start http://localhost:8000/index.html
python -m http.server 8000
