# 語音直播切片工具

一個完整的語音直播內容處理工具，可以將 MP4 影片轉換為逐字稿，並自動生成多種格式的文案（社團文章、Email、YT Shorts 腳本、精華摘要）。

## 功能特色

- 🎬 **MP4 轉 MP3**：自動提取影片中的音訊
- 🎙️ **語音轉文字**：使用 OpenAI Whisper 進行高準確度的語音識別
- ✍️ **多格式文案生成**：
  - 社團文章文案
  - Email 文案
  - YT Shorts 短影音腳本
  - 整場精華摘要
- 📦 **批量處理**：支援一次處理多個檔案
- 🌐 **Web 界面**：直觀易用的網頁操作界面
- 🐳 **Docker 部署**：一鍵啟動，本地部署簡單

## 技術架構

### 後端
- **FastAPI**：現代化的 Python Web 框架
- **Whisper**：OpenAI 的語音識別模型
- **MoviePy**：音訊處理
- **OpenAI/Anthropic API**：文案生成

### 前端
- **React**：現代化的前端框架
- **Axios**：HTTP 客戶端

## 快速開始

### 前置需求

- Docker 和 Docker Compose
- OpenAI API 金鑰或 Anthropic API 金鑰

### 安裝步驟

1. **複製環境變數檔案**
   ```bash
   cp .env.example .env
   ```

2. **編輯 `.env` 檔案**
   - 填入您的 OpenAI API 金鑰或 Anthropic API 金鑰
   - 調整其他配置（如 Whisper 模型等級）

3. **啟動服務**
   ```bash
   docker-compose up -d
   ```

4. **存取應用程式**
   - 前端界面：http://localhost:3000
   - API 文件：http://localhost:8000/docs

### 本地開發（不使用 Docker）

#### 後端開發

1. 進入後端目錄
   ```bash
   cd backend
   ```

2. 建立虛擬環境
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

3. 安裝依賴
   ```bash
   pip install -r requirements.txt
   ```
   
   **如果遇到安裝錯誤**：
   
   **問題 1: openai-whisper 安裝錯誤**（KeyError: '__version__'）
   ```bash
   # 方法 1: 使用提供的安裝腳本（推薦）
   # Windows:
   install_whisper.bat
   # Linux/Mac:
   chmod +x install_whisper.sh
   ./install_whisper.sh
   
   # 方法 2: 手動修復
   pip install --upgrade pip setuptools wheel
   pip install openai-whisper --no-build-isolation
   ```
   
   **問題 2: pydantic-core 編譯錯誤**（需要 Rust）
   ```bash
   # 更新 pip 和相關工具
   pip install --upgrade pip setuptools wheel
   
   # 使用更新的 pydantic 版本（已有預編譯 wheel）
   pip install "pydantic>=2.9.0" "pydantic-settings>=2.6.0"
   
   # 或者使用最小化依賴版本
   pip install -r requirements-minimal.txt
   ```

4. 設定環境變數（建立 `.env` 檔案）

5. 啟動服務
   ```bash
   uvicorn app.main:app --reload
   ```

#### 前端開發

1. 進入前端目錄
   ```bash
   cd frontend
   ```

2. 安裝依賴
   ```bash
   npm install
   ```
   
   **注意**：
   - 安裝時可能會看到一些 deprecation 警告，這些是 `react-scripts` 的依賴警告，不影響功能
   - **請勿使用 `npm audit fix --force`**，這會移除太多依賴導致應用無法運行
   - 如果遇到安全漏洞，可以執行 `npm audit fix`（不使用 `--force`）
   - 如果依賴安裝出現問題，可以執行修復腳本：
     ```bash
     # Windows:
     fix-install.bat
     # Linux/Mac:
     rm -rf node_modules package-lock.json && npm install
     ```

3. 啟動開發伺服器
   ```bash
   npm start
   ```

## 使用說明

### 基本流程

1. **上傳 MP4 檔案**
   - 支援拖放或點擊選擇檔案
   - 支援批量上傳

