"""
主要 API 路由
定義所有 API 端點
"""
import asyncio
import os
import uuid
from typing import List
import math  # 用於計算切片數量
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from app.models.schemas import (
    UploadResponse, ProcessRequest, ProcessResponse, GenerateRequest, GenerateResponse,
    TaskStatusResponse, TaskStatus, ContentFormat, GenerateFromTranscriptRequest
)
from app.api.upload import handle_upload
from app.services.audio_service import AudioService
from app.services.transcription_service import get_transcription_service
from app.services.content_generator import get_content_generator
from app.services.punctuation_service import get_punctuation_service
from app.config import settings
from app.utils.file_handler import (
    generate_file_id, validate_file, save_uploaded_file,
    get_file_path, file_exists, get_output_path  # 取得輸出檔案路徑（用於切片與最終逐字稿）
)
from moviepy.editor import AudioFileClip  # 用於將整段音訊切成多個小片段

router = APIRouter()

# 任務狀態儲存（生產環境應使用 Redis 或資料庫）
tasks_storage = {}
files_storage = {}  # 儲存檔案資訊


@router.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """
    上傳 MP4 檔案
    
    Args:
        file: 上傳的 MP4 檔案
        
    Returns:
        UploadResponse: 上傳結果
    """
    # 驗證檔案
    is_valid, error_msg = validate_file(file)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    
    # 生成檔案 ID
    file_id = generate_file_id()
    
    try:
        # 儲存檔案
        file_path = await save_uploaded_file(file, file_id)
        
        # 取得檔案大小
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        
        # 儲存檔案資訊
        files_storage[file_id] = {
            "filename": file.filename,
            "file_path": file_path,
            "file_size": file_size
        }
        
        return UploadResponse(
            file_id=file_id,
            filename=file.filename or "unknown",
            file_size=file_size,
            message="檔案上傳成功"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"檔案上傳失敗: {str(e)}")


@router.post("/process", response_model=ProcessResponse)
async def process_file(request: ProcessRequest, background_tasks: BackgroundTasks):
    """
    處理檔案：提取音訊並轉換為逐字稿
    
    Args:
        request: 處理請求
        background_tasks: FastAPI 背景任務
        
    Returns:
        ProcessResponse: 處理結果
    """
    file_id = request.file_id
    
    # 檢查檔案是否存在
    if file_id not in files_storage:
        raise HTTPException(status_code=404, detail="檔案不存在")
    
    # 生成任務 ID
    task_id = str(uuid.uuid4())
    
    # 初始化任務狀態（確保在返回前就已經存在）
    tasks_storage[task_id] = {
        "status": TaskStatus.PENDING,
        "progress": 0.0,
        "message": "等待處理",
        "file_id": file_id
    }
    
    # 添加調試日誌
    print(f"[DEBUG] 創建處理任務: task_id={task_id}, file_id={file_id}")
    print(f"[DEBUG] 任務已存入 tasks_storage，當前任務數: {len(tasks_storage)}")
    
    # 在背景執行處理任務
    background_tasks.add_task(process_file_task, task_id, file_id, request.include_timestamps)
    
    # 確保任務狀態可以被查詢
    print(f"[DEBUG] 返回任務ID: {task_id}, 狀態: {tasks_storage[task_id]['status']}")
    
    return ProcessResponse(
        task_id=task_id,
        status=TaskStatus.PENDING,
        message="處理任務已啟動"
    )


