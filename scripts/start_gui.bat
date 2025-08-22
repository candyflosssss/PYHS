@echo off
setlocal
set PY=%~dp0venv\Scripts\python.exe
set APP=%~dp0tk_main.py
"%PY%" "%APP%"
endlocal
