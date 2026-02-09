#!/bin/bash

# 語音直播切片工具啟動腳本

echo "🚀 啟動語音直播切片工具..."

# 檢查 .env 檔案是否存在
if [ ! -f .env ]; then
    echo "⚠️  未找到 .env 檔案，正在從 env.example 複製..."
    cp env.example .env
    echo "✅ 已建立 .env 檔案，請編輯並填入您的 API 金鑰"
    echo "📝 編輯 .env 檔案後，再次執行此腳本"
    exit 1
fi

# 檢查 Docker 是否運行
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker 未運行，請先啟動 Docker"
    exit 1
fi

# 啟動服務
echo "🐳 使用 Docker Compose 啟動服務..."
docker-compose up -d

echo ""
echo "✅ 服務已啟動！"
echo ""
echo "📱 前端界面: http://localhost:3000"
echo "📚 API 文件: http://localhost:8000/docs"
echo ""
echo "查看日誌: docker-compose logs -f"
echo "停止服務: docker-compose down"