2. **自動處理**
   - 系統會自動提取音訊並轉換為逐字稿
   - 處理進度會即時顯示

3. **選擇格式**
   - 選擇要生成的文案格式（可多選）
   - 點擊「生成文案」按鈕

4. **查看結果**
   - 預覽生成的文案內容
   - 複製或下載結果

### API 使用

#### 上傳檔案
```bash
curl -X POST "http://localhost:8000/api/upload" \
  -F "file=@your_video.mp4"
```

#### 處理檔案
```bash
curl -X POST "http://localhost:8000/api/process" \
  -H "Content-Type: application/json" \
  -d '{"file_id": "your_file_id", "include_timestamps": false}'
```

#### 生成文案
```bash
curl -X POST "http://localhost:8000/api/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "transcript_id": "your_transcript_id",
    "formats": ["community_post", "email", "yt_post", "summary"]
  }'
```

#### 已有逐字稿時，直接生成文案（跳過 MP4 上傳與轉錄）
```bash
curl -X POST "http://localhost:8000/api/generate-from-transcript" \
  -H "Content-Type: application/json" \
  -d '{
    "transcript": "這裡放完整的逐字稿文字內容",
    "formats": ["community_post", "email", "yt_post", "summary"]
  }'
```

## 配置說明

### 環境變數

| 變數名稱 | 說明 | 預設值 |
|---------|------|--------|
| `OPENAI_API_KEY` | OpenAI API 金鑰 | - |
| `ANTHROPIC_API_KEY` | Anthropic API 金鑰 | - |
| `GEMINI_API_KEY` | Google Gemini API 金鑰 | - |
| `WHISPER_MODEL` | Whisper 模型等級 | `base` |
| `DEFAULT_LLM_PROVIDER` | 預設 LLM 提供者 | `openai`、`anthropic` 或 `gemini` |
| `OPENAI_MODEL` | OpenAI 模型名稱 | `gpt-4o-mini` |
| `ANTHROPIC_MODEL` | Anthropic 模型名稱 | `claude-3-haiku-20240307` |
| `GEMINI_MODEL` | Gemini 模型名稱 | `gemini-pro` |
| `MAX_FILE_SIZE` | 最大檔案大小（bytes） | `524288000` (500MB) |

### Whisper 模型選擇

- **tiny**：最快，準確度較低
- **base**：平衡速度和準確度（推薦）
- **small**：較準確，速度較慢
- **medium**：高準確度，速度慢
- **large**：最高準確度，速度最慢

## 專案結構

```
語音直播切片/
├── backend/              # 後端服務
│   ├── app/
│   │   ├── main.py       # FastAPI 主應用
│   │   ├── config.py     # 配置管理
│   │   ├── models/       # 數據模型
│   │   ├── services/     # 業務邏輯
│   │   ├── api/          # API 路由
│   │   └── utils/        # 工具函數
│   └── requirements.txt  # Python 依賴
├── frontend/             # 前端應用
│   ├── src/
│   │   ├── components/   # React 組件
│   │   ├── services/     # API 服務
│   │   └── App.js        # 主應用
│   └── package.json      # Node 依賴
├── docker-compose.yml    # Docker Compose 配置
├── .env.example          # 環境變數範例
└── README.md             # 本檔案
```

## 未來擴展

- [ ] 任務隊列系統（Celery + Redis）
- [ ] 資料庫整合（儲存處理歷史）
- [ ] 用戶認證系統
- [ ] 雲端存儲整合（S3）
- [ ] 更多文案格式支援
- [ ] 自訂 Prompt 模板

## 授權

MIT License

## 貢獻

歡迎提交 Issue 和 Pull Request！

## 問題回報

如遇到問題，請在 GitHub 上建立 Issue，並提供：
- 錯誤訊息
- 操作步驟
- 環境資訊（OS、Python 版本等）

## 聯絡方式

如有任何問題或建議，歡迎聯絡！