async def process_file_task(task_id: str, file_id: str, include_timestamps: bool):
    """
    背景任務：處理檔案
    
    Args:
        task_id: 任務 ID
        file_id: 檔案 ID
        include_timestamps: 是否包含時間戳記
    """
    try:
        # 確保任務存在
        if task_id not in tasks_storage:
            print(f"[ERROR] 任務不存在於 tasks_storage: {task_id}")
            return
        
        # 更新任務狀態為處理中
        tasks_storage[task_id]["status"] = TaskStatus.PROCESSING
        tasks_storage[task_id]["progress"] = 5.0
        tasks_storage[task_id]["message"] = "正在準備處理..."
        print(f"[DEBUG] 開始處理任務: {task_id}, 進度: 5%")
        
        # 取得檔案路徑
        file_info = files_storage[file_id]
        video_path = file_info["file_path"]
        
        # 步驟 1: 提取音訊
        # 說明：先從影片中抽出 MP3，再根據 MP3 來計算長度與後續轉錄
        tasks_storage[task_id]["progress"] = 10.0
        tasks_storage[task_id]["message"] = "正在提取音訊..."
        print(f"[DEBUG] 更新進度: {task_id}, 進度: 10%, 訊息: 正在提取音訊...")
        
        audio_service = AudioService()
        audio_path = audio_service.extract_audio(video_path, file_id)
        
        # 更新進度：音訊提取完成
        tasks_storage[task_id]["progress"] = 30.0
        tasks_storage[task_id]["message"] = "音訊提取完成，正在分析音訊長度..."
        print(f"[DEBUG] 更新進度: {task_id}, 進度: 30%, 訊息: 音訊提取完成...")
        
        # 取得音訊長度（秒），用來估算後續轉錄進度
        total_duration = audio_service.get_audio_duration(audio_path)
        tasks_storage[task_id]["total_duration"] = total_duration
        tasks_storage[task_id]["processed_duration"] = 0.0
        print(f"[DEBUG] 音訊總長度: {total_duration:.2f} 秒 (task_id={task_id})")
        
        # 步驟 2: 語音轉文字（這是最耗時的部分）
        # 說明：我們改成依照「已處理秒數 / 總秒數」來計算 40%~90% 的進度，而不是用模擬
        transcription_service = get_transcription_service()
        
        # 如果無法取得音訊長度（例如 0 秒），使用 fallback：保留舊的模擬進度邏輯
        if not total_duration or total_duration <= 0:
            print(f"[WARNING] 無法取得音訊長度，使用模擬進度模式 (task_id={task_id})")
            
            # 更新進度：開始語音識別
            tasks_storage[task_id]["progress"] = 40.0
            tasks_storage[task_id]["message"] = "正在進行語音識別..."
            print(f"[DEBUG] 更新進度: {task_id}, 進度: 40%, 訊息: 正在進行語音識別...")
            
            # === 舊的模擬進度邏輯，保留為 fallback ===
            transcription_completed = asyncio.Event()
            
            async def simulate_transcription_progress():
                """
                模擬轉錄進度更新（fallback 模式）
                從40%逐漸增加到85%，給用戶視覺反饋
                """
                current_progress = 40.0
                max_progress = 85.0  # 最多到85%，等待實際轉錄完成
                last_logged_progress = 40.0  # 記錄上次打印的進度，用於減少日誌輸出
                
                while current_progress < max_progress and not transcription_completed.is_set():
                    # 每1.5秒增加5-8%的進度
                    increment = 5.0 + (max_progress - current_progress) * 0.1  # 越接近目標，增量越小
                    current_progress = min(current_progress + increment, max_progress)
                    
                    # 更新任務進度（確保任務仍然存在）
                    if task_id in tasks_storage and tasks_storage[task_id]["status"] == TaskStatus.PROCESSING:
                        tasks_storage[task_id]["progress"] = current_progress
                        tasks_storage[task_id]["message"] = f"正在進行語音識別... {int(current_progress)}%"
                        
                        # 只在進度變化超過5%時才打印，減少日誌輸出
                        if current_progress - last_logged_progress >= 5.0:
                            print(f"[DEBUG] 模擬進度更新: {task_id}, 進度: {current_progress:.1f}%")
                            last_logged_progress = current_progress
                    
                    # 等待1.5秒後再次更新
                    await asyncio.sleep(1.5)
            
            # 啟動進度模擬任務
            progress_task = asyncio.create_task(simulate_transcription_progress())
            
            try:
                # 開始轉錄（Whisper 是同步處理，無法獲取中間進度）
                # 注意：這裡需要在異步函數中運行同步的轉錄操作
                # 使用 asyncio.to_thread 或 run_in_executor 來避免阻塞事件循環
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    transcription_service.transcribe,
                    audio_path,
                    file_id,
                    include_timestamps
                )
            finally:
                # 標記轉錄完成，停止進度模擬
                transcription_completed.set()
                # 等待進度模擬任務完成（如果還在運行）
                if not progress_task.done():
                    progress_task.cancel()
                    try:
                        await progress_task
                    except asyncio.CancelledError:
                        pass
            
            # 轉錄完成，預設使用原始 Whisper 逐字稿作為結果
            tasks_storage[task_id]["progress"] = 90.0
            tasks_storage[task_id]["message"] = "語音識別完成"
            print(f"[DEBUG] 更新進度: {task_id}, 進度: 90%, 訊息: 語音識別完成 (fallback)...")
        
        else:
            # === 真實進度模式（切片轉錄）：進度從 0% 開始一路跑到 90% ===
            # 說明：
            # - 先前的 10% / 30% 僅用來表示「提取音訊」的中間狀態，為了讓整體體感更直覺，
            #   在真正開始語音識別（切片轉錄）時，會將進度重置為 0%，讓使用者看到「轉錄本身」完整的 0%→90% 過程。
            tasks_storage[task_id]["progress"] = 0.0
            tasks_storage[task_id]["processed_duration"] = 0.0
            tasks_storage[task_id]["message"] = "正在進行語音識別..."
            print(
                f"[DEBUG] 更新進度: {task_id}, 進度: 0%, "
                f"訊息: 正在進行語音識別 (切片真實模式，從 0% 開始)..."
            )

            # 這裡定義每個切片的長度（秒），可依實際效能調整
            # 数值越小，進度更新越頻繁，但 Whisper 呼叫次數越多
            CHUNK_DURATION = 60.0

            # 用於累積所有片段的文字與語言資訊
            all_texts = []
            detected_language = None
            # 標記是否使用了 fallback 模式（整段轉錄）
            use_fallback_result = False

            # 說明：這裡不再共用同一個 AudioFileClip，而是每個 chunk 各自開啟一次 audio 檔
            # 以避免在 Windows + ffmpeg 組合下，共用 reader 造成 NoneType stdout 的錯誤
            num_chunks = max(1, math.ceil(total_duration / CHUNK_DURATION))
            # 這裡直接從 0% 開始推進到 90%
            transcription_start_progress = 0.0
            processed_duration = 0.0
            last_logged_progress = 0.0

            for index in range(num_chunks):
                # 計算當前切片的起訖時間（秒）
                start_time = index * CHUNK_DURATION
                end_time = min((index + 1) * CHUNK_DURATION, total_duration)
                chunk_duration = max(0.0, end_time - start_time)

                if chunk_duration <= 0:
                    continue

                # 為每個切片建立一個暫存音訊檔案
                chunk_file_id = f"{file_id}_chunk_{index}"
                chunk_audio_path = get_output_path(chunk_file_id, ".mp3")

                # 額外的診斷資訊：列出當前 chunk 的時間範圍與長度
                print(
                    f"[DEBUG] 準備切片: task_id={task_id}, chunk_index={index}, "
                    f"start={start_time:.2f}s, end={end_time:.2f}s, duration={chunk_duration:.2f}s"
                )

                # 每個 chunk 各自開啟一次 AudioFileClip，完成後立即關閉
                try:
                    with AudioFileClip(audio_path) as audio_clip:
                        subclip = audio_clip.subclip(start_time, end_time)
                        subclip.write_audiofile(
                            chunk_audio_path,
                            codec="mp3",
                            bitrate="192k",
                            verbose=False,
                            logger=None,
                        )
                        subclip.close()
                except Exception as e:
                    # 這裡是 moviepy/ffmpeg 在切片時出錯（例如 AttributeError: 'NoneType' object has no attribute 'stdout'）
                    # 為了避免整個任務失敗，我們會回退到「整段一次轉錄」模式
                    print(
                        f"[ERROR] 切片音訊寫入失敗，回退到整段轉錄模式: "
                        f"task_id={task_id}, file_id={file_id}, chunk_index={index}, error={e}"
                    )
                    # 使用整段音訊進行一次性轉錄
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(
                        None,
                        transcription_service.transcribe,
                        audio_path,
                        file_id,
                        include_timestamps,
                    )
                    # 直接將進度拉到 90%，並更新訊息
                    tasks_storage[task_id]["processed_duration"] = total_duration
                    tasks_storage[task_id]["progress"] = 90.0
                    tasks_storage[task_id]["message"] = "語音識別完成（切片失敗，改用整段轉錄）"
                    print(
                        f"[DEBUG] 更新進度: {task_id}, 進度: 90%, "
                        f"訊息: 語音識別完成（切片失敗，改用整段轉錄）..."
                    )
                    # 標記已使用 fallback，並跳出切片迴圈
                    use_fallback_result = True
                    break

                # 使用 Whisper 轉錄這個小片段
                # 說明：每個切片都在背景執行緒中轉錄，避免阻塞事件迴圈
                loop = asyncio.get_event_loop()
                chunk_result = await loop.run_in_executor(
                    None,
                    transcription_service.transcribe,
                    chunk_audio_path,
                    chunk_file_id,
                    include_timestamps,
                )

                # 累積文字結果
                all_texts.append(chunk_result.get("text", ""))
                if detected_language is None:
                    detected_language = chunk_result.get("language", "zh")

                # 轉錄完一個切片後，更新「已處理秒數」與進度
                processed_duration += chunk_duration
                tasks_storage[task_id]["processed_duration"] = min(processed_duration, total_duration)

                # 依「已處理秒數 / 總秒數」計算進度：
                # - 從 0% 一路平滑推進到 90%
                ratio = min(tasks_storage[task_id]["processed_duration"] / total_duration, 1.0)
                progress = transcription_start_progress + (90.0 - transcription_start_progress) * ratio

                if task_id in tasks_storage and tasks_storage[task_id]["status"] == TaskStatus.PROCESSING:
                    tasks_storage[task_id]["progress"] = progress
                    done_minutes = tasks_storage[task_id]["processed_duration"] / 60.0
                    total_minutes = total_duration / 60.0
                    tasks_storage[task_id]["message"] = (
                        "正在進行語音識別... \n"
                        f"語音總長度：{total_minutes:.1f}分鐘，已完成約 {done_minutes:.1f} / {total_minutes:.1f} 分鐘"
                    )

                    # 控制日誌輸出頻率：每增加 5% 以上才記錄一次，避免 log 太多
                    if progress - last_logged_progress >= 5.0:
                        print(
                            f"[DEBUG] 切片真實進度更新: task_id={task_id}, "
                            f"progress={progress:.1f}%, "
                            f"processed={done_minutes:.1f}/{total_minutes:.1f} 分鐘"
                        )
                        last_logged_progress = progress

                # 切片轉錄完成後，可以刪除暫存音訊檔案以節省空間
                try:
                    if os.path.exists(chunk_audio_path):
                        os.remove(chunk_audio_path)
                except Exception as cleanup_err:
                    print(f"[WARNING] 無法刪除暫存切片檔案: {chunk_audio_path}, error={cleanup_err}")

            # 如果使用了 fallback 模式（整段轉錄），跳過切片模式的結尾邏輯
            # 因為 fallback 分支已經設定好 result 和進度了
            if not use_fallback_result:
                # 如果 all_texts 有內容，代表至少有部分切片成功，可以組合成最終逐字稿
                if all_texts:
                    merged_transcript = "\n".join(all_texts).strip()

                    # 將合併後的逐字稿寫入單一輸出檔案
                    final_transcript_file = get_output_path(file_id, "_transcript.txt")
                    with open(final_transcript_file, "w", encoding="utf-8") as f:
                        f.write(merged_transcript)

                    # 保底：語音識別階段最後至少要到 90%
                    tasks_storage[task_id]["progress"] = max(tasks_storage[task_id]["progress"], 90.0)
                    tasks_storage[task_id]["message"] = "語音識別完成"
                    print(
                        f"[DEBUG] 更新進度: {task_id}, 進度: {tasks_storage[task_id]['progress']}%, "
                        f"訊息: 語音識別完成 (切片真實模式)..."
                    )

                    # 準備一個與原本 transcribe 結果相容的結構，方便後續標點流程沿用
                    result = {
                        "text": merged_transcript,
                        "file_path": final_transcript_file,
                        "language": detected_language or "zh",
                    }

        # 預設結果為原始 Whisper 逐字稿 / 切片合併後的逐字稿
        final_transcript = result["text"]
        final_transcript_file = result["file_path"]

        # 如果有啟用標點處理才進行（預設關閉，避免影響主流程）
        if settings.GEMINI_API_KEY and settings.ENABLE_PUNCTUATION:
            # 步驟 3: 添加標點符號和分段
            print(f"[DEBUG] 開始標點符號處理: task_id={task_id}, file_id={file_id}")
            try:
                # 切片轉錄完成後，先把進度拉到 95%，並明確告訴使用者現在進入標點符號階段
                tasks_storage[task_id]["progress"] = 95.0
                tasks_storage[task_id]["message"] = "正在呼叫 Gemini AI 模型進行標點符號處理，請稍後..."

                # 💡 加入一個短暫的 sleep (例如 0.5~1秒)，確保前端輪詢能抓到這個 95%
                await asyncio.sleep(2)

                punctuation_service = get_punctuation_service()
                print(f"[DEBUG] 標點符號服務初始化成功，開始處理逐字稿...")
                formatted_result = punctuation_service.add_punctuation(result["text"], file_id)
                
                print(f"[INFO] 標點符號處理成功，處理後文字長度: {len(formatted_result['text'])} 字元")
                
                # 使用處理後的逐字稿作為最終結果（進度 100% 與完成訊息在函式結尾統一設定）
                final_transcript = formatted_result["text"]
                final_transcript_file = formatted_result["file_path"]
            except Exception as e:
                # 如果標點符號處理失敗，記錄錯誤但不中斷流程，繼續使用原始逐字稿
                print(f"[ERROR] 標點符號處理失敗: {str(e)}")
                import traceback
                traceback.print_exc()
                print(f"[WARNING] 使用原始逐字稿繼續處理")
        
        # 更新任務狀態為完成
        tasks_storage[task_id]["status"] = TaskStatus.COMPLETED
        tasks_storage[task_id]["progress"] = 100.0
        tasks_storage[task_id]["message"] = "✅ 逐字稿處理完成"
        tasks_storage[task_id]["result"] = {
            "transcript": final_transcript,
            "transcript_file": final_transcript_file,
            "language": result.get("language", "zh"),
            "raw_transcript": result["text"]  # 保留原始逐字稿供參考
        }
        
        # 儲存逐字稿 ID（使用 file_id）
        files_storage[file_id]["transcript_id"] = file_id
        files_storage[file_id]["transcript"] = final_transcript
        print(f"[INFO] 逐字稿處理完成: task_id={task_id}, file_id={file_id}")
        
    except Exception as e:
        # 更新任務狀態為失敗
        tasks_storage[task_id]["status"] = TaskStatus.FAILED
        tasks_storage[task_id]["progress"] = 0.0
        tasks_storage[task_id]["message"] = f"❌ 處理失敗: {str(e)}"
        tasks_storage[task_id]["error"] = str(e)
        # 記錄錯誤
        print(f"[ERROR] 處理任務失敗: task_id={task_id}, file_id={file_id}, error={str(e)}")
        import traceback
        traceback.print_exc()


