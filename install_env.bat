@echo off
echo [1/3] 正在检查 Python 环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: 未检测到 Python，请先安装 Python 并添加到环境变量!
    pause
    exit
)

echo [2/3] 正在创建虚拟环境 (.venv)...
python -m venv .venv

echo [3/3] 正在安装依赖包 (可能需要几分钟)...
call .venv\Scripts\activate
pip install -r requirements.txt


pause