@echo off
rem Start OneButton (Windows). The Python launcher restarts the loop after updates or crashes.
setlocal
set "HERE=%~dp0.."
set "ONEBUTTON_HOME=%HERE%"
chcp 65001 >nul
if exist "%HERE%\.venv\Scripts\python.exe" (
  "%HERE%\.venv\Scripts\python.exe" -m onebutton.launcher %*
) else (
  python -m onebutton.launcher %*
)
