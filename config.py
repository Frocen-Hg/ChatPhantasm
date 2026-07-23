import os
import json
from dotenv import load_dotenv

# 1. 立即加载环境变量
load_dotenv()

# 2. 【核心修复】在全局作用域定义变量，以便外部 import
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
BASE_URL = "https://api.deepseek.com"

# 定义配置文件的绝对路径，防止路径地狱
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(BASE_DIR, "settings.json")

def _load_settings():
    """内部函数：加载并解析配置文件"""
    if not os.path.exists(SETTINGS_PATH):
        raise FileNotFoundError(f"配置文件缺失: {SETTINGS_PATH}")
        
    with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
    
    # 读取外部 prompt 文件内容并注入到字典中
    prompt_rel_path = config["phantasm_setup"]["system_prompt"]
    prompt_full_path = os.path.join(BASE_DIR, prompt_rel_path)
    
    with open(prompt_full_path, "r", encoding="utf-8") as f:
        config["phantasm_setup"]["system_prompt"] = f.read()
        
    return config

# 3. 【核心修复】将加载后的字典也暴露给全局
CONFIG = _load_settings()

# 验证 Key 是否存在
if not DEEPSEEK_API_KEY:
    raise ValueError("环境变量中缺失 DEEPSEEK_API_KEY，请检查 .env 文件")