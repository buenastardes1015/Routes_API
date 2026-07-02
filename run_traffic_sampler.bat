@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%"

"C:\Users\praut\AppData\Local\Programs\Python\Launcher\py.exe" -3 "%SCRIPT_DIR%traffic_sampler.py" >> "%SCRIPT_DIR%traffic_scheduler.log" 2>&1
set "EXIT_CODE=%ERRORLEVEL%"

popd
exit /b %EXIT_CODE%
