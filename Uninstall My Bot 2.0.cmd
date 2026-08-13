@echo off
setlocal
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\Install-LocalRuntime.ps1" -Uninstall %*
if errorlevel 1 (
  echo.
  echo My Bot 2.0 was not removed. Review the error above.
  pause
  exit /b 1
)
echo My Bot 2.0 was removed for this Windows user.
pause

