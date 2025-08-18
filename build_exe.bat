@echo off
setlocal
set ROOT=%~dp0
set PYEXE=%ROOT%venv\Scripts\python.exe
if not exist "%PYEXE%" (
  echo [ERROR] venv Python not found: %PYEXE%
  echo Please adjust PYEXE or activate your venv and run PyInstaller manually.
  exit /b 1
)

rem Build CLI (main.py) into a single exe named COMOS-CLI.exe
"%PYEXE%" -m PyInstaller --noconfirm --clean --onefile --name COMOS-CLI ^
  --add-data "%ROOT%scenes;scenes" ^
  "%ROOT%main.py"

if errorlevel 1 (
  echo [ERROR] Build failed.
  exit /b 1
)

echo.
echo Build success. EXE at: %ROOT%dist\COMOS-CLI.exe
endlocal
