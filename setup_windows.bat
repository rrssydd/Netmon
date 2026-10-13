@echo off
cd /d "%~dp0"

where py >nul 2>nul
if not errorlevel 1 (
    py -3 -m venv .venv
) else (
    python -m venv .venv
)
if errorlevel 1 goto failed

".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto failed

".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed

echo.
echo Setup selesai. Jalankan start_windows.bat untuk membuka Netmon.
pause
exit /b 0

:failed
echo.
echo Setup gagal. Pastikan Python 3 sudah terpasang dan komputer terhubung ke internet.
pause
exit /b 1
