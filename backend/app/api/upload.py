"""
檔案上傳處理模組
處理單個檔案上傳
"""
from fastapi import UploadFile, HTTPException
from app.models.schemas import UploadResponse
from app.utils.file_handler import (
    generate_file_id, validate_file, save_uploaded_file
)


async def handle_upload(file: UploadFile) -> UploadResponse:
    """
    處理單個檔案上傳
    
    Args:
        file: 上傳的檔案物件
        
    Returns:
        UploadResponse: 上傳結果
    """
    # 驗證檔案
    is_valid, error_msg = validate_file(file)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    
    # 生成檔案 ID
    file_id = generate_file_id()
    
    # 儲存檔案
    file_path = await save_uploaded_file(file, file_id)
    
    # 取得檔案大小
    import os
    file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
    
    return UploadResponse(
        file_id=file_id,
        filename=file.filename or "unknown",
        file_size=file_size,
        message="檔案上傳成功"
    )


