@echo off
setlocal enabledelayedexpansion

rem 切换到当前脚本所在的目录
cd /d "%~dp0"

set YML_FILE=environment.yml

echo [Step 1] Auto-detecting Conda installation...

rem --- 自动定义可能的路径列表 (优先级从上到下) ---
rem 你可以在这里添加更多可能的路径
set "POSSIBLE_PATHS=D:\conda;%USERPROFILE%\anaconda3;%USERPROFILE%\miniconda3;C:\ProgramData\anaconda3;C:\ProgramData\miniconda3;C:\anaconda3;C:\miniconda3"

set "CONDA_ROOT="

rem --- 循环检查路径 ---
for %%p in ("%POSSIBLE_PATHS:;=" "%") do (
    set "CHECK_PATH=%%~p"
    if exist "!CHECK_PATH!\Scripts\activate.bat" (
        set "CONDA_ROOT=!CHECK_PATH!"
        goto :Found
    )
)

rem --- 如果循环结束没找到，尝试检查系统PATH里的conda ---
where conda >nul 2>nul
if %errorlevel% equ 0 (
    echo Found 'conda' in system PATH.
    rem 此时不需要设置 CONDA_ROOT，直接继续即可，但为了稳妥还是建议找到 activate
    goto :SystemPathFound
)

:NotFound
echo.
echo [Error] Could not find Anaconda or Miniconda automatically.
echo Please install Conda or add it to your System PATH.
pause
exit /b

:Found
echo [Success] Found Conda at: !CONDA_ROOT!
call "!CONDA_ROOT!\Scripts\activate.bat"
goto :CreateEnv

:SystemPathFound
echo [Info] Using system global Conda...
rem 尝试激活 base (如果能在PATH里找到activate)
call activate base
goto :CreateEnv

:CreateEnv
echo.
echo [Step 2] Creating Environment from %YML_FILE%...

if not exist "%YML_FILE%" (
    echo [Error] %YML_FILE% not found in the current folder!
    pause
    exit /b
)

rem 执行创建命令
conda env create -f %YML_FILE%

echo.
echo ---------------------------------------------------
if %errorlevel% equ 0 (
    echo [Done] Environment created successfully!
    echo.
    echo To start, you can assume the environment name is inside the yml file.
) else (
    echo [Warning] Something went wrong. 
    echo If it says "prefix already exists", the environment is already there.
)
echo ---------------------------------------------------

pause