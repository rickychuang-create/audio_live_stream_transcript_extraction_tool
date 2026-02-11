## 語音直播切片工具（Audio Live Stream Transcript Extraction Tool）

一個專門為「語音直播內容」設計的完整處理工具，可以將 MP4 直播影片轉換為逐字稿，並自動生成多種格式的文案（社團摘要、Email 導流信、YouTube 社群貼文、精華摘要），現在也支援**直接貼上逐字稿文字生成文案**的流程。

### 功能特色

- 🎬 **MP4 轉 MP3**：自動提取影片中的音訊，為 Whisper 轉錄做準備  
- 🎙️ **語音轉文字**：使用 OpenAI Whisper 將長時間直播精準轉成逐字稿  
- ✍️ **多格式文案生成**（對應後端 `ContentFormat` 與前端 `FormatSelector`）：
  - 社團摘要文案：給 App 免費社團使用的直播整理貼文
  - Email 文案：喚回 / 導流用的簡短 Email
  - YouTube 社群貼文（`yt_post`）：以 Mike 第一人稱口吻的社群貼
  - 精華摘要：3 點重點式總結
- 📝 **直接貼上逐字稿生成**：
  - 若你已經有文字逐字稿，可在前端第二個 Tab 直接貼上
  - 不需要 MP4 上傳與轉錄流程，直接呼叫 `/api/generate-from-transcript`
- ✂️ **長直播處理與切片設計**：
  - 後端會將音訊切成小段依序送進 Whisper，避免一次處理超大檔案
  - 支援處理長度較長的直播檔（實際上前端一次只上傳一個 MP4）
- 🌐 **Web 界面**：直觀的 React 介面，清楚呈現上傳、轉錄、生成三個步驟
- 🐳 **Docker 部署**：提供 `docker-compose.yml` 與 `start.bat` / `start.sh`，一鍵啟動

### 技術架構

#### 後端
- **FastAPI**：現代化的 Python Web 框架，負責 REST API 與任務狀態查詢
- **Whisper**：OpenAI 的語音識別模型，用於語音轉文字
- **MoviePy**：負責從 MP4 提取音訊並進行切片處理
- **OpenAI / Anthropic / Google Gemini API**：用於文案生成與（選用）標點符號處理
- **pydantic-settings**：集中管理 `.env` 與環境變數配置（見 `backend/app/config.py`）

#### 前端
- **React**：建立單頁應用（SPA），整合上傳、轉錄、生成結果展示
- **Axios**：呼叫後端 `/api` 相關端點的 HTTP 客戶端

## 快速開始

### 前置需求

- 已安裝 Docker 與 Docker Compose
- 至少一組 LLM API 金鑰：  
  - 可選：OpenAI / Anthropic / Google Gemini（至少擁有其中一種即可）

### 使用啟動腳本（推薦）

專案根目錄已提供啟動腳本，會自動檢查 `.env` 與 Docker 狀態：

1. **第一次使用：建立 `.env` 並填入金鑰**
   - 請先開啟 `env.example`，確認欄位與說明
   - 將其複製為 `.env` 並填入實際金鑰與模型設定：
     ```bash
     cp .env.example .env
     # Windows 用戶也可以直接執行 start.bat，若找不到 .env 會自動幫你複製一份
     ```

2. **啟動服務**
   - Windows：
     ```bash
     start.bat
     ```
   - macOS / Linux：
     ```bash
     chmod +x start.sh
     ./start.sh
     ```
   - 腳本會：
     - 檢查 `.env` 是否存在（不存在則從 `env.example` 複製）
     - 檢查 Docker 是否正在運行
     - 呼叫 `docker-compose up -d` 背景啟動所有服務

3. **存取應用程式**
   - 前端界面：`http://localhost:3000`
   - API 文件（Swagger）：`http://localhost:8000/docs`

### 直接使用 Docker Compose（手動）

如果你不想使用啟動腳本，也可以手動執行：

1. **複製環境變數檔案**
   ```bash
   cp .env.example .env
   ```

2. **編輯 `.env` 檔案**
   - 填入你的 OpenAI / Anthropic / Gemini API 金鑰（至少一種）
   - 視需求調整 Whisper 模型與 LLM 模型名稱

