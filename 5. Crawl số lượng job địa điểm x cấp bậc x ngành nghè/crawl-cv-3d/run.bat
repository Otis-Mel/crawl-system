@echo off
cd /d "%~dp0"

set LOG_DIR=%~dp0logs
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

set LOG_FILE=%LOG_DIR%\%date:~6,4%-%date:~3,2%-%date:~0,2%.txt

echo ============================= >> "%LOG_FILE%"
echo Run: %date% %time%           >> "%LOG_FILE%"
echo ============================= >> "%LOG_FILE%"

python main.py >> "%LOG_FILE%" 2>&1

echo Exit code: %errorlevel%      >> "%LOG_FILE%"
