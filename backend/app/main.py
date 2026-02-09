"""
FastAPI 主應用程式
提供 RESTful API 服務
"""
import os
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import settings
from app.api.routes import router

# 配置日誌：減少 Uvicorn 訪問日誌的輸出
# 只記錄警告級別以上的日誌，減少頻繁的狀態查詢日誌
# 應用程式使用 print() 輸出日誌，不受此配置影響
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

# 建立 FastAPI 應用實例
app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    debug=settings.DEBUG
)

# 設定 CORS（允許前端跨域請求）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生產環境應設定具體的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 註冊 API 路由
app.include_router(router, prefix="/api", tags=["api"])

# 提供靜態檔案服務（用於下載生成的檔案）
if os.path.exists(settings.OUTPUT_DIR):
    app.mount("/outputs", StaticFiles(directory=settings.OUTPUT_DIR), name="outputs")

if os.path.exists(settings.UPLOAD_DIR):
    app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")


@app.get("/")
async def root():
    """根路徑，返回 API 資訊"""
    return {
        "message": "語音直播切片工具 API",
        "version": settings.API_VERSION,
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """健康檢查端點"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    # 設置日誌級別為 INFO
    # 訪問日誌已經通過 logging.getLogger("uvicorn.access") 設置為 WARNING，所以不會顯示
    # 應用程式使用 print() 輸出，不受此配置影響
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_level="info"
    )
