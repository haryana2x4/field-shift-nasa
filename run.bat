@echo off
title Field Shift - NASA Earth Observations
echo ================================================================
echo   Field Shift: Adapting Farms with NASA Data (Hackathon Project)
echo ================================================================
echo Starting web server...
cd /d "%~dp0"
"C:\Users\Rocky\AppData\Local\Programs\Python\Python312\python.exe" app.py
pause
