@echo off
echo 请选择启动模式:
echo   1. 启动服务器 (玩家1)
echo   2. 启动客户端 (玩家2)
echo   3. 同时启动两个窗口 (本地双人)
echo   4. 退出
echo.
set /p choice=请输入选择 (1-4): 

if "%choice%"=="1" (
    echo 启动服务器...
    "c:\Users\MoSaki\PYHS\yyy\venv\Scripts\python.exe" "c:\Users\MoSaki\PYHS\yyy\main.py" server
) else if "%choice%"=="2" (
    echo 启动客户端...
    "c:\Users\MoSaki\PYHS\yyy\venv\Scripts\python.exe" "c:\Users\MoSaki\PYHS\yyy\main.py" client
) else if "%choice%"=="3" (
    echo 启动双人模式...
    start "服务器" cmd /c ""c:\Users\MoSaki\PYHS\yyy\venv\Scripts\python.exe" "c:\Users\MoSaki\PYHS\yyy\main.py" server"
    timeout /t 2 /nobreak > nul
    start "客户端" cmd /c ""c:\Users\MoSaki\PYHS\yyy\venv\Scripts\python.exe" "c:\Users\MoSaki\PYHS\yyy\main.py" client"
) else if "%choice%"=="4" (
    echo 再见!
    exit
) else (
    echo 无效选择
    pause
    goto start
)

pause
