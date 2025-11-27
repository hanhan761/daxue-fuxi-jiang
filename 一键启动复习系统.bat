@echo off

rem =======================================================
rem  [核心修复] 这里修改了你的 Conda 安装路径
rem  根据之前的日志，你的 Anaconda 在 D:\software\anaconda3
rem =======================================================
set CONDA_ROOT=D:\software\anaconda3

set ENV_NAME=daxue
set SERVER_FILE=server.py

rem 锚定当前目录
cd /d "%~dp0"

echo [Step 1] Activating Conda environment...

rem 检查启动脚本是否存在，如果找不到会打印出它试图去哪里找
if not exist "%CONDA_ROOT%\Scripts\activate.bat" (
    echo.
    echo [Error] Cannot find activate.bat
    echo We looked in: "%CONDA_ROOT%\Scripts\activate.bat"
    echo.
    echo Please check if your Anaconda path is correct.
    pause
    exit /b
)

rem 激活环境
call "%CONDA_ROOT%\Scripts\activate.bat" %ENV_NAME%

echo [Step 2] Starting Server (Debug Mode)...
echo Please check 'server_debug.log' if browser does not open.
echo.

rem 启动 Python 主程序
python %SERVER_FILE%

echo.
echo Server stopped.
pause