@router.post("/generate", response_model=GenerateResponse)
async def generate_content(request: GenerateRequest, background_tasks: BackgroundTasks):
    """
    生成指定格式的文案
    
    Args:
        request: 生成請求
        background_tasks: FastAPI 背景任務
        
    Returns:
        GenerateResponse: 生成結果
    """
    transcript_id = request.transcript_id
    
    # 添加調試日誌
    print(f"[DEBUG] 收到生成請求: transcript_id={transcript_id}, formats={[f.value for f in request.formats]}")
    print(f"[DEBUG] 當前 files_storage 中的 file_ids: {list(files_storage.keys())[:5]}")
    
    # 檢查逐字稿是否存在
    file_info = None
    for fid, info in files_storage.items():
        if info.get("transcript_id") == transcript_id or fid == transcript_id:
            file_info = info
            print(f"[DEBUG] 找到對應的檔案: file_id={fid}, transcript_id={info.get('transcript_id')}")
            break
    
    if not file_info or "transcript" not in file_info:
        # 添加詳細的調試信息，幫助排查問題
        print(f"[ERROR] 逐字稿不存在: transcript_id={transcript_id}")
        print(f"[ERROR] files_storage 中的內容:")
        for fid, info in files_storage.items():
            print(f"[ERROR]   file_id={fid}, transcript_id={info.get('transcript_id')}, has_transcript={'transcript' in info}")
        raise HTTPException(status_code=404, detail=f"逐字稿不存在: transcript_id={transcript_id}")
    
    # 生成任務 ID
    task_id = str(uuid.uuid4())
    
    # 初始化任務狀態
    tasks_storage[task_id] = {
        "status": TaskStatus.PENDING,
        "progress": 0.0,
        "message": "等待生成",
        "formats": [f.value for f in request.formats]
    }
    
    # 在背景執行生成任務
    background_tasks.add_task(
        generate_content_task,
        task_id,
        file_info["transcript"],
        request.formats,
        transcript_id,
        request.custom_prompt
    )
    
    return GenerateResponse(
        task_id=task_id,
        status=TaskStatus.PENDING,
        formats=request.formats,
        message="文案生成任務已啟動"
    )


