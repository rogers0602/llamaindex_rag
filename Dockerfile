FROM python:3.10-slim

WORKDIR /app

# 安装系统依赖 (pgvector 需要编译环境)
RUN apt-get update && apt-get install -y \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖
COPY requirements.txt .
# 使用清华源加速
RUN pip install --no-cache-dir -r requirements.txt
# RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 🔥 关键：把本地模型 copy 进去，实现离线运行
# 假设你在项目根目录有个 models 文件夹，或者你按之前的教程放在 backend/models
COPY ./models /app/models

# 复制业务代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动
CMD ["python", "main.py"]