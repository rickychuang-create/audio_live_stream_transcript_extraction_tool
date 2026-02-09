"""
標點符號處理服務模組
使用 Gemini API 為逐字稿添加標點符號和分段
"""
import os
from typing import Optional
from app.config import settings
from app.utils.file_handler import get_output_path


class PunctuationService:
    """標點符號處理服務類別"""
    
    def __init__(self):
        """初始化服務，設定 Gemini 客戶端"""
        if not settings.GEMINI_API_KEY:
            raise ValueError("未設定 GEMINI_API_KEY")
        
        try:
            import google.generativeai as genai
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self.client = genai
            self.model = settings.GEMINI_MODEL
        except ImportError:
            raise ImportError("請安裝 google-generativeai 套件: pip install google-generativeai")
    
    def add_punctuation(self, raw_text: str, file_id: str) -> dict:
        """
        為逐字稿添加標點符號和分段
        
        Args:
            raw_text: 沒有標點符號的原始逐字稿
            file_id: 檔案 ID（用於命名輸出檔案）
            
        Returns:
            dict: 包含處理後的逐字稿和相關資訊的字典
                - text: 有標點符號且分段好的逐字稿
                - file_path: 儲存的檔案路徑
        """
        try:
            print(f"[DEBUG] 標點符號處理開始: file_id={file_id}, 原始文字長度={len(raw_text)} 字元")
            
            # 構建提示詞
            prompt = self._build_prompt(raw_text)
            print(f"[DEBUG] 提示詞構建完成，長度={len(prompt)} 字元")
            
            # 調用 Gemini API
            print(f"[DEBUG] 調用 Gemini API: model={self.model}")
            model = self.client.GenerativeModel(self.model)
            response = model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.3,  # 較低溫度，確保準確性
                    "max_output_tokens": 200000,  # 足夠的輸出長度
                }
            )
            
            # 提取處理後的文字
            processed_text = response.text.strip()
            print(f"[DEBUG] Gemini API 回應成功，處理後文字長度={len(processed_text)} 字元")
            
            # 建立輸出檔案路徑
            output_path = get_output_path(file_id, "_transcript_formatted.txt")
            
            # 儲存處理後的逐字稿
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(processed_text)
            print(f"[DEBUG] 處理後的逐字稿已儲存: {output_path}")
            
            return {
                "text": processed_text,
                "file_path": output_path
            }
            
        except Exception as e:
            print(f"[ERROR] 標點符號處理過程中發生錯誤: {str(e)}")
            import traceback
            traceback.print_exc()
            raise Exception(f"標點符號處理失敗: {str(e)}")
    
    def _build_prompt(self, raw_text: str) -> str:
        """
        構建提示詞
        
        Args:
            raw_text: 原始逐字稿文字
            
        Returns:
            str: 完整的提示詞
        """
        prompt = """請為以下語音直播的逐字稿添加適當的標點符號並合理分段。

要求：
1. 添加適當的標點符號（句號、逗號、問號、驚嘆號等）
2. 合理分段，每段約 3-5 句話，讓內容更易閱讀
3. 保持原意不變，不要修改或刪除任何內容
4. 只返回處理後的文字，不要添加任何說明、註解或額外內容
5. 確保分段自然流暢，符合中文閱讀習慣

逐字稿內容：
{transcript}"""
        
        return prompt.format(transcript=raw_text)


# 建立全域服務實例（單例模式）
_punctuation_service = None

def get_punctuation_service() -> PunctuationService:
    """
    取得標點符號處理服務實例（單例模式）
    
    Returns:
        PunctuationService: 服務實例
    """
    global _punctuation_service
    if _punctuation_service is None:
        _punctuation_service = PunctuationService()
    return _punctuation_service

