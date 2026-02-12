"""
主要 API 路由
定義所有 API 端點
"""
import asyncio
import os
import uuid
import json
from pathlib import Path
from typing import List
import math  # 用於計算切片數量
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from app.models.schemas import (
    UploadResponse, ProcessRequest, ProcessResponse, GenerateRequest, GenerateResponse,
    TaskStatusResponse, TaskStatus, ContentFormat, GenerateFromTranscriptRequest
)
from app.api.upload import handle_upload
from app.services.transcription_service import get_transcription_service
from app.services.content_generator import get_content_generator
from app.config import settings
from app.utils.file_handler import (
    generate_file_id, validate_file, save_uploaded_file,
    get_file_path, file_exists, get_output_path  # 取得輸出檔案路徑
)

router = APIRouter()

# 任務狀態儲存（生產環境應使用 Redis 或資料庫）
tasks_storage = {}
files_storage = {}  # 儲存檔案資訊


@router.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """
    上傳 MP3 檔案
    
    Args:
        file: 上傳的 MP3 檔案
        
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
    處理檔案：轉換 MP3 為逐字稿（使用 Gemini API）
    
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
        "file_id": file_id,
        "transcript_chunks": [],  # 用於儲存串流文字片段
        "full_transcript": ""  # 完整逐字稿
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
    背景任務：上傳檔案到 Gemini（不執行轉錄，轉錄由 SSE endpoint 處理）
    
    Args:
        task_id: 任務 ID
        file_id: 檔案 ID
        include_timestamps: 是否包含時間戳記（保留參數以相容，但不使用）
    """
    gemini_file_name = None
    
    try:
        # 確保任務存在
        if task_id not in tasks_storage:
            print(f"[ERROR] 任務不存在於 tasks_storage: {task_id}")
            return
        
        # 更新任務狀態為處理中
        tasks_storage[task_id]["status"] = TaskStatus.PROCESSING
        tasks_storage[task_id]["progress"] = 5.0
        tasks_storage[task_id]["message"] = "正在準備上傳..."
        print(f"[DEBUG] 開始處理任務: {task_id}, 進度: 5%")
        
        # 取得檔案路徑（現在只支援 MP3）
        file_info = files_storage[file_id]
        file_path = file_info["file_path"]
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext != ".mp3":
            raise ValueError(f"不支援的檔案格式: {file_ext}，僅支援 MP3")
        
        audio_path = file_path
        tasks_storage[task_id]["progress"] = 10.0
        tasks_storage[task_id]["message"] = "音訊檔案就緒，開始上傳到 Gemini..."
        print(f"[DEBUG] 使用 MP3 檔案: {audio_path} (task_id={task_id})")
        
        # 取得轉錄服務實例（用於上傳檔案）
        transcription_service = get_transcription_service()
        
        # 上傳檔案到 Gemini（在背景執行緒中執行）
        tasks_storage[task_id]["progress"] = 20.0
        tasks_storage[task_id]["message"] = "正在上傳音訊到 Gemini..."
        print(f"[DEBUG] 開始上傳到 Gemini: task_id={task_id}")
        
        # 在背景執行緒中上傳檔案
        loop = asyncio.get_event_loop()
        
        def upload_to_gemini():
            """上傳檔案到 Gemini（同步函數）"""
            import google.generativeai as genai
            from app.config import settings
            
            genai.configure(api_key=settings.GEMINI_API_KEY)
            print(f"[DEBUG] 正在上傳音訊到 Gemini: {audio_path}")
            audio_file = genai.upload_file(path=audio_path)
            return audio_file.name
        
        gemini_file_name = await loop.run_in_executor(None, upload_to_gemini)
        
        # 上傳完成，更新進度
        tasks_storage[task_id]["progress"] = 100.0
        tasks_storage[task_id]["message"] = "✅ 上傳完成，準備開始轉錄"
        tasks_storage[task_id]["status"] = TaskStatus.COMPLETED  # 標記為完成（上傳階段完成）
        
        # 儲存 Gemini 檔案名稱到任務狀態，供 SSE endpoint 使用
        tasks_storage[task_id]["gemini_file_name"] = gemini_file_name
        tasks_storage[task_id]["file_path"] = audio_path
        
        print(f"[INFO] Gemini 上傳完成: task_id={task_id}, gemini_file_name={gemini_file_name}")
        print(f"[INFO] 轉錄將由 SSE endpoint 處理")
        
    except Exception as e:
        # 更新任務狀態為失敗
        tasks_storage[task_id]["status"] = TaskStatus.FAILED
        tasks_storage[task_id]["progress"] = 0.0
        tasks_storage[task_id]["message"] = f"❌ 上傳失敗: {str(e)}"
        tasks_storage[task_id]["error"] = str(e)
        # 記錄錯誤
        print(f"[ERROR] 上傳任務失敗: task_id={task_id}, file_id={file_id}, error={str(e)}")
        import traceback
        traceback.print_exc()
        
        # 嘗試清理 Gemini 檔案
        if gemini_file_name:
            try:
                transcription_service = get_transcription_service()
                transcription_service.cleanup_gemini_file(gemini_file_name)
            except:
                pass


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


