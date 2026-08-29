@echo off
cd /d "%~dp0"
python build.py %*
set BUILD_EXIT_CODE=%ERRORLEVEL%
echo.
if not "%BUILD_EXIT_CODE%"=="0" (
    echo Build failed. Exit code: %BUILD_EXIT_CODE%
)
pause
exit /b %BUILD_EXIT_CODE%
