"""
檔案處理工具模組
負責檔案上傳、驗證、儲存等操作
"""
import os
import uuid
import hashlib
from pathlib import Path
from typing import Optional, Tuple
from fastapi import UploadFile, HTTPException
from app.config import settings


def generate_file_id() -> str:
    """
    生成唯一的檔案 ID
    
    Returns:
        str: 唯一的檔案識別碼
    """
    return str(uuid.uuid4())


def get_file_hash(file_path: str) -> str:
    """
    計算檔案的 MD5 雜湊值
    
    Args:
        file_path: 檔案路徑
        
    Returns:
        str: MD5 雜湊值
    """
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def validate_file(file: UploadFile) -> Tuple[bool, Optional[str]]:
    """
    驗證上傳的檔案
    
    Args:
        file: 上傳的檔案物件
        
    Returns:
        Tuple[bool, Optional[str]]: (是否有效, 錯誤訊息)
    """
    # 檢查檔案類型（支援 MP4 和 MP3，避免使用者上傳非影音檔）
    allowed_extensions = {".mp4", ".MP4", ".mp3", ".MP3"}
    file_ext = Path(file.filename).suffix if file.filename else ""
    
    if file_ext not in allowed_extensions:
        return False, f"不支援的檔案格式。僅支援: {', '.join(allowed_extensions)}"

    # ⚠️ 目前「不再限制檔案大小」
    # 原本這裡會依照 settings.MAX_FILE_SIZE 檢查檔案大小，
    # 但因實際使用情境 MP4 影片常常超過預設 500MB，
    # 為了避免上傳被直接擋掉，先完全關閉大小限制。
    #
    # 若未來希望重新啟用大小限制，可以參考以下範例邏輯：
    # if settings.MAX_FILE_SIZE and settings.MAX_FILE_SIZE > 0:
    #     if hasattr(file, "size") and file.size and file.size > settings.MAX_FILE_SIZE:
    #         return False, f"檔案大小超過限制 ({settings.MAX_FILE_SIZE / 1024 / 1024}MB)"

    return True, None


async def save_uploaded_file(file: UploadFile, file_id: str) -> str:
    """
    儲存上傳的檔案
    
    Args:
        file: 上傳的檔案物件
        file_id: 檔案 ID
        
    Returns:
        str: 儲存的檔案路徑
    """
    # 取得原始檔案副檔名（預設為 .mp4，但如果是 MP3 則保留 .mp3）
    file_ext = Path(file.filename).suffix if file.filename else ".mp4"
    
    # 建立儲存路徑
    save_path = Path(settings.UPLOAD_DIR) / f"{file_id}{file_ext}"
    
    # 確保目錄存在
    save_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 儲存檔案
    with open(save_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    return str(save_path)


def get_file_path(file_id: str, extension: str = ".mp4") -> str:
    """
    根據檔案 ID 取得檔案路徑
    
    Args:
        file_id: 檔案 ID
        extension: 檔案副檔名
        
    Returns:
        str: 檔案路徑
    """
    return str(Path(settings.UPLOAD_DIR) / f"{file_id}{extension}")


def get_output_path(file_id: str, extension: str = ".txt") -> str:
    """
    根據檔案 ID 取得輸出檔案路徑
    
    Args:
        file_id: 檔案 ID
        extension: 檔案副檔名
        
    Returns:
        str: 輸出檔案路徑
    """
    output_path = Path(settings.OUTPUT_DIR) / f"{file_id}{extension}"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return str(output_path)


def file_exists(file_path: str) -> bool:
    """
    檢查檔案是否存在
    
    Args:
        file_path: 檔案路徑
        
    Returns:
        bool: 檔案是否存在
    """
    return os.path.exists(file_path) and os.path.isfile(file_path)


def delete_file(file_path: str) -> bool:
    """
    刪除檔案
    
    Args:
        file_path: 檔案路徑
        
    Returns:
        bool: 是否成功刪除
    """
    try:
        if file_exists(file_path):
            os.remove(file_path)
            return True
        return False
    except Exception:
        return False
