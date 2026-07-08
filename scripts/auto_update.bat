@echo off
rem Task Scheduler runner - silent, logs only (keep this file ASCII-only)
cd /d "%~dp0.."
if not exist logs mkdir logs
echo ===== update start ===== >> logs\update.log
date /t >> logs\update.log
time /t >> logs\update.log
"C:\Users\gkwls\AppData\Local\Programs\Python\Python314\python.exe" -X utf8 scripts\update_products.py >> logs\update.log 2>&1
echo exit code: %errorlevel% >> logs\update.log
