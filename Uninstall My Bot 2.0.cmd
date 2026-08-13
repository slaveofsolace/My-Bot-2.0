@echo off
setlocal
set "INSTALLER=%~dp0tools\install_local_runtime.py"
where py.exe >nul 2>nul
if not errorlevel 1 (
  py.exe -3 "%INSTALLER%" --uninstall %*
) else (
  python.exe "%INSTALLER%" --uninstall %*
)
if errorlevel 1 (
  echo.
  echo My Bot 2.0 was not removed. Review the error above.
  pause
  exit /b 1
)
echo My Bot 2.0 was removed for this Windows user.
pause
