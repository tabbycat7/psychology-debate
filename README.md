# 心理测评辩论平台

基于 Flask + SQLAlchemy + 大模型 API 的青少年心理测评辩论系统。

---

## 快速部署（推荐：Docker）

### 前置要求
- Docker + Docker Compose（[安装文档](https://docs.docker.com/get-docker/)）

### 方式一：内置 MySQL（推荐，无需提前准备数据库）

```bash
# 1. 克隆仓库
git clone <your-repo-url>
cd TL_Psychology

# 2. 配置环境变量
cp app/env.example app/.env
# 编辑 app/.env，填写 ENHANCE_MODEL_API_KEY、REFUTE_MODEL_API_KEY
# DATABASE_URL 保持默认即可（已指向内置 MySQL 容器）

# 3. 一键启动（会同时启动 MySQL 容器和 Web 容器）
docker-compose up -d

# 4. 访问
# 浏览器打开 http://localhost:5000
```

> 数据库和表会**自动创建**，MySQL 数据持久化在 Docker volume `mysql_data` 中，容器重建后数据不丢失。

### 方式二：使用已有 MySQL 服务器

```bash
# app/.env 中修改 DATABASE_URL，指向你的 MySQL 服务器
DATABASE_URL=mysql+pymysql://用户名:密码@主机地址:3306/数据库名

# 只启动 web 服务（跳过内置 MySQL 容器）
docker-compose up -d web
```

### 停止 / 重启

```bash
docker-compose down        # 停止并删除容器（数据保留）
docker-compose restart     # 重启
docker-compose logs -f     # 查看日志
```

---

## 本地开发（无 Docker）

### 前置要求
- Python 3.11+

### 步骤

```bash
# 1. 进入应用目录
cd app

# 2. 创建虚拟环境并安装依赖
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt

# 3. 配置环境变量
cp env.example .env
# 编辑 .env，填写 API 密钥

# 4. 启动开发服务器
python app.py
# 访问 http://localhost:5000
```

数据库和表会在**首次启动时自动创建**，无需额外操作。

---

## 环境变量说明（app/.env）

| 变量名 | 说明 | 默认值 |
|---|---|---|
| `SECRET_KEY` | Flask Session 密钥 | `dev-secret-key` |
| `DATABASE_URL` | 数据库连接串 | `sqlite:///debate.db` |
| `ENHANCE_MODEL_API_URL` | 加持模型 API 地址 | - |
| `ENHANCE_MODEL_API_KEY` | 加持模型 API 密钥 | - |
| `ENHANCE_MODEL_NAME` | 加持模型名称 | `gpt-4o-mini` |
| `REFUTE_MODEL_API_URL` | 反驳模型 API 地址 | - |
| `REFUTE_MODEL_API_KEY` | 反驳模型 API 密钥 | - |

使用 MySQL 示例：
```
DATABASE_URL=mysql+pymysql://user:password@host:3306/debate_db
```

---

## 项目结构

```
TL_Psychology/
├── app/
│   ├── app.py          # Flask 主应用 & 路由
│   ├── config.py       # 配置项
│   ├── models.py       # 数据库模型
│   ├── questions.py    # 辩题数据
│   ├── llm_api.py      # 大模型 API 调用
│   ├── requirements.txt
│   ├── env.example     # 环境变量模板
│   ├── static/         # CSS / JS
│   └── templates/      # HTML 模板
├── Dockerfile
├── docker-compose.yml
└── README.md
```
