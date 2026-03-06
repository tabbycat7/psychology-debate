"""
应用配置文件
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """基础配置"""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///debate.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

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

    # 反驳模型名称列表 —— 每次辩论随机抽取其中一个
    REFUTE_MODEL_NAMES = [
        'gpt-4o',
        'claude-3-sonnet',
        'deepseek-chat',
    ]
