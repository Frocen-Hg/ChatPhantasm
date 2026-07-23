import os
import json
import datetime

class ChatLogger:

    # init是用于定义对象的初始状态的方法，
    def __init__(self, log_dir="logs"):
        self.log_dir = log_dir # 设置日志存储目录
        # 检查日志目录是否存在，如果不存在则创建它
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
        today = datetime.date.today()
        # 创建可读日志文件和数据日志文件的路径
        self.human_log = os.path.join(self.log_dir, f"{today}.log")
        self.data_log = os.path.join(self.log_dir, f"{today}.jsonl")

    def log_chat(self, message_dict):
        """记录聊天消息到日志文件和数据文件"""
        # 1. 将消息记录到JSONL数据文件
        with open(self.data_log, "a", encoding="utf-8") as f:
            # 将message_dict转换为JSON字符串并写入文件
            # ensure_ascii=False: 允许保存非ASCII字符（如中文）
            # 添加换行符\n: 确保每条记录在文件中单独一行（JSON Lines格式）
            f.write(json.dumps(message_dict, ensure_ascii=False) + "\n")
        # 时分秒的标准时间
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        # 从message_dict中提取角色role并转换为大写，增强可读性
        role = message_dict['role'].upper()
        # 提取消息内容
        content = message_dict['content']
        # 写入人类可读的日志文件
        with open(self.human_log, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {role}: {content}\n")