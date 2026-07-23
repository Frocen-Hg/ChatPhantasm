import os    # 必须导入
import json  # 必须导入
from openai import OpenAI
from .config import DEEPSEEK_API_KEY, BASE_URL, CONFIG
from .logger import ChatLogger

class PhantasmChat:
    def __init__(self):
        self.client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=BASE_URL)
        self.setup = CONFIG["phantasm_setup"]
        self.model_params = CONFIG["model_settings"]
        self.logger = ChatLogger()
        
        # 1. 定义地基
        self.system_message = {"role": "system", "content": self.setup["system_prompt"]}
        self.max_memory = 20
        
        # 2. 【核心修复】必须在这里调用加载函数！
        last_history = self._load_last_history()
        
        # 3. 组装记忆：系统设定 + 历史记录
        self.history = [self.system_message] + last_history

    def _load_last_history(self):
        """精准读取 JSONL 格式的历史记录"""
        # 注意：这里使用的是 logger.py 中定义的 data_log 路径
        data_file = self.logger.data_log
        if not os.path.exists(data_file):
            return []

        history = []
        try:
            with open(data_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        # 将 JSON 字符串转回字典
                        history.append(json.loads(line))
            
            # 这里的切片逻辑：只取最后 N 条
            return history[-10:]
        except Exception as e:
            print(f"（记忆突触受损）无法解析历史记录: {e}")
            return []

    def get_response(self, user_input: str) -> str:
        # 构造并记录用户消息
        user_msg = {"role": "user", "content": user_input}
        self.history.append(user_msg)
        self.logger.log_chat(user_msg)
        
        # 上下文修剪
        if len(self.history) > self.max_memory:
            self.history = [self.system_message] + self.history[-(self.max_memory-1):]

        try:
            response = self.client.chat.completions.create(
                model=self.model_params["model"],
                messages=self.history,
                temperature=self.model_params["temperature"]
            )
            
            # 获取对象
            assistant_msg_obj = response.choices[0].message
            
            # 【关键修复】强制转为字典
            msg_dict = {
                "role": "assistant", 
                "content": assistant_msg_obj.content
            }
            
            # 统一：存入内存历史的是字典，存入日志的也是字典
            self.history.append(msg_dict) 
            self.logger.log_chat(msg_dict)
            
            return msg_dict["content"]
            
        except Exception as e:
            # 【修复】错误记录也必须符合新的字典格式协议
            error_data = {"role": "system", "content": f"ERROR: {str(e)}"}
            self.logger.log_chat(error_data)
            return f"（终端闪烁红光）影子掉线了... 原因: {e}"
