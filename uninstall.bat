@echo off
setlocal

rem Task name to be deleted
set TASK_NAME=PrivateDevbotRAG

rem 작업 스케쥴러에서 작업 삭제
schtasks /Delete /TN "%TASK_NAME%" /F

if %ERRORLEVEL%==0 (
    echo Task deletion succeeded.
) else (
    echo Task deletion failed.
)

endlocal
pause