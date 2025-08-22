@echo off
setlocal enabledelayedexpansion
rem Resolve BASE to yyy/ (parent of scripts/)
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%.." >nul 2>nul
set "BASE=%CD%\"
popd >nul 2>nul

rem Prefer venv Python if present, else fallback to system Python
set "PYEXE=%BASE%venv\Scripts\python.exe"
set "PYCMD=%PYEXE%"
if not exist "%PYEXE%" (
  rem Try system python
  for /f "delims=" %%P in ('where python 2^>nul') do (
    set "PYCMD=\"%%P\""
    goto :got_py
  )
  for /f "delims=" %%P in ('where py 2^>nul') do (
    set "PYCMD=py -3"
    goto :got_py
  )
  set "PYCMD=python"
)
:got_py
echo [INFO] Using Python: %PYCMD%

rem Paths
set "SCENES=%BASE%src\scenes"
set "MAIN=%BASE%main.py"
set "GUI_MAIN=%BASE%tk_main.py"

if not exist "%MAIN%" (
  echo [ERROR] main.py not found at %MAIN%
  exit /b 1
)
if not exist "%GUI_MAIN%" (
  echo [ERROR] tk_main.py not found at %GUI_MAIN%
  exit /b 1
)
if not exist "%SCENES%" (
  echo [WARN] Scenes folder not found at %SCENES% (build will continue without data)
)

rem Build CLI (main.py) into a single exe named COMOS-CLI.exe
%PYCMD% -m PyInstaller --noconfirm --clean --onefile --name COMOS-CLI ^
  --add-data "%SCENES%;scenes" ^
  --add-data "%SCENES%;yyy/scenes" ^
  "%MAIN%"

if errorlevel 1 (
  echo [ERROR] Build failed.
  exit /b 1
)

echo.
echo Build success. CLI EXE at: %BASE%dist\COMOS-CLI.exe

rem Build GUI (tk_main.py) into a windowed single exe named COMOS-GUI.exe
rem 注意：运行时会在 scenes_roots() 中查找 scenes 与 yyy/scenes，两处皆打包。
%PYCMD% -m PyInstaller --noconfirm --clean --onefile --windowed --name COMOS-GUI ^
  --add-data "%SCENES%;scenes" ^
  --add-data "%SCENES%;yyy/scenes" ^
  "%GUI_MAIN%"

if errorlevel 1 (
  echo [ERROR] GUI Build failed.
  exit /b 1
)

echo.
echo Build success. GUI EXE at: %BASE%dist\COMOS-GUI.exe
endlocal
