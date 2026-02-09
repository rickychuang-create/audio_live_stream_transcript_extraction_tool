"""
配置管理模組
負責讀取和管理環境變數、API 金鑰、模型設定等配置
"""
import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings


def find_env_file():
    """
    查找 .env 文件
    優先順序：
    1. 當前工作目錄的 .env
    2. backend 目錄的 .env
    3. 項目根目錄的 .env（向上查找）
    
    Returns:
        str: .env 文件的路徑，如果找不到則返回項目根目錄的 .env
    """
    # 獲取當前文件所在目錄（backend/app/config.py）
    current_file = Path(__file__)
    # backend 目錄
    backend_dir = current_file.parent.parent
    # 項目根目錄（backend 的父目錄）
    root_dir = backend_dir.parent
    
    # 按優先順序查找 .env 文件
    env_locations = [
        Path.cwd() / ".env",  # 當前工作目錄
        backend_dir / ".env",  # backend 目錄
        root_dir / ".env",  # 項目根目錄
    ]
    
    for env_path in env_locations:
        if env_path.exists():
            print(f"[DEBUG] 找到 .env 文件: {env_path}")
            return str(env_path)
    
    # 如果都沒找到，返回項目根目錄的 .env（讓 pydantic 處理）
    print(f"[WARNING] 未找到 .env 文件，將使用項目根目錄: {root_dir / '.env'}")
    return str(root_dir / ".env")


class Settings(BaseSettings):
    """應用程式配置類別"""
    
    # API 金鑰配置
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    
    # Whisper 模型配置
    WHISPER_MODEL: str = "base"  # 可選: tiny, base, small, medium, large
    
    # 檔案處理配置
    MAX_FILE_SIZE: int = 500 * 1024 * 1024  # 500MB (單位: bytes)
    UPLOAD_DIR: str = "uploads"
    OUTPUT_DIR: str = "outputs"
    
    # 應用程式配置
    API_TITLE: str = "語音直播切片工具 API"
    API_VERSION: str = "1.0.0"
    DEBUG: bool = False
    # 是否啟用標點符號處理（預設關閉，避免模型問題影響主流程）
    ENABLE_PUNCTUATION: bool = True
    
    # LLM 配置
    DEFAULT_LLM_PROVIDER: str = "openai"  # openai、anthropic 或 gemini
    OPENAI_MODEL: str = "gpt-4.1"  # 使用的 OpenAI 模型
    ANTHROPIC_MODEL: str = "claude-3-haiku-20240307"  # 使用的 Claude 模型
    GEMINI_MODEL: str = "gemini-2.5-flash"  # 使用的 Gemini 模型（gemini-pro 已棄用，改用 gemini-1.5-flash）
    
    class Config:
        env_file_encoding = "utf-8"
        case_sensitive = True


# 查找 .env 文件並建立全域設定實例
env_file_path = find_env_file()
settings = Settings(_env_file=env_file_path)

# 調試信息：顯示配置讀取情況（不顯示完整的 API 金鑰）
print(f"[DEBUG] 配置讀取完成:")
print(f"  - .env 文件位置: {env_file_path}")
print(f"  - DEFAULT_LLM_PROVIDER: {settings.DEFAULT_LLM_PROVIDER}")
print(f"  - OPENAI_API_KEY: {'已設定' if settings.OPENAI_API_KEY else '未設定'}")
print(f"  - ANTHROPIC_API_KEY: {'已設定' if settings.ANTHROPIC_API_KEY else '未設定'}")
print(f"  - GEMINI_API_KEY: {'已設定' if settings.GEMINI_API_KEY else '未設定'}")

# 確保必要的目錄存在
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