async def generate_content_task(
    task_id: str,
    transcript: str,
    formats: List[ContentFormat],
    file_id: str,
    custom_prompt: str = None
):
    """
    背景任務：生成文案
    
    Args:
        task_id: 任務 ID
        transcript: 逐字稿文字
        formats: 要生成的格式列表
        file_id: 檔案 ID
        custom_prompt: 自訂提示詞
    """
    try:
        # 更新任務狀態
        tasks_storage[task_id]["status"] = TaskStatus.PROCESSING
        tasks_storage[task_id]["progress"] = 10.0
        tasks_storage[task_id]["message"] = "正在生成文案..."
        
        # 生成文案
        content_generator = get_content_generator()
        results = content_generator.generate_content(
            transcript,
            formats,
            file_id,
            custom_prompt
        )
        
        # 更新任務狀態為完成
        tasks_storage[task_id]["status"] = TaskStatus.COMPLETED
        tasks_storage[task_id]["progress"] = 100.0
        tasks_storage[task_id]["message"] = "文案生成完成"
        tasks_storage[task_id]["result"] = results
        print(f"[INFO] 文案生成完成: task_id={task_id}, file_id={file_id}, formats={[f.value for f in formats]}")
        
    except Exception as e:
        # 更新任務狀態為失敗
        tasks_storage[task_id]["status"] = TaskStatus.FAILED
        tasks_storage[task_id]["message"] = f"生成失敗: {str(e)}"
        tasks_storage[task_id]["error"] = str(e)
        # 記錄錯誤
        print(f"[ERROR] 生成文案失敗: task_id={task_id}, file_id={file_id}, formats={[f.value for f in formats]}, error={str(e)}")
        import traceback
        traceback.print_exc()


