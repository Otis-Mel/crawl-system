@echo off
rem Chạy 1 lượt scraper Facebook (dùng cho Task Scheduler). Log chi tiết nằm ở logs\scraper_YYYYMMDD.log
cd /d "%~dp0"
if not exist logs mkdir logs
py -u fb_scraper_no_login_v2.py --once > logs\scheduler_last_run.txt 2>&1
echo Exit code: %errorlevel% >> logs\scheduler_last_run.txt
exit /b %errorlevel%
