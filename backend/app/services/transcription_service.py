"""
語音轉文字服務模組
使用 Whisper 將音訊轉換為逐字稿
"""
import os
import whisper
from typing import Dict, Optional
from app.config import settings
from app.utils.file_handler import get_output_path


class TranscriptionService:
    """語音轉文字服務類別"""
    
    def __init__(self):
        """初始化服務，載入 Whisper 模型"""
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """
        載入 Whisper 模型
        使用配置中指定的模型等級
        """
        try:
            # 載入 Whisper 模型
            # 模型等級: tiny, base, small, medium, large
            self.model = whisper.load_model(settings.WHISPER_MODEL)
        except Exception as e:
            raise Exception(f"無法載入 Whisper 模型: {str(e)}")
    
    def transcribe(
        self, 
        audio_path: str, 
        file_id: str,
        include_timestamps: bool = False
    ) -> Dict:
        """
        將音訊轉換為逐字稿
        
        Args:
            audio_path: 音訊檔案路徑
            file_id: 檔案 ID（用於命名輸出檔案）
            include_timestamps: 是否包含時間戳記
            
        Returns:
            Dict: 包含逐字稿文字和相關資訊的字典
                - text: 逐字稿文字
                - segments: 分段資訊（如果包含時間戳記）
                - language: 偵測到的語言
                - file_path: 儲存的逐字稿檔案路徑
                
        Raises:
            FileNotFoundError: 當音訊檔案不存在時
            Exception: 當轉錄失敗時
        """
        # 檢查音訊檔案是否存在
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"音訊檔案不存在: {audio_path}")
        
        try:
            # 使用 Whisper 進行語音轉文字
            result = self.model.transcribe(
                audio_path,
                language="zh",  # 指定中文（可根據需求調整）
                verbose=False  # 減少輸出訊息
            )
            
            # 建立輸出檔案路徑
            transcript_path = get_output_path(file_id, "_transcript.txt")
            
            # 儲存逐字稿文字
            with open(transcript_path, "w", encoding="utf-8") as f:
                f.write(result["text"])
            
            # 準備返回結果
            response = {
                "text": result["text"],
                "language": result.get("language", "zh"),
                "file_path": transcript_path
            }
            
            # 如果包含時間戳記，也儲存分段資訊
            if include_timestamps and "segments" in result:
                response["segments"] = result["segments"]
                
                # 儲存帶時間戳記的版本
                timestamp_path = get_output_path(file_id, "_transcript_timestamps.txt")
                with open(timestamp_path, "w", encoding="utf-8") as f:
                    for segment in result["segments"]:
                        start_time = self._format_timestamp(segment["start"])
                        end_time = self._format_timestamp(segment["end"])
                        f.write(f"[{start_time} - {end_time}] {segment['text']}\n")
                
                response["timestamp_file_path"] = timestamp_path
            
            return response
            
        except Exception as e:
            raise Exception(f"語音轉文字失敗: {str(e)}")
    
    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        """
        將秒數格式化為時間戳記字串 (HH:MM:SS)
        
        Args:
            seconds: 秒數
            
        Returns:
            str: 格式化的時間戳記
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"


# 建立全域服務實例（單例模式）
_transcription_service = None

def get_transcription_service() -> TranscriptionService:
    """
    取得語音轉文字服務實例（單例模式）
    
    Returns:
        TranscriptionService: 服務實例
    """
    global _transcription_service
    if _transcription_service is None:
        _transcription_service = TranscriptionService()
    return _transcription_service
