@echo off
REM اجرای کامل کَلَم در ویندوز
REM   run_windows.bat "C:\Users\...\starcoach-dataset-v16-cap300-csv.zip"   (ساخت پایگاه داده از zip و اجرا)
REM   run_windows.bat                                                         (اجرا با پایگاه داده‌ای که قبلاً ساخته شده)
chcp 65001 >nul
cd /d "%~dp0"

python -m pip install -r requirements.txt || goto :error

if not "%~1"=="" (
    python scripts\build_db.py "%~1" || goto :error
)

if not exist torob.db (
    echo torob.db not found. Run: run_windows.bat "path\to\dataset.zip"
    exit /b 1
)

start "" http://127.0.0.1:8000/
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
exit /b 0

:error
echo.
echo Failed. See the error above.
exit /b 1