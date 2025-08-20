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
  --add-data "%ROOT%scenes;yyy/scenes" ^
  "%ROOT%main.py"

if errorlevel 1 (
  echo [ERROR] Build failed.
  exit /b 1
)

echo.
echo Build success. CLI EXE at: %ROOT%dist\COMOS-CLI.exe

rem Build GUI (tk_main.py) into a windowed single exe named COMOS-GUI.exe
rem 注意：SimplePvEGame 通过 yyy/game_modes/..\scenes 查找资源，
rem 因此这里将场景目录打到 yyy/scenes 以匹配运行时相对路径。
"%PYEXE%" -m PyInstaller --noconfirm --clean --onefile --windowed --name COMOS-GUI ^
  --add-data "%ROOT%scenes;scenes" ^
  --add-data "%ROOT%scenes;yyy/scenes" ^
  "%ROOT%tk_main.py"

if errorlevel 1 (
  echo [ERROR] GUI Build failed.
  exit /b 1
)

echo.
echo Build success. GUI EXE at: %ROOT%dist\COMOS-GUI.exe
endlocal