3. **啟動服務**
   ```bash
   docker-compose up -d
   ```

4. **存取應用程式**
   - 前端界面：`http://localhost:3000`
   - API 文件：`http://localhost:8000/docs`

### 本地開發（不使用 Docker）

#### 後端開發

1. 進入後端目錄
   ```bash
   cd backend
   ```

2. 建立虛擬環境
   ```bash
   python -m venv venv
   # macOS / Linux
   source venv/bin/activate
   # Windows
   # venv\Scripts\activate
   ```

3. 安裝依賴
   ```bash
   pip install -r requirements.txt
   ```
   
   **如果遇到安裝錯誤，可以依照以下指引排除：**
   
   **問題 1：`openai-whisper` 安裝錯誤（KeyError: '__version__'）**
   ```bash
   # 方法 1：使用專案提供的安裝腳本（推薦）
   # Windows:
   install_whisper.bat
   # Linux / macOS:
   chmod +x install_whisper.sh
   ./install_whisper.sh
   
   # 方法 2：手動修復環境後再安裝
   pip install --upgrade pip setuptools wheel
   pip install openai-whisper --no-build-isolation
   ```
   
   **問題 2：pydantic-core 編譯錯誤（缺少 Rust 或編譯工具）**
   ```bash
   # 更新 pip 與相關工具
   pip install --upgrade pip setuptools wheel
   
   # 安裝較新版本的 pydantic 與 pydantic-settings（通常有預編譯 wheel）
   pip install "pydantic>=2.9.0" "pydantic-settings>=2.6.0"
   
   # 或改用最小化依賴版本
   pip install -r requirements-minimal.txt
   ```

4. 設定環境變數（建立 `.env` 檔案）
   - 可直接複製根目錄的 `env.example` 到 `backend` 目錄，或在專案根目錄建立 `.env`
   - `backend/app/config.py` 會自動尋找合適位置的 `.env`

5. 啟動後端服務
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
   
   **注意：**
   - 安裝時可能會看到一些 deprecation 警告，這些是 `react-scripts` 的依賴警告，通常不影響功能
   - **請勿使用 `npm audit fix --force`**，這可能移除必要依賴導致無法啟動
   - 若有安全性警告，可先嘗試 `npm audit fix`（不加 `--force`）
   - 若遇到依賴衝突，可執行專案提供的修復腳本：
     ```bash
     # Windows:
     fix-install.bat
     # Linux / macOS:
     rm -rf node_modules package-lock.json && npm install
     ```

3. 啟動前端開發伺服器
   ```bash
   npm start
   ```

## 使用說明

### 前端操作流程

#### 模式一：使用 MP4 檔案（完整流程）

1. **上傳 MP4 檔案**
   - 支援拖放或點擊選擇檔案
   - 一次**只上傳一個檔案**（前端 `FileUpload` 組件會限制多選）

2. **自動處理**
   - 系統會：
     - 將 MP4 轉為音訊
     - 將音訊切片並送入 Whisper 轉成逐字稿
   - 前端會透過 `/api/status/{task_id}` 輪詢任務狀態，顯示處理進度

3. **選擇格式**
   - 在「MP4 轉逐字稿生成」這個 Tab 中，選擇要生成的文案格式（可多選）
   - 點擊「生成文案」按鈕，呼叫 `/api/generate`

4. **查看結果**
   - 頁面下方會顯示各格式生成的內容
   - 可以複製文字或下載文字檔案

#### 模式二：已有人聲逐字稿（跳過 MP4）

1. 切換到「直接貼上逐字稿生成」Tab  
2. 將完整逐字稿貼到文字框中  
3. 勾選要生成的文案格式（與模式一共用同一組格式）  
4. 點擊「生成文案」，前端會呼叫 `/api/generate-from-transcript`  
5. 生成結果會顯示在同一張卡片下方，可複製或下載

### API 使用

#### 上傳檔案（MP4）
```bash
curl -X POST "http://localhost:8000/api/upload" \
  -F "file=@your_video.mp4"
```

#### 處理檔案（觸發轉錄任務）
```bash
curl -X POST "http://localhost:8000/api/process" \
  -H "Content-Type: application/json" \
  -d '{"file_id": "your_file_id", "include_timestamps": false}'
```

