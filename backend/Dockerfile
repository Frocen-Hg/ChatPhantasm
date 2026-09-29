FROM python:3.11-slim

WORKDIR /app

# 安装依赖（requirements.txt 为 -e ./backend，与本地一致）
# 可通过 --build-arg PIP_INDEX_URL=国内镜像 加速
ARG PIP_INDEX_URL=https://pypi.org/simple
COPY requirements.txt /app/requirements.txt
COPY backend /app/backend
COPY prompts /app/prompts
RUN pip install --no-cache-dir -i ${PIP_INDEX_URL} -r /app/requirements.txt

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]