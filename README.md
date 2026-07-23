# Chat Phantasm

本项目为为基于deepseek的，通过提示词进行人格模仿的小型项目

## 如何安装代码环境

1. 确定python版本
`python --version`
python环境采用3.11.9，不建议过低

2. 安装虚拟环境
`python -m venv .venv`

3. 启动虚拟环境
`.\.venv\Scripts\Activate.ps1`

4. 安装依赖
`pip install -r .\requirements.txt`

5. 启动程序
命令行对话窗口从main_cli.py启动
网页版对话窗口从main_api.py启动

## 一些简单的调用关系

| 文件 | 被谁调用 | 用途 |
|---|---|---|
| settings.json | config.py | 提供模型参数和 prompt 路径 |
| config.py | chat_engine.py | 加载配置，暴露 DEEPSEEK_API_KEY、BASE_URL、CONFIG |
| logger.py | chat_engine.py | 记录对话到 JSONL 日志 |
| ui.py | main_cli.py | 终端打字效果和清屏 |