#### 查詢任務狀態
```bash
curl -X GET "http://localhost:8000/api/status/your_task_id"
```

#### 根據轉錄結果生成文案
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

以下是與專案相關的主要環境變數；建議直接修改根目錄的 `env.example` 來了解目前支援的完整列表：

| 變數名稱 | 說明 | 典型預設 / 建議值 |
|---------|------|-------------------|
| `OPENAI_API_KEY` | OpenAI API 金鑰 | 無預設，需自行填入 |
| `ANTHROPIC_API_KEY` | Anthropic API 金鑰 | 無預設，需自行填入 |
| `GEMINI_API_KEY` | Google Gemini API 金鑰 | 無預設，需自行填入 |
| `WHISPER_MODEL` | Whisper 模型等級 | `base`（速度與準確度平衡） |
| `DEFAULT_LLM_PROVIDER` | 預設 LLM 提供者 | `openai` / `anthropic` / `gemini` |
| `OPENAI_MODEL` | OpenAI 模型名稱 | `gpt-4o-mini`（見 `env.example`） |
| `ANTHROPIC_MODEL` | Anthropic 模型名稱 | `claude-3-haiku-20240307` |
| `GEMINI_MODEL` | Gemini 模型名稱 | `gemini-2.5-flash` |
| `MAX_FILE_SIZE` | 最大檔案大小（bytes） | `524288000`（約 500MB） |
| `DEBUG` | 是否啟用 FastAPI debug 模式 | `false` |
| `ENABLE_PUNCTUATION` | 是否啟用 Gemini 標點 / 分段處理 | 預設啟用（見 `config.py`） |

### Whisper 模型選擇

- **tiny**：最快，準確度較低，適合測試
- **base**：速度與準確度平衡（預設推薦值）
- **small**：較高準確度、速度稍慢
- **medium**：高準確度，速度慢
- **large**：最高準確度，速度最慢，需較高資源

## 專案結構

```text
語音直播切片/
├── backend/                 # 後端服務
│   ├── app/
│   │   ├── main.py          # FastAPI 主應用（掛載 /api 路由與靜態檔案）
│   │   ├── config.py        # 配置與環境變數管理（pydantic-settings）
│   │   ├── models/          # Pydantic 模型與 Enum 定義
│   │   ├── services/        # 業務邏輯（轉錄、文案生成、標點處理等）
│   │   ├── api/             # API 路由與上傳處理
│   │   └── utils/           # 共用工具（檔案處理等）
│   ├── requirements.txt     # 完整 Python 依賴
│   └── requirements-minimal.txt # 最小化依賴版本
├── frontend/                # 前端 React 應用
│   ├── src/
│   │   ├── components/      # UI 組件（上傳、進度條、結果展示等）
│   │   ├── services/        # 封裝後端 API 呼叫
│   │   └── App.js           # 主應用：整合兩種輸入模式與流程
│   └── package.json         # Node 依賴
├── docker-compose.yml       # Docker Compose 配置
├── start.bat                # Windows 啟動腳本（含 .env 與 Docker 檢查）
├── start.sh                 # macOS / Linux 啟動腳本
├── .env.example             # 環境變數範例檔（請從此複製為 .env）
└── README.md                # 本檔案
```

## 未來擴展

- [ ] 任務隊列系統（Celery + Redis），將長任務改為真正背景排程
- [ ] 資料庫整合（儲存處理歷史與逐字稿 / 文案）
- [ ] 用戶認證與權限系統
- [ ] 雲端存儲整合（例如 S3，儲存原始檔與輸出結果）
- [ ] 更多文案格式支援與自訂模板管理介面
- [ ] 前端支援多語系與更多 UI 優化

## 授權

MIT License

## 貢獻

歡迎提交 Issue 和 Pull Request，一起讓工具更好用！

## 問題回報

如遇到問題，請在 GitHub 上建立 Issue，並提供：
- 錯誤訊息（含完整 stack trace 或 console log）
- 觸發錯誤的操作步驟與使用場景
- 環境資訊（OS、Python 版本、Node 版本、Docker 版本等）

## 聯絡方式

如有任何問題或建議，歡迎在 Issue 中留言或發 PR 討論。
