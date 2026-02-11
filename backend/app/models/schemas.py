"""
數據模型定義
使用 Pydantic 定義 API 請求和響應的數據結構
"""
from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class ContentFormat(str, Enum):
    """文案格式類型枚舉"""
    COMMUNITY_POST = "community_post"  # 社團文章
    EMAIL = "email"  # Email 文案
    YT_POST = "yt_post"  # YT 貼文（原為 YT Shorts 腳本）
    SUMMARY = "summary"  # 精華摘要
    SUBSTACK_ARTICLE = "substack_article"  # Substack 長文


class TaskStatus(str, Enum):
    """任務狀態枚舉"""
    PENDING = "pending"  # 等待中
    PROCESSING = "processing"  # 處理中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失敗


class UploadResponse(BaseModel):
    """檔案上傳響應模型"""
    file_id: str = Field(..., description="檔案唯一識別碼")
    filename: str = Field(..., description="檔案名稱")
    file_size: int = Field(..., description="檔案大小（bytes）")
    message: str = Field(..., description="響應訊息")


class ProcessRequest(BaseModel):
    """處理請求模型"""
    file_id: str = Field(..., description="要處理的檔案 ID")
    include_timestamps: bool = Field(False, description="是否包含時間戳記")


class ProcessResponse(BaseModel):
    """處理響應模型"""
    task_id: str = Field(..., description="任務 ID")
    status: TaskStatus = Field(..., description="任務狀態")
    message: str = Field(..., description="響應訊息")


class GenerateRequest(BaseModel):
    """文案生成請求模型"""
    transcript_id: str = Field(..., description="逐字稿 ID")
    formats: List[ContentFormat] = Field(..., description="要生成的文案格式列表")
    custom_prompt: Optional[str] = Field(None, description="自訂提示詞（可選）")


class GenerateResponse(BaseModel):
    """文案生成響應模型"""
    task_id: str = Field(..., description="任務 ID")
    status: TaskStatus = Field(..., description="任務狀態")
    formats: List[ContentFormat] = Field(..., description="請求的格式列表")
    message: str = Field(..., description="響應訊息")


class GenerateFromTranscriptRequest(BaseModel):
    """直接使用逐字稿文字生成文案的請求模型（免 transcript_id）"""
    transcript: str = Field(..., description="完整逐字稿文字內容")
    formats: List[ContentFormat] = Field(..., description="要生成的文案格式列表")


class TaskStatusResponse(BaseModel):
    """任務狀態響應模型"""
    task_id: str = Field(..., description="任務 ID")
    status: TaskStatus = Field(..., description="任務狀態")
    progress: float = Field(0.0, description="進度百分比 (0-100)")
    # 下列兩個欄位用於顯示較真實的處理進度（以秒數為單位），前端可選擇使用
    total_duration: Optional[float] = Field(
        None,
        description="任務對應的音訊總長度（秒），用於計算真實進度"
    )
    processed_duration: Optional[float] = Field(
        None,
        description="目前已處理的音訊長度（秒），用於估算剩餘時間"
    )
    message: Optional[str] = Field(None, description="狀態訊息")
    result: Optional[dict] = Field(None, description="結果數據（完成時）")
    error: Optional[str] = Field(None, description="錯誤訊息（失敗時）")


