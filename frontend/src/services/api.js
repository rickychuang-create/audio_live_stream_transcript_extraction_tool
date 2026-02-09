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