@router.get("/transcribe-stream/{task_id}")
async def transcribe_stream(task_id: str):
    """
    SSE endpoint：即時串流轉錄結果
    
    Args:
        task_id: 任務 ID
        
    Returns:
        StreamingResponse: SSE 串流回應
    """
    if task_id not in tasks_storage:
        raise HTTPException(status_code=404, detail=f"任務不存在: {task_id}")
    
    task = tasks_storage[task_id]
    file_id = task.get("file_id")
    
    if not file_id or file_id not in files_storage:
        raise HTTPException(status_code=404, detail="檔案不存在")
    
    file_info = files_storage[file_id]
    file_path = file_info["file_path"]
    
    # 檢查是否已經上傳到 Gemini（從任務狀態中取得）
    gemini_file_name_from_task = task.get("gemini_file_name")
    
    async def generate_stream():
        """生成 SSE 事件流（簡化版：直接迭代生成器，避免 Thread + Queue 阻塞）"""
        transcription_service = get_transcription_service()
        gemini_file_name = task.get("gemini_file_name")
        
        try:
            # 如果已經上傳完成，直接開始轉錄；否則等待上傳完成
            if gemini_file_name:
                # 已經上傳，發送開始轉錄事件
                yield f"data: {json.dumps({'type': 'progress', 'message': '開始轉錄...'})}\n\n"
                await asyncio.sleep(0.01)  # 強迫數據發送
            else:
                # 等待上傳完成
                yield f"data: {json.dumps({'type': 'progress', 'message': '等待上傳完成...'})}\n\n"
                await asyncio.sleep(0.01)  # 強迫數據發送
                
                # 輪詢直到上傳完成
                max_wait = 60  # 最多等待 60 秒
                wait_count = 0
                while not gemini_file_name and wait_count < max_wait:
                    await asyncio.sleep(1)
                    if task_id in tasks_storage:
                        gemini_file_name = tasks_storage[task_id].get("gemini_file_name")
                        if gemini_file_name:
                            yield f"data: {json.dumps({'type': 'progress', 'message': '上傳完成，開始轉錄...'})}\n\n"
                            await asyncio.sleep(0.01)  # 強迫數據發送
                            break
                    wait_count += 1
                
                if not gemini_file_name:
                    yield f"data: {json.dumps({'type': 'error', 'message': '上傳超時'})}\n\n"
                    return
            
            # 🟢 重點：使用簡化的 Queue 邏輯，在執行緒中運行生成器，每次只讀取一個事件
            event_queue = asyncio.Queue()
            loop = asyncio.get_event_loop()
            
            def run_generator():
                """在執行緒中運行生成器，將事件放入 queue"""
                try:
                    # 直接迭代生成器
                    for event in transcription_service.transcribe_stream_with_file(
                        gemini_file_name, file_id
                    ):
                        # 將事件放入 queue（使用線程安全的方式）
                        loop.call_soon_threadsafe(event_queue.put_nowait, event)
                    # 發送結束標記
                    loop.call_soon_threadsafe(event_queue.put_nowait, None)
                except Exception as e:
                    # 發送錯誤事件
                    error_event = {
                        "type": "error",
                        "message": f"轉錄失敗: {str(e)}",
                        "gemini_file_name": gemini_file_name
                    }
                    loop.call_soon_threadsafe(event_queue.put_nowait, error_event)
                    loop.call_soon_threadsafe(event_queue.put_nowait, None)
            
            # 在背景執行緒中啟動轉錄
            import threading
            thread = threading.Thread(target=run_generator, daemon=True)
            thread.start()
            
            # 從 queue 中讀取事件並發送 SSE（每次只讀取一個，立即 yield 並 await）
            print(f"[SSE] 開始從 queue 讀取事件，task_id={task_id}")
            event_count = 0
            while True:
                # 等待事件（使用較短的超時時間）
                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=0.1)
                except asyncio.TimeoutError:
                    # 超時，繼續等待（避免阻塞）
                    continue
                
                event_count += 1
                if event_count <= 3 or event_count % 10 == 0:
                    print(f"[SSE] 從 queue 讀取到事件 #{event_count}, 類型: {event.get('type') if event else 'None'}")
                
                # None 表示結束
                if event is None:
                    break
                
                event_type = event.get("type")
                
                if event_type == "progress":
                    yield f"data: {json.dumps({'type': 'progress', 'message': event.get('message', '')})}\n\n"
                    await asyncio.sleep(0.01)  # 🔴 關鍵：給予非同步循環喘息機會，強迫數據發送
                
                elif event_type == "chunk":
                    # 文字片段 - 立即發送
                    chunk_text = event.get("text", "")
                    # 更新任務狀態中的逐字稿
                    if "transcript_chunks" not in tasks_storage[task_id]:
                        tasks_storage[task_id]["transcript_chunks"] = []
                    tasks_storage[task_id]["transcript_chunks"].append(chunk_text)
                    tasks_storage[task_id]["full_transcript"] = tasks_storage[task_id].get("full_transcript", "") + chunk_text
                    
                    # 構建 SSE 事件資料
                    chunk_data = {'type': 'chunk', 'text': chunk_text}
                    sse_message = f"data: {json.dumps(chunk_data, ensure_ascii=False)}\n\n"
                    
                    # 添加調試日誌（僅記錄前幾個 chunk，避免日誌過多）
                    chunk_count = len(tasks_storage[task_id]["transcript_chunks"])
                    if chunk_count <= 3 or chunk_count % 10 == 0:
                        print(f"[SSE] 發送 chunk #{chunk_count}, 長度: {len(chunk_text)} 字元, 預覽: {chunk_text[:50] if len(chunk_text) > 50 else chunk_text}")
                    
                    yield sse_message
                    await asyncio.sleep(0.01)  # 🔴 關鍵：給予非同步循環喘息機會，強迫數據發送
                
                elif event_type == "complete":
                    # 轉錄完成
                    full_text = event.get("full_text", "")
                    file_path_result = event.get("file_path", "")
                    event_gemini_file_name = event.get("gemini_file_name")
                    
                    # 更新任務狀態
                    tasks_storage[task_id]["status"] = TaskStatus.COMPLETED
                    tasks_storage[task_id]["progress"] = 100.0
                    tasks_storage[task_id]["message"] = "✅ 轉錄完成"
                    tasks_storage[task_id]["result"] = {
                        "transcript": full_text,
                        "transcript_file": file_path_result,
                        "language": "zh"
                    }
                    
                    # 儲存逐字稿
                    files_storage[file_id]["transcript_id"] = file_id
                    files_storage[file_id]["transcript"] = full_text
                    
                    yield f"data: {json.dumps({'type': 'complete', 'full_text': full_text, 'file_path': file_path_result})}\n\n"
                    await asyncio.sleep(0.01)  # 強迫數據發送
                    
                    # 清理 Gemini 檔案
                    if event_gemini_file_name:
                        transcription_service.cleanup_gemini_file(event_gemini_file_name)
                    
                    break
                
                elif event_type == "error":
                    # 錯誤事件
                    error_msg = event.get("message", "轉錄失敗")
                    event_gemini_file_name = event.get("gemini_file_name")
                    
                    tasks_storage[task_id]["status"] = TaskStatus.FAILED
                    tasks_storage[task_id]["error"] = error_msg
                    
                    yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
                    await asyncio.sleep(0.01)  # 強迫數據發送
                    
                    # 清理 Gemini 檔案
                    if event_gemini_file_name:
                        transcription_service.cleanup_gemini_file(event_gemini_file_name)
                    
                    break
                    
        except Exception as e:
            # 發生未預期的錯誤
            error_msg = f"轉錄過程發生錯誤: {str(e)}"
            tasks_storage[task_id]["status"] = TaskStatus.FAILED
            tasks_storage[task_id]["error"] = error_msg
            
            yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
            await asyncio.sleep(0.01)  # 強迫數據發送
            
            # 嘗試清理
            if gemini_file_name:
                try:
                    transcription_service.cleanup_gemini_file(gemini_file_name)
                except:
                    pass
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # 禁用 Nginx 緩衝
        }
    )


