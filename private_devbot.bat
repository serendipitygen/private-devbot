@echo off
chcp 65001 > nul

echo [INFO] Current directory: %cd%
echo [INFO] Batch file directory: %~dp0
echo [INFO] Attempting to activate Conda environment: private_devbot_conda...
call "%~dp0private_devbot_conda\Scripts\activate.bat"

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to execute activate.bat.
    echo [ERROR] Expected path: "%~dp0private_devbot_conda\Scripts\activate.bat"
    echo [ERROR] Please check if the Conda environment 'private_devbot_conda' exists in the same directory as run.bat and is correctly configured.
    pause
    goto :eof
)
echo [INFO] Conda environment activated successfully.

echo [INFO] Starting Private DevBOT RAG Server...
set PYTHONUNBUFFERED=1
echo [INFO] PYTHONUNBUFFERED=1 set to disable buffering
python private_devbot_ui.py