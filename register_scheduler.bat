@echo off
setlocal
rem Start to register PrivateDevBOT Server on to Windows Task Scheduler.
set SCRIPT_DIR=%~dp0
echo %SCRIPT_DIR%

rem Task name is PrivateDevbotRAG 
set TASK_NAME=PrivateDevbotRAG

rem Register the task to run when windows os starts
schtasks /Create /SC ONLOGON /F /TN "%TASK_NAME%" /TR "cmd.exe /c cd /d %SCRIPT_DIR% && private_devbot.vbs"

if %ERRORLEVEL%==0 (
    echo Task registration succeeded.
) else (
    echo Task registration failed. (Use Admin Permission Execution)
)

endlocal
pause