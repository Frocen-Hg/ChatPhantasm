# Chat Phantasm

基于 DeepSeek API 的虚拟人格扮演项目。你将与 **影子（Phantasm）**——一位住在你终端里的虚拟主播对话。他说话幽默、偶尔腹黑，有猫耳和触手，是你的粉丝朋友。

---

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

---

## 前置要求

- **Python** ≥ 3.11（开发使用 3.11.9）
- **DeepSeek API Key** → [platform.deepseek.com](https://platform.deepseek.com/api_keys)

---

## 快速开始

### 1. 克隆项目

```bash
git clone git@github.com:Frocen-Hg/ChatPhantasm.git
cd ChatPhantasm
```

### 2. 配置 API Key

```bash
cp .env.example .env
```

然后编辑 `.env`，将 `sk-你的API密钥` 替换为你的真实 Key。

### 3. 创建虚拟环境

```bash
python -m venv .venv
```

### 4. 激活虚拟环境

| Shell | 命令 |
|-------|------|
| PowerShell | `.venv\Scripts\Activate.ps1` |
| Git Bash | `source .venv/Scripts/activate` |
| cmd | `.venv\Scripts\activate.bat` |

### 5. 安装依赖

```bash
pip install -r requirements.txt
```

### 6. 启动

```bash
# 终端版（命令行对话）
python main_cli.py

# 网页版（浏览器对话，自动打开 http://127.0.0.1:8000）
python main_web.py
```

---

## 配置说明

`settings.json`：

| 字段 | 含义 | 默认值 |
|------|------|--------|
| `model_settings.model` | 使用的模型 | `deepseek-chat` |
| `model_settings.temperature` | 回复随机性（0-2） | `1.3` |
| `model_settings.max_tokens` | 最大回复长度 | `2000` |
| `phantasm_setup.system_prompt` | 角色提示词文件路径 | `prompts/phantasm_v1.txt` |

---

## 角色设定

**影子（Phantasm）**，25 岁，INTP。

B站杂谈势虚拟主播，紫色中长发，猫耳，章鱼触手，显示器眼镜。说话温柔幽默，偶尔腹黑嘴碎。粉丝名"影子菜"，MBTI 猜测准确率 3%（经常被群友拿这个迫害）。中二时期网名"随风之魔"（已被群友收录为永久黑历史）。

---

## 技术栈

| 层 | 技术 |
|----|------|
| AI | DeepSeek API（OpenAI SDK 兼容） |
| 后端 | FastAPI + Uvicorn |
| 前端 | Vue 3 + Tailwind CSS |
| CLI | 纯 Python |
