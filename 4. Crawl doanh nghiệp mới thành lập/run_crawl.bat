@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist logs mkdir logs
python -X utf8 -u crawl_dn_moi.py %* >> "logs\crawl_%date:~-4%%date:~3,2%%date:~0,2%.log" 2>&1
