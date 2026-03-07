"""
应用配置文件
"""
import os
from dotenv import load_dotenv

# 确保从 config.py 所在目录加载 .env 文件
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))


class Config:
    """基础配置"""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///debate.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ============================================================
    # 连接池配置（解决 MySQL 长时间空闲后断连的问题）
    # ============================================================
    SQLALCHEMY_ENGINE_OPTIONS = {
        # 每次从连接池取出连接前先 ping 一下，确认连接存活；若已断开则自动重连
        "pool_pre_ping": True,
        # 连接在池中最长存活 1800 秒（30 分钟），到期后回收重建
        # 必须小于 MySQL 的 wait_timeout（默认 28800 秒 = 8 小时）
        "pool_recycle": 1800,
        # 连接池大小
        "pool_size": 5,
        # 超出 pool_size 后允许的临时连接数
        "max_overflow": 10,
        # 获取连接超时时间（秒）
        "pool_timeout": 30,
    }

    # ============================================================
    # 大模型 API 配置
    # ============================================================

    # "加持"模型配置 —— 用于润色学生观点
    ENHANCE_MODEL_API_URL = os.environ.get('ENHANCE_MODEL_API_URL', 'https://api.example.com/v1/chat/completions')
    ENHANCE_MODEL_API_KEY = os.environ.get('ENHANCE_MODEL_API_KEY', 'your-enhance-api-key')
    ENHANCE_MODEL_NAME = os.environ.get('ENHANCE_MODEL_NAME', 'gpt-4o-mini')

    # "反驳"模型配置 —— 用于反驳学生观点（共用同一个 API，随机抽取不同模型）
    REFUTE_MODEL_API_URL = os.environ.get('REFUTE_MODEL_API_URL', 'https://api.example.com/v1/chat/completions')
    REFUTE_MODEL_API_KEY = os.environ.get('REFUTE_MODEL_API_KEY', 'your-refute-api-key')

    # "出题"模型配置 —— 每轮反驳后生成理解力选择题
    QUIZ_MODEL_API_URL = os.environ.get('QUIZ_MODEL_API_URL', os.environ.get('REFUTE_MODEL_API_URL', 'https://api.example.com/v1/chat/completions'))
    QUIZ_MODEL_API_KEY = os.environ.get('QUIZ_MODEL_API_KEY', os.environ.get('REFUTE_MODEL_API_KEY', 'your-quiz-api-key'))
    QUIZ_MODEL_NAME = os.environ.get('QUIZ_MODEL_NAME', 'gemini-3-pro-preview')

    # 反驳模型名称列表 —— 每次辩论随机抽取其中一个
    REFUTE_MODEL_NAMES = [
        'gpt-4o',
        'gpt-5.1',
        'gpt-5.2',
        'claude-opus-4-6',
        'claude-sonnet-4-5-20250929',
        'doubao-1-5-thinking-pro-250415',
        'doubao-seed-2-0-pro-260215',
        'gemini-2.5-pro',
        'gemini-3.1-pro-preview',
        'gemini-3-pro-preview',
        'deepseek-chat',
        'qwen3-max',
        'qwen-plus-2025-01-25',
        'grok-4',
        'deepseek-chat',
        'deepseek-reasoner'
    ]
