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

    # "反驳"模型配置 —— 用于反驳学生观点（支持多个模型，随机抽取）
    # 每个模型配置格式: {"name": "模型名称", "api_url": "...", "api_key": "...", "model": "..."}
    REFUTE_MODELS = [
        {
            "name": "反驳模型A",
            "api_url": os.environ.get('REFUTE_MODEL_A_API_URL', 'https://api.example.com/v1/chat/completions'),
            "api_key": os.environ.get('REFUTE_MODEL_A_API_KEY', 'your-refute-a-api-key'),
            "model": os.environ.get('REFUTE_MODEL_A_NAME', 'gpt-4o'),
        },
        {
            "name": "反驳模型B",
            "api_url": os.environ.get('REFUTE_MODEL_B_API_URL', 'https://api.example.com/v1/chat/completions'),
            "api_key": os.environ.get('REFUTE_MODEL_B_API_KEY', 'your-refute-b-api-key'),
            "model": os.environ.get('REFUTE_MODEL_B_NAME', 'claude-3-sonnet'),
        },
        {
            "name": "反驳模型C",
            "api_url": os.environ.get('REFUTE_MODEL_C_API_URL', 'https://api.example.com/v1/chat/completions'),
            "api_key": os.environ.get('REFUTE_MODEL_C_API_KEY', 'your-refute-c-api-key'),
            "model": os.environ.get('REFUTE_MODEL_C_NAME', 'deepseek-chat'),
        },
    ]
