import os
import webbrowser
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles # 新增：用于托管静态文件
from fastapi.responses import FileResponse # 新增：用于返回 HTML
from pydantic import BaseModel
from core import PhantasmChat
import uvicorn
from threading import Timer # 新增：用于延迟打开浏览器
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
import json

# --- FastAPI 应用初始化 ---
app = FastAPI(title="Phantasm Terminal")
app.mount("/static", StaticFiles(directory="web/static"), name="static")

# --- 1. 初始化引擎 ---
chat_engine = PhantasmChat()

class ChatMessage(BaseModel):
    content: str

# --- 2. 挂载 API 路由 ---
@app.post("/chat")
async def chat_endpoint(msg: ChatMessage):
    try:
        reply = chat_engine.get_response(msg.content)
        return {"role": "assistant", "content": reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- 3. 【核心】静态资源与页面分发 ---
# 假设你的 index.html 就在当前目录下
@app.get("/")
async def read_index():
    return FileResponse('web/index.html')

# 如果你以后有图片文件夹 assets，可以这样挂载：
# app.mount("/assets", StaticFiles(directory="assets"), name="assets")

# --- 4. 自动打开浏览器逻辑 ---
def open_browser():
    webbrowser.open("http://127.0.0.1:8000")

if __name__ == "__main__":
    # 使用 Timer 延迟 2.5 秒打开浏览器，确保后端服务已经完全启动
    Timer(2.5, open_browser).start()
    uvicorn.run(app, host="127.0.0.1", port=8000)

    # 这是文档 http://127.0.0.1:8000/docs
