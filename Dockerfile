# ============================================================
# 心理测评辩论平台 Docker 镜像
# ============================================================
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 安装依赖
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir gunicorn

# 复制项目文件
COPY app/ .

# 暴露端口
EXPOSE 5000

# 使用 gunicorn 启动（生产模式）
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "120", "app:app"]
