@echo off
REM Daily sync cron job for Windows
REM Schedule with Task Scheduler: run daily at 3:00 AM

cd /d "%~dp0\.."

REM Set PYTHONPATH
set PYTHONPATH=app

REM Run daily sync
echo Starting daily sync at %date% %time%
python scripts\daily_sync.py
echo Daily sync completed at %date% %time%