@router.post("/generate-from-transcript", response_model=GenerateResponse)
async def generate_from_transcript(request: GenerateFromTranscriptRequest, background_tasks: BackgroundTasks):
    """
    直接使用逐字稿文字生成文案（免 transcript_id 與 MP4 上傳流程）

    Args:
        request: 生成請求，包含逐字稿全文與格式列表
        background_tasks: FastAPI 背景任務

    Returns:
        GenerateResponse: 生成任務資訊（與 /generate 保持一致，方便前端共用輪詢機制）
    """
    transcript_text = request.transcript

    # 基本驗證：逐字稿內容不可為空
    if not transcript_text or not transcript_text.strip():
        raise HTTPException(status_code=400, detail="逐字稿內容不可為空")

    # 生成任務 ID（與 /generate 共用任務結構與輪詢機制）
    task_id = str(uuid.uuid4())

    # 初始化任務狀態
    tasks_storage[task_id] = {
        "status": TaskStatus.PENDING,
        "progress": 0.0,
        "message": "等待生成",
        "formats": [f.value for f in request.formats],
    }

    # 這裡使用一個臨時 file_id，僅用於命名輸出檔案，不對應實際上傳檔案
    temp_file_id = f"manual_{task_id}"

    # 在背景執行生成任務，重用同一個 generate_content_task 邏輯
    background_tasks.add_task(
        generate_content_task,
        task_id,
        transcript_text,
        request.formats,
        temp_file_id,
        None,  # 目前手動貼上流程不支援 custom_prompt，有需要可在前端開欄位後再傳入
    )

    return GenerateResponse(
        task_id=task_id,
        status=TaskStatus.PENDING,
        formats=request.formats,
        message="文案生成任務已啟動（手動逐字稿）",
    )


@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """
    查詢任務狀態
    
    Args:
        task_id: 任務 ID
        
    Returns:
        TaskStatusResponse: 任務狀態
    """
    if task_id not in tasks_storage:
        # 只在任務不存在時打印日誌（這是錯誤情況，需要記錄）
        print(f"[DEBUG] 任務不存在: {task_id}")
        print(f"[DEBUG] 現有任務ID列表: {list(tasks_storage.keys())[:10]}")  # 只顯示前10個
        raise HTTPException(status_code=404, detail=f"任務不存在: {task_id}")
    
    task = tasks_storage[task_id]
    
    # 移除頻繁的狀態查詢日誌，因為前端每0.2秒輪詢一次，會產生大量日誌
    # 只在需要調試時可以臨時啟用
    # print(f"[DEBUG] 查詢任務狀態: {task_id}, 狀態: {task.get('status')}, 進度: {task.get('progress')}")
    
    return TaskStatusResponse(
        task_id=task_id,
        status=task["status"],
        progress=task.get("progress", 0.0),
        total_duration=task.get("total_duration"),
        processed_duration=task.get("processed_duration"),
        message=task.get("message"),
        result=task.get("result"),
        error=task.get("error")
    )


