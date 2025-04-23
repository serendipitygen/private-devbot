REM Run Private DevBOT RAG Server

echo Activating Conda environment: private_devbot_conda...
call .\private_devbot_conda\Scripts\activate.bat

REM activate.bat 실행 중 오류가 발생했는지 간단히 확인 (선택 사항)
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to execute activate.bat. Check the path and Conda environment.
    pause
    goto :eof
)
echo Conda environment activated successfully.

echo Starting Private DevBOT RAG Server
uvicorn.exe main:app --host 0.0.0.0 --port 8125