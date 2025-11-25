@echo off

set CONDA_ROOT=D:\conda

set ENV_NAME=daxue

set SERVER_FILE=server.py



cd /d "%~dp0"



echo [Step 1] Activating Conda environment...

if not exist "%CONDA_ROOT%\Scripts\activate.bat" (

? ? echo Error: Cannot find activate.bat

? ? pause

? ? exit /b

)

call "%CONDA_ROOT%\Scripts\activate.bat" %ENV_NAME%



echo [Step 2] Starting Server (Debug Mode)...

echo Please check 'server_debug.log' if browser does not open.

echo.



python %SERVER_FILE%



echo.

echo Server stopped.

pause