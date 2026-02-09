"""
音訊處理服務模組
負責 MP4 轉 MP3 的音訊提取功能
"""
import os
from pathlib import Path
from typing import Optional
from moviepy.editor import VideoFileClip
from app.config import settings
from app.utils.file_handler import get_output_path


class AudioService:
    """音訊處理服務類別"""
    
    @staticmethod
    def extract_audio(video_path: str, file_id: str) -> str:
        """
        從 MP4 影片中提取音訊並轉換為 MP3
        
        Args:
            video_path: 影片檔案路徑
            file_id: 檔案 ID（用於命名輸出檔案）
            
        Returns:
            str: 輸出的 MP3 檔案路徑
            
        Raises:
            FileNotFoundError: 當影片檔案不存在時
            Exception: 當音訊提取失敗時
        """
        # 檢查影片檔案是否存在
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"影片檔案不存在: {video_path}")
        
        # 建立輸出 MP3 檔案路徑
        audio_path = get_output_path(file_id, ".mp3")
        
        try:
            # 載入影片檔案
            video = VideoFileClip(video_path)
            
            # 檢查是否有音訊軌道
            if video.audio is None:
                raise ValueError("影片檔案沒有音訊軌道")
            
            # 提取音訊並儲存為 MP3
            video.audio.write_audiofile(
                audio_path,
                codec='mp3',
                bitrate='192k',  # 設定音訊品質
                verbose=False,  # 減少輸出訊息
                logger=None  # 關閉日誌
            )
            
            # 關閉影片物件以釋放資源
            video.close()
            
            # 檢查輸出檔案是否成功建立
            if not os.path.exists(audio_path):
                raise Exception("音訊檔案提取失敗")
            
            return audio_path
            
        except Exception as e:
            # 如果發生錯誤，清理可能建立的檔案
            if os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                except:
                    pass
            raise Exception(f"音訊提取失敗: {str(e)}")
    
    @staticmethod
    def get_audio_duration(audio_path: str) -> float:
        """
        取得音訊檔案的時長（秒）
        
        Args:
            audio_path: 音訊檔案路徑
            
        Returns:
            float: 音訊時長（秒）
        """
        try:
            from moviepy.editor import AudioFileClip
            audio = AudioFileClip(audio_path)
            duration = audio.duration
            audio.close()
            return duration
        except Exception:
            return 0.0
