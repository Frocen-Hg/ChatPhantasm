@echo off
echo 影子正在苏醒...
set "VIRTUAL_ENV=.venv"
if not exist "%VIRTUAL_ENV%" (
    echo 错误: 未找到虚拟环境，请先运行 install_env.bat
    pause
    exit
)

:: 激活虚拟环境并运行后端
call .venv\Scripts\activate
python main_api.py

pause