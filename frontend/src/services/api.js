/**
 * API 服務模組
 * 負責與後端 API 進行通訊
 */
import axios from 'axios';

// 建立 axios 實例
const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL || '/api',
  timeout: 900000, // 5 分鐘超時（處理大檔案）
});

/**
 * 上傳 MP4 檔案
 * @param {File} file - 要上傳的檔案
 * @param {Function} onUploadProgress - 上傳進度回調函數（可選）
 * @returns {Promise} 上傳結果
 */
export const uploadFile = async (file, onUploadProgress = null) => {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await api.post('/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    onUploadProgress: (progressEvent) => {
      if (onUploadProgress && progressEvent.total) {
        const percentCompleted = Math.round(
          (progressEvent.loaded * 100) / progressEvent.total
        );
        onUploadProgress(percentCompleted);
      }
    },
  });
  
  return response.data;
};

/**
 * 處理檔案（提取音訊並轉換為逐字稿）
 * @param {string} fileId - 檔案 ID
 * @param {boolean} includeTimestamps - 是否包含時間戳記
 * @returns {Promise} 處理結果
 */
export const processFile = async (fileId, includeTimestamps = false) => {
  const response = await api.post('/process', {
    file_id: fileId,
    include_timestamps: includeTimestamps,
  });
  
  return response.data;
};

/**
 * 查詢任務狀態
 * @param {string} taskId - 任務 ID
 * @returns {Promise} 任務狀態
 */
export const getTaskStatus = async (taskId) => {
  const response = await api.get(`/status/${taskId}`);
  return response.data;
};

/**
 * 生成文案
 * @param {string} transcriptId - 逐字稿 ID
 * @param {string[]} formats - 要生成的格式列表
 * @param {string} customPrompt - 自訂提示詞（可選）
 * @returns {Promise} 生成結果
 */
export const generateContent = async (transcriptId, formats, customPrompt = null) => {
  const response = await api.post('/generate', {
    transcript_id: transcriptId,
    formats: formats,
    custom_prompt: customPrompt,
  });
  
  return response.data;
};

/**
 * 直接使用逐字稿文字生成文案（免經過 MP4 上傳流程）
 *
 * 說明：
 * - 適用於使用者已經手上有文字逐字稿的情境
 * - 與 generateContent 最大差異在於：這裡直接傳 transcript 文字，而不是 transcript_id
 *
 * @param {string} transcript - 逐字稿全文
 * @param {string[]} formats - 要生成的格式列表（例如 ['community_post', 'email']）
 * @returns {Promise} 生成結果（具體結構依後端實作，建議與 /generate 一致）
 */
export const generateContentFromTranscript = async (transcript, formats) => {
  const response = await api.post('/generate-from-transcript', {
    transcript,
    formats,
  });

  return response.data;
};

/**
 * 使用 SSE (Server-Sent Events) 即時接收轉錄結果
 * 
 * @param {string} taskId - 任務 ID
 * @param {Function} onProgress - 進度回調函數 (message) => void
 * @param {Function} onChunk - 文字片段回調函數 (text) => void
 * @param {Function} onComplete - 完成回調函數 (fullText, filePath) => void
 * @param {Function} onError - 錯誤回調函數 (error) => void
 * @returns {EventSource} EventSource 實例（可用於關閉連線）
 */
export const transcribeStream = (taskId, { onProgress, onChunk, onComplete, onError }) => {
  const baseURL = process.env.REACT_APP_API_URL || '/api';
  const url = `${baseURL}/transcribe-stream/${taskId}`;
  
  console.log('[SSE] 建立 SSE 連線:', url);
  console.log('[SSE] 回調函數檢查:', {
    hasOnProgress: !!onProgress,
    hasOnChunk: !!onChunk,
    hasOnComplete: !!onComplete,
    hasOnError: !!onError
  });
  
  const eventSource = new EventSource(url);
  
  // 立即記錄連線狀態
  console.log('[SSE] EventSource 已創建，初始 readyState:', eventSource.readyState);
  console.log('[SSE] EventSource URL:', eventSource.url);
  
  // 連線開啟事件
  eventSource.onopen = () => {
    console.log('[SSE] ✅ 連線已建立，taskId:', taskId, 'readyState:', eventSource.readyState);
    console.log('[SSE] 連線狀態: OPEN，準備接收事件');
  };
  
  eventSource.onmessage = (event) => {
    try {
      console.log('[SSE] 收到事件，原始資料:', event.data);
      const data = JSON.parse(event.data);
      const { type, message, text, full_text, file_path } = data;
      
      console.log('[SSE] 解析後的事件類型:', type, '內容:', {
        message,
        textLength: text?.length,
        fullTextLength: full_text?.length,
        file_path
      });
      
      switch (type) {
        case 'progress':
          console.log('[SSE] 進度更新:', message);
          if (onProgress) onProgress(message || '');
          break;
          
        case 'chunk':
          console.log('[SSE] 收到文字片段，長度:', text?.length || 0, '內容預覽:', text?.substring(0, 50) || '');
          console.log('[SSE] onChunk 回調是否存在:', !!onChunk, '類型:', typeof onChunk);
          if (onChunk) {
            try {
              console.log('[SSE] 準備調用 onChunk 回調，傳入文字長度:', (text || '').length);
              onChunk(text || '');
              console.log('[SSE] ✅ 已成功調用 onChunk 回調');
            } catch (err) {
              console.error('[SSE] ❌ 調用 onChunk 回調時發生錯誤:', err);
            }
          } else {
            console.error('[SSE] ❌ onChunk 回調未定義！無法處理 chunk 事件');
          }
          break;
          
        case 'complete':
          console.log('[SSE] 轉錄完成，總長度:', full_text?.length || 0);
          if (onComplete) {
            onComplete(full_text || '', file_path || '');
            console.log('[SSE] 已調用 onComplete 回調');
          }
          eventSource.close();
          console.log('[SSE] 連線已關閉（完成）');
          break;
          
        case 'error':
          console.error('[SSE] 收到錯誤事件:', message);
          if (onError) {
            onError(message || '轉錄失敗');
            console.log('[SSE] 已調用 onError 回調');
          }
          eventSource.close();
          console.log('[SSE] 連線已關閉（錯誤）');
          break;
          
        default:
          console.warn('[SSE] 未知的 SSE 事件類型:', type, '完整資料:', data);
      }
    } catch (err) {
      console.error('[SSE] 解析 SSE 事件失敗:', err);
      console.error('[SSE] 原始事件資料:', event.data);
      if (onError) onError('解析轉錄結果失敗');
      eventSource.close();
    }
  };
  
  eventSource.onerror = (error) => {
    console.error('[SSE] SSE 連線錯誤:', error);
    console.error('[SSE] EventSource readyState:', eventSource.readyState);
    console.error('[SSE] EventSource url:', eventSource.url);
    console.error('[SSE] EventSource withCredentials:', eventSource.withCredentials);
    
    // readyState: 0 = CONNECTING, 1 = OPEN, 2 = CLOSED
    if (eventSource.readyState === EventSource.CONNECTING) {
      console.warn('[SSE] 連線中斷，正在重新連線...');
      // 不要立即關閉，讓 EventSource 自動重試
      return;
    }
    
    if (eventSource.readyState === EventSource.CLOSED) {
      console.error('[SSE] 連線已關閉，可能是伺服器端關閉或網路問題');
      if (onError) onError('連線錯誤，請重試');
      eventSource.close();
    }
  };
  
  return eventSource;
};

