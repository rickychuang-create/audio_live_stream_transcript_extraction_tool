#!/bin/bash
# Whisper 安裝腳本（Linux/Mac）
# 解決 openai-whisper 安裝時的 setuptools 問題

echo "🔧 更新 pip、setuptools 和 wheel..."
python -m pip install --upgrade pip setuptools wheel

echo ""
echo "📦 安裝 openai-whisper..."
pip install openai-whisper --no-build-isolation

echo ""
echo "✅ 安裝完成！"
