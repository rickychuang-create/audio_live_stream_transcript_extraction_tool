"""
語音轉文字服務模組
使用 Gemini 2.5 Flash API 將音訊轉換為逐字稿
"""
import os
import time
import google.generativeai as genai
from typing import Dict, Optional, Generator
from app.config import settings
from app.utils.file_handler import get_output_path


class TranscriptionService:
    """語音轉文字服務類別（使用 Gemini API）"""
    
    def __init__(self):
        """初始化服務，設定 Gemini API"""
        if not settings.GEMINI_API_KEY:
            raise ValueError("未設定 GEMINI_API_KEY，無法使用 Gemini 轉錄服務")
        
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model_name = settings.GEMINI_MODEL or "gemini-2.5-flash"
        self.model = genai.GenerativeModel(self.model_name)
    
    def transcribe(
        self, 
        audio_path: str, 
        file_id: str,
        include_timestamps: bool = False
    ) -> Dict:
        """
        將音訊轉換為逐字稿（非串流模式，收集完整結果後返回）
        
        Args:
            audio_path: 音訊檔案路徑
            file_id: 檔案 ID（用於命名輸出檔案）
            include_timestamps: 是否包含時間戳記（Gemini API 不支援，保留參數以相容）
            
        Returns:
            Dict: 包含逐字稿文字和相關資訊的字典
                - text: 逐字稿文字
                - language: 偵測到的語言（預設為 zh）
                - file_path: 儲存的逐字稿檔案路徑
                - gemini_file_name: Gemini 雲端檔案名稱（用於清理）
                
        Raises:
            FileNotFoundError: 當音訊檔案不存在時
            Exception: 當轉錄失敗時
        """
        # 檢查音訊檔案是否存在
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"音訊檔案不存在: {audio_path}")
        
        gemini_file_name = None
        
        try:
            # 1. 上傳音訊到 Gemini
            print(f"[DEBUG] 正在上傳音訊到 Gemini: {audio_path}")
            audio_file = genai.upload_file(path=audio_path)
            gemini_file_name = audio_file.name
            
            # 2. 等待處理完成
            print(f"[DEBUG] 等待 Gemini 處理音訊檔案...")
            while audio_file.state.name == "PROCESSING":
                print(".", end="", flush=True)
                time.sleep(3)
                audio_file = genai.get_file(audio_file.name)
            
            if audio_file.state.name == "FAILED":
                raise Exception("Gemini 處理音訊檔案失敗")
            
            print(f"\n[DEBUG] Gemini 處理完成，開始轉錄...")
            
            # 3. 轉錄提示詞
            instruction = (
                "請幫我將這段音訊轉錄成完整的繁體中文逐字稿。請精確地記下說話內容，"
                "並加上適當的標點符號與分段。若有類似【呃】、【嗯】之類的語助詞或停頓詞請排除。"
            )
            
            # 4. 執行轉錄（非串流模式）
            response = self.model.generate_content(
                [instruction, audio_file],
                stream=False
            )
            
            # 5. 取得完整逐字稿
            transcript_text = response.text if hasattr(response, 'text') else str(response)
            
            # 6. 建立輸出檔案路徑
            transcript_path = get_output_path(file_id, "_transcript.txt")
            
            # 7. 儲存逐字稿文字
            with open(transcript_path, "w", encoding="utf-8") as f:
                f.write(transcript_text)
            
            # 8. 準備返回結果
            result = {
                "text": transcript_text,
                "language": "zh",  # Gemini 預設為中文
                "file_path": transcript_path,
                "gemini_file_name": gemini_file_name
            }
            
            return result
            
        except Exception as e:
            # 發生錯誤時，嘗試清理 Gemini 檔案
            if gemini_file_name:
                try:
                    genai.delete_file(gemini_file_name)
                except:
                    pass
            raise Exception(f"語音轉文字失敗: {str(e)}")
    
    def transcribe_stream(
        self,
        audio_path: str,
        file_id: str
    ) -> Generator[Dict, None, None]:
        """
        將音訊轉換為逐字稿（串流模式，使用 yield 返回文字片段）
        
        Args:
            audio_path: 音訊檔案路徑
            file_id: 檔案 ID（用於命名輸出檔案）
            
        Yields:
            Dict: 包含轉錄進度和文字片段的字典
                - type: 事件類型 ('progress', 'chunk', 'complete', 'error')
                - message: 狀態訊息
                - text: 文字片段（僅在 type='chunk' 時）
                - full_text: 完整逐字稿（僅在 type='complete' 時）
                - file_path: 儲存的逐字稿檔案路徑（僅在 type='complete' 時）
                - gemini_file_name: Gemini 雲端檔案名稱（用於清理）
                
        Raises:
            FileNotFoundError: 當音訊檔案不存在時
            Exception: 當轉錄失敗時
        """
        # 檢查音訊檔案是否存在
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"音訊檔案不存在: {audio_path}")
        
        gemini_file_name = None
        full_text = ""
        transcript_path = None
        
        try:
            # 1. 上傳音訊到 Gemini
            yield {
                "type": "progress",
                "message": "正在上傳音訊到 Gemini..."
            }
            
            print(f"[DEBUG] 正在上傳音訊到 Gemini: {audio_path}")
            audio_file = genai.upload_file(path=audio_path)
            gemini_file_name = audio_file.name
            
            # 2. 等待處理完成
            yield {
                "type": "progress",
                "message": "等待 Gemini 處理音訊檔案..."
            }
            
            print(f"[DEBUG] 等待 Gemini 處理音訊檔案...")
            while audio_file.state.name == "PROCESSING":
                print(".", end="", flush=True)
                time.sleep(3)
                audio_file = genai.get_file(audio_file.name)
            
            if audio_file.state.name == "FAILED":
                raise Exception("Gemini 處理音訊檔案失敗")
            
            print(f"\n[DEBUG] Gemini 處理完成，開始串流轉錄...")
            
            # 3. 轉錄提示詞
            instruction = (
                "請幫我將這段音訊轉錄成完整的繁體中文逐字稿。請精確地記下說話內容，"
                "並加上適當的標點符號與分段。若有類似【呃】、【嗯】之類的語助詞或停頓詞請排除。"
            )
            
            # 4. 執行串流轉錄
            yield {
                "type": "progress",
                "message": "開始轉錄..."
            }
            
            response = self.model.generate_content(
                [instruction, audio_file],
                stream=True
            )
            
            # 5. 迭代輸出文字片段（確保每個 chunk 立即 yield）
            # 如果 Gemini 返回的 chunk 太大，進一步分割成更小的片段以實現更好的串流效果
            CHUNK_SIZE_LIMIT = 100  # 每個片段最大長度（字元數）
            chunk_count = 0
            
            for chunk in response:
                if hasattr(chunk, 'text') and chunk.text:
                    chunk_text = chunk.text
                    full_text += chunk_text
                    
                    # 如果 chunk 太大，進一步分割成更小的片段
                    if len(chunk_text) > CHUNK_SIZE_LIMIT:
                        # 按句子或標點符號分割，如果沒有標點則按固定長度分割
                        import re
                        # 嘗試按句子分割（句號、問號、驚嘆號、換行）
                        sentences = re.split(r'([。！？\n])', chunk_text)
                        current_segment = ""
                        
                        for i in range(0, len(sentences), 2):
                            if i + 1 < len(sentences):
                                sentence = sentences[i] + sentences[i + 1]
                            else:
                                sentence = sentences[i]
                            
                            # 如果當前片段加上新句子超過限制，先發送當前片段
                            if len(current_segment) + len(sentence) > CHUNK_SIZE_LIMIT and current_segment:
                                chunk_count += 1
                                print(f"[DEBUG] 發送轉錄 chunk #{chunk_count}, 長度: {len(current_segment)} 字元（分割後）")
                                yield {
                                    "type": "chunk",
                                    "text": current_segment,
                                    "message": "正在轉錄..."
                                }
                                current_segment = sentence
                            else:
                                current_segment += sentence
                            
                            # 如果當前片段達到限制，立即發送
                            if len(current_segment) >= CHUNK_SIZE_LIMIT:
                                chunk_count += 1
                                print(f"[DEBUG] 發送轉錄 chunk #{chunk_count}, 長度: {len(current_segment)} 字元（分割後）")
                                yield {
                                    "type": "chunk",
                                    "text": current_segment,
                                    "message": "正在轉錄..."
                                }
                                current_segment = ""
                        
                        # 發送剩餘的片段
                        if current_segment:
                            chunk_count += 1
                            print(f"[DEBUG] 發送轉錄 chunk #{chunk_count}, 長度: {len(current_segment)} 字元（分割後）")
                            yield {
                                "type": "chunk",
                                "text": current_segment,
                                "message": "正在轉錄..."
                            }
                    else:
                        # chunk 不大，直接發送
                        chunk_count += 1
                        print(f"[DEBUG] 發送轉錄 chunk #{chunk_count}, 長度: {len(chunk_text)} 字元")
                        yield {
                            "type": "chunk",
                            "text": chunk_text,
                            "message": "正在轉錄..."
                        }
            
            print(f"[DEBUG] 轉錄完成，共發送 {chunk_count} 個 chunks，總長度: {len(full_text)} 字元")
            
            # 6. 建立輸出檔案路徑
            transcript_path = get_output_path(file_id, "_transcript.txt")
            
            # 7. 儲存完整逐字稿
            with open(transcript_path, "w", encoding="utf-8") as f:
                f.write(full_text)
            
            # 8. 返回完成事件
            yield {
                "type": "complete",
                "message": "轉錄完成",
                "full_text": full_text,
                "file_path": transcript_path,
                "gemini_file_name": gemini_file_name
            }
            
        except Exception as e:
            # 發生錯誤時，返回錯誤事件
            yield {
                "type": "error",
                "message": f"轉錄失敗: {str(e)}",
                "gemini_file_name": gemini_file_name
            }
            # 嘗試清理 Gemini 檔案
            if gemini_file_name:
                try:
                    genai.delete_file(gemini_file_name)
                except:
                    pass
            raise
    
    def transcribe_stream_with_file(
        self,
        gemini_file_name: str,
        file_id: str
    ) -> Generator[Dict, None, None]:
        """
        使用已上傳的 Gemini 檔案進行串流轉錄
        
        Args:
            gemini_file_name: 已上傳的 Gemini 檔案名稱
            file_id: 檔案 ID（用於命名輸出檔案）
            
        Yields:
            Dict: 包含轉錄進度和文字片段的字典
                - type: 事件類型 ('progress', 'chunk', 'complete', 'error')
                - message: 狀態訊息
                - text: 文字片段（僅在 type='chunk' 時）
                - full_text: 完整逐字稿（僅在 type='complete' 時）
                - file_path: 儲存的逐字稿檔案路徑（僅在 type='complete' 時）
                - gemini_file_name: Gemini 雲端檔案名稱（用於清理）
        """
        full_text = ""
        transcript_path = None
        
        try:
            # 1. 取得已上傳的檔案
            audio_file = genai.get_file(gemini_file_name)
            
            # 2. 等待處理完成（如果還在處理中）
            if audio_file.state.name == "PROCESSING":
                yield {
                    "type": "progress",
                    "message": "等待 Gemini 處理音訊檔案..."
                }
                
                print(f"[DEBUG] 等待 Gemini 處理音訊檔案...")
                while audio_file.state.name == "PROCESSING":
                    print(".", end="", flush=True)
                    time.sleep(3)
                    audio_file = genai.get_file(gemini_file_name)
            
            if audio_file.state.name == "FAILED":
                raise Exception("Gemini 處理音訊檔案失敗")
            
            print(f"\n[DEBUG] Gemini 處理完成，開始串流轉錄...")
            
            # 3. 轉錄提示詞
            instruction = (
                "請幫我將這段音訊轉錄成完整的繁體中文逐字稿。請精確地記下說話內容，"
                "並加上適當的標點符號與分段。若有類似【呃】、【嗯】之類的語助詞或停頓詞請排除。"
            )
            
            # 4. 執行串流轉錄
            yield {
                "type": "progress",
                "message": "開始轉錄..."
            }
            
            response = self.model.generate_content(
                [instruction, audio_file],
                stream=True
            )
            
            # 5. 迭代輸出文字片段（確保每個 chunk 立即 yield）
            # 如果 Gemini 返回的 chunk 太大，進一步分割成更小的片段以實現更好的串流效果
            CHUNK_SIZE_LIMIT = 100  # 每個片段最大長度（字元數）
            chunk_count = 0
            
            for chunk in response:
                try:
                    # 安全地取得 chunk 文字
                    chunk_text = None
                    
                    # 方法 1: 直接從 chunk.text 取得
                    if hasattr(chunk, 'text') and chunk.text:
                        chunk_text = chunk.text
                    # 方法 2: 從 candidates 中取得
                    elif hasattr(chunk, 'candidates') and chunk.candidates:
                        candidate = chunk.candidates[0]
                        if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                            parts = candidate.content.parts
                            if parts and hasattr(parts[0], 'text'):
                                chunk_text = parts[0].text
                    
                    # 如果沒有取得文字，檢查 finish_reason
                    if not chunk_text:
                        finish_reason = None
                        if hasattr(chunk, 'candidates') and chunk.candidates:
                            candidate = chunk.candidates[0]
                            if hasattr(candidate, 'finish_reason'):
                                finish_reason = candidate.finish_reason
                                print(f"[DEBUG] Chunk finish_reason: {finish_reason}")
                                # finish_reason 1 = STOP，這是正常的結束
                                if finish_reason == 1:  # STOP
                                    print(f"[DEBUG] 收到 STOP 信號，轉錄已完成")
                                    break
                        # 如果沒有文字也沒有 finish_reason，跳過這個 chunk
                        print(f"[DEBUG] 跳過沒有文字的 chunk，finish_reason: {finish_reason}")
                        continue
                    
                    full_text += chunk_text
                    
                    # 如果 chunk 太大，進一步分割成更小的片段
                    if len(chunk_text) > CHUNK_SIZE_LIMIT:
                        # 按句子或標點符號分割，如果沒有標點則按固定長度分割
                        import re
                        # 嘗試按句子分割（句號、問號、驚嘆號、換行）
                        sentences = re.split(r'([。！？\n])', chunk_text)
                        current_segment = ""
                        
                        for i in range(0, len(sentences), 2):
                            if i + 1 < len(sentences):
                                sentence = sentences[i] + sentences[i + 1]
                            else:
                                sentence = sentences[i]
                            
                            # 如果當前片段加上新句子超過限制，先發送當前片段
                            if len(current_segment) + len(sentence) > CHUNK_SIZE_LIMIT and current_segment:
                                chunk_count += 1
                                print(f"[DEBUG] 發送轉錄 chunk #{chunk_count}, 長度: {len(current_segment)} 字元（分割後）")
                                yield {
                                    "type": "chunk",
                                    "text": current_segment,
                                    "message": "正在轉錄..."
                                }
                                current_segment = sentence
                            else:
                                current_segment += sentence
                            
                            # 如果當前片段達到限制，立即發送
                            if len(current_segment) >= CHUNK_SIZE_LIMIT:
                                chunk_count += 1
                                print(f"[DEBUG] 發送轉錄 chunk #{chunk_count}, 長度: {len(current_segment)} 字元（分割後）")
                                yield {
                                    "type": "chunk",
                                    "text": current_segment,
                                    "message": "正在轉錄..."
                                }
                                current_segment = ""
                        
                        # 發送剩餘的片段
                        if current_segment:
                            chunk_count += 1
                            print(f"[DEBUG] 發送轉錄 chunk #{chunk_count}, 長度: {len(current_segment)} 字元（分割後）")
                            yield {
                                "type": "chunk",
                                "text": current_segment,
                                "message": "正在轉錄..."
                            }
                    else:
                        # chunk 不大，直接發送
                        chunk_count += 1
                        print(f"[DEBUG] 發送轉錄 chunk #{chunk_count}, 長度: {len(chunk_text)} 字元")
                        yield {
                            "type": "chunk",
                            "text": chunk_text,
                            "message": "正在轉錄..."
                        }
                except Exception as chunk_error:
                    # 處理單個 chunk 的錯誤，記錄但不中斷整個流程
                    print(f"[WARNING] 處理 chunk 時發生錯誤: {chunk_error}")
                    print(f"[WARNING] Chunk 類型: {type(chunk)}")
                    # 繼續處理下一個 chunk
                    continue
            
            # 檢查是否有累積的文字內容
            if not full_text:
                raise Exception("轉錄過程中沒有收到任何文字內容，可能是 API 回應格式異常")
            
            print(f"[DEBUG] 轉錄完成，共發送 {chunk_count} 個 chunks，總長度: {len(full_text)} 字元")
            
            # 6. 建立輸出檔案路徑
            transcript_path = get_output_path(file_id, "_transcript.txt")
            
            # 7. 儲存完整逐字稿
            with open(transcript_path, "w", encoding="utf-8") as f:
                f.write(full_text)
            
            # 8. 返回完成事件
            yield {
                "type": "complete",
                "message": "轉錄完成",
                "full_text": full_text,
                "file_path": transcript_path,
                "gemini_file_name": gemini_file_name
            }
            
        except Exception as e:
            # 發生錯誤時，返回錯誤事件
            error_msg = f"轉錄失敗: {str(e)}"
            print(f"[ERROR] {error_msg}")
            import traceback
            traceback.print_exc()
            yield {
                "type": "error",
                "message": error_msg,
                "gemini_file_name": gemini_file_name
            }
            # 不重新拋出異常，讓錯誤事件能正確發送到前端
    
    def cleanup_gemini_file(self, gemini_file_name: str):
        """
        清理 Gemini 雲端檔案
        
        Args:
            gemini_file_name: Gemini 檔案名稱
        """
        if gemini_file_name:
            try:
                genai.delete_file(gemini_file_name)
                print(f"[DEBUG] 已清理 Gemini 檔案: {gemini_file_name}")
            except Exception as e:
                print(f"[WARNING] 清理 Gemini 檔案失敗: {gemini_file_name}, error={e}")


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
