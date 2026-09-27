FROM python:3.11-slim

WORKDIR /app

# 安装依赖（requirements.txt 为 -e ./backend，与本地一致）
COPY requirements.txt /app/requirements.txt
COPY backend /app/backend
COPY prompts /app/prompts
RUN pip install --no-cache-dir -r /app/requirements.txt

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]