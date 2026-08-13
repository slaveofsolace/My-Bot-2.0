@echo off
setlocal
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\Install-LocalRuntime.ps1" %*
if errorlevel 1 (
  echo.
  echo My Bot 2.0 was not installed. Review the error above.
  pause
  exit /b 1
)
echo.
echo My Bot 2.0 is installed. Open Start and type: My Bot 2.0
pause

