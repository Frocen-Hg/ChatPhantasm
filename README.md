# Chat Phantasm

本项目为为基于deepseek的，通过提示词进行人格模仿的小型项目。

主人格为**影子（Phantasm）**，他说话幽默、偶尔腹黑，有猫耳和触手。

## 项目结构

```
ChatPhantasm/
├── main_cli.py           # 终端版入口
├── main_web.py           # 网页版入口（FastAPI）
├── core/                 # 共享核心
│   ├── chat_engine.py    #   聊天引擎（调用 DeepSeek）
│   ├── config.py         #   配置加载（读 .env + settings.json）
│   └── logger.py         #   对话日志（JSONL）
├── cli/                  # CLI 专属
│   └── ui.py             #   终端打字效果
├── web/                  # Web 专属
│   ├── index.html        #   Vue 3 前端页面
│   └── static/           #   静态资源（头像等）
├── prompts/
│   └── phantasm_v1.txt   # 角色扮演提示词
├── settings.json         # 模型参数配置
├── .env                  # API Key（不入仓）
├── .env.example          # Key 模板
└── requirements.txt
```



## 前置要求

- **Python** ≥ 3.11（开发使用 3.11.9）
- **DeepSeek API Key** → [platform.deepseek.com](https://platform.deepseek.com/api_keys)



## 快速开始

1. 克隆项目

`git clone git@github.com:Frocen-Hg/ChatPhantasm.git`

2. 安装虚拟环境
  `python -m venv .venv`

3. 启动虚拟环境

  | Shell      | 命令                            |
  | ---------- | ------------------------------- |
  | PowerShell | `.venv\Scripts\Activate.ps1`    |
  | Git Bash   | `source .venv/Scripts/activate` |
  | cmd        | `.venv\Scripts\activate.bat`    |

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

## 技术栈

| 层   | 技术                            |
| ---- | ------------------------------- |
| AI   | DeepSeek API（OpenAI SDK 兼容） |
| 后端 | FastAPI + Uvicorn               |
| 前端 | Vue 3 + Tailwind CSS            |
| CLI  | 纯 Python                       |