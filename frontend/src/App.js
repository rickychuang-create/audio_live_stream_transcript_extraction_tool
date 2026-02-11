/**
 * 主應用程式組件
 * 整合所有功能：檔案上傳、處理、文案生成
 */
import React, { useState, useEffect } from 'react';
import './App.css';
import FileUpload from './components/FileUpload';
import FormatSelector from './components/FormatSelector';
import ProgressBar from './components/ProgressBar';
import ResultDisplay from './components/ResultDisplay';
import {
  uploadFile,
  processFile,
  getTaskStatus,
  generateContent,
  // 新增：直接以逐字稿文字生成文案的 API
  generateContentFromTranscript,
} from './services/api';

/**
 * 系統支援的文案格式代碼清單
 * 必須同時與前端 FormatSelector 的 value 以及後端 ContentFormat Enum 保持一致
 */

function App() {
  // 狀態管理
  const [currentFileId, setCurrentFileId] = useState(null);
  const [currentTranscript, setCurrentTranscript] = useState(null);
  /**
   * 文案格式選擇狀態（依 Tab 分開管理）
   * - fileSelectedFormats：MP4 → 逐字稿 → 生成文案流程專用
   * - manualSelectedFormats：直接貼上逐字稿生成文案流程專用
   *
   * 註：兩個 Tab 各自獨立，避免在一個 Tab 勾選或變更格式時，影響到另一個 Tab
   */
  const [fileSelectedFormats, setFileSelectedFormats] = useState([]);
  const [manualSelectedFormats, setManualSelectedFormats] = useState([]);
  const [processingTask, setProcessingTask] = useState(null);
  const [generatingTask, setGeneratingTask] = useState(null);
  /**
   * 生成結果狀態（依 Tab 分開管理）
   * - fileResults：MP4 流程生成的文案結果
   * - manualResults：手動貼上逐字稿流程生成的文案結果
   *
   * 註：切換 Tab 時，不互相覆蓋，讓使用者可以回到各自 Tab 查看當時生成的內容
   */
  const [fileResults, setFileResults] = useState(null);
  const [manualResults, setManualResults] = useState(null);
  const [error, setError] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(null); // 上傳進度
  const [uploadCompleted, setUploadCompleted] = useState(false); // 上傳完成標記
  const [processingCompleted, setProcessingCompleted] = useState(false); // 處理完成標記
  const [processingProgress, setProcessingProgress] = useState(null); // 處理進度（用於保留顯示）
  /**
   * 輸入模式
   * - file：使用 MP4 檔案 → 轉逐字稿 → 生成文案（既有流程）
   * - transcript：之後會新增「直接貼上逐字稿」的流程
   * 
   * 註：先在這裡建立模式切換，讓未來可以平滑加入第二條流程
   */
  const [inputMode, setInputMode] = useState('file');
  /**
   * 手動貼上模式下的逐字稿內容
   * - 僅在 inputMode === 'transcript' 時使用
   * - 不與 currentTranscript 共用，避免兩種來源混淆
   */
  const [manualTranscript, setManualTranscript] = useState('');

  /**
   * 處理檔案上傳
   * @param {File} file - 上傳的檔案
   */
  const handleUpload = async (file) => {
    try {
      setError(null);
      setUploadProgress(0); // 開始上傳，顯示進度條
      setUploadCompleted(false);
      
      const response = await uploadFile(file, (progress) => {
        setUploadProgress(progress);
      });
      
      setCurrentFileId(response.file_id);
      setUploadProgress(100); // 上傳完成
      setUploadCompleted(true); // 標記上傳完成
      
      // 自動開始處理（不隱藏上傳進度條）
      handleProcess(response.file_id);
    } catch (err) {
      setError(`上傳失敗: ${err.message}`);
      setUploadProgress(null);
      setUploadCompleted(false);
      console.error('上傳錯誤:', err);
    }
  };

  /**
   * 處理檔案（提取音訊並轉換為逐字稿）
   * @param {string} fileId - 檔案 ID
   */
  const handleProcess = async (fileId) => {
    try {
      setError(null);
      setProcessingCompleted(false); // 重置處理完成狀態
      setProcessingProgress(null); // 重置處理進度
      const response = await processFile(fileId, false);
      console.log('處理任務已啟動，task_id:', response.task_id);
      setProcessingTask(response.task_id);
      
      // 開始輪詢任務狀態（不通過 pollTaskStatus，直接由 TaskProgress 組件處理）
      // pollTaskStatus 已經被 TaskProgress 組件內部的輪詢取代
    } catch (err) {
      setError(`處理失敗: ${err.message}`);
      console.error('處理錯誤:', err);
    }
  };

  /**
   * 輪詢任務狀態
   * @param {string} taskId - 任務 ID
   * @param {string} type - 任務類型 ('processing' 或 'generating')
   * @param {('file' | 'manual')} mode - 生成模式來源（僅在 type === 'generating' 時使用，用來決定更新哪一個結果狀態）
   */
  const pollTaskStatus = async (taskId, type, mode = 'file') => {
    const maxAttempts = 300; // 最多輪詢 5 分鐘（每 1 秒一次）
    let attempts = 0;

    const poll = async () => {
      try {
        const status = await getTaskStatus(taskId);
        
        if (type === 'processing') {
          setProcessingTask(taskId);
        } else if (type === 'generating') {
          setGeneratingTask(taskId);
        }

        if (status.status === 'completed') {
          if (type === 'processing') {
            // 處理完成，儲存逐字稿
            setCurrentTranscript(status.result.transcript);
            setProcessingTask(null);
            
            // 如果已選擇格式，自動開始生成
            if (fileSelectedFormats.length > 0) {
              await handleGenerate(status.result.transcript, status.result.transcript_file);
            }
          } else if (type === 'generating') {
            // 生成完成，依來源模式分別儲存結果
            if (mode === 'file') {
              setFileResults(status.result);
            } else if (mode === 'manual') {
              setManualResults(status.result);
            }
            setGeneratingTask(null);
          }
          return;
        }

        if (status.status === 'failed') {
          setError(`任務失敗: ${status.error || status.message}`);
          if (type === 'processing') {
            setProcessingTask(null);
          } else if (type === 'generating') {
            setGeneratingTask(null);
          }
          return;
        }

        // 繼續輪詢
        attempts++;
        if (attempts < maxAttempts) {
          setTimeout(poll, 1000); // 每 1 秒輪詢一次
        } else {
          setError('任務處理超時');
        }
      } catch (err) {
        setError(`查詢狀態失敗: ${err.message}`);
        console.error('狀態查詢錯誤:', err);
      }
    };

    poll();
  };

  /**
   * 生成文案
   * @param {string} transcript - 逐字稿文字
   * @param {string} transcriptId - 逐字稿 ID
   */
  const handleGenerate = async (transcript, transcriptId = null) => {
    // 僅檢查 MP4 流程對應的格式勾選狀態
    if (fileSelectedFormats.length === 0) {
      setError('請至少選擇一種要生成的格式');
      return;
    }

    try {
      setError(null);
      const transcriptIdToUse = transcriptId || currentFileId;
      // 使用 MP4 流程專用的格式清單
      const response = await generateContent(transcriptIdToUse, fileSelectedFormats);
      setGeneratingTask(response.task_id);
      
      // 開始輪詢任務狀態
      pollTaskStatus(response.task_id, 'generating', 'file');
    } catch (err) {
      setError(`生成失敗: ${err.message}`);
      console.error('生成錯誤:', err);
    }
  };

  /**
   * 直接使用手動貼上的逐字稿生成文案
   *
   * 說明：
   * - 不需要 transcript_id，也不經過 MP4 上傳 / 轉錄流程
   * - 直接呼叫後端 /generate-from-transcript API
   */
  const handleGenerateFromManual = async () => {
    // 基本驗證：逐字稿是否有內容
    if (!manualTranscript || manualTranscript.trim().length === 0) {
      setError('請先貼上逐字稿文字，再進行生成');
      return;
    }

    // 驗證：是否有選擇至少一種格式（僅檢查手動逐字稿 Tab 的格式狀態）
    if (manualSelectedFormats.length === 0) {
      setError('請至少選擇一種要生成的格式');
      return;
    }

    try {
      setError(null);

      // 呼叫後端新 API，這裡假設後端回傳結構與 /generate 類似（含 task_id）
      // 呼叫後端新 API，這裡假設後端回傳結構與 /generate 類似（含 task_id）
      // 使用「直接貼上逐字稿」Tab 專用的格式清單
      const response = await generateContentFromTranscript(manualTranscript, manualSelectedFormats);

      // 若後端也走任務輪詢機制，沿用現有的 pollTaskStatus 流程
      if (response.task_id) {
        setGeneratingTask(response.task_id);
        pollTaskStatus(response.task_id, 'generating', 'manual');
      } else if (response.result) {
        // 如果後端選擇同步回傳結果，直接更新「手動逐字稿」結果狀態
        setManualResults(response.result);
      }
    } catch (err) {
      setError(`生成失敗: ${err.message}`);
      console.error('手動逐字稿生成錯誤:', err);
    }
  };

  /**
   * 取得當前任務狀態
   */
  const getCurrentTaskStatus = () => {
    if (generatingTask) {
      return { taskId: generatingTask, type: 'generating' };
    }
    if (processingTask) {
      return { taskId: processingTask, type: 'processing' };
    }
    return null;
  };

  const currentTask = getCurrentTaskStatus();

  return (
    <div className="App">
      <div className="container">
        <header className="app-header">
          <h1>🎙️ 語音直播切片工具</h1>
          <p>將 MP4/MP3 轉換為逐字稿，並生成多種格式的文案</p>
        </header>

        {/* 輸入模式切換：用 MP4 或 直接貼上逐字稿
            說明：目前只實作 MP4 模式，逐字稿模式會在之後的任務中補上 */}
        <div style={{ marginBottom: '20px', display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          <button
            type="button"
            className={`btn ${inputMode === 'file' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setInputMode('file')}
          >
            上傳檔案轉逐字稿生成
          </button>
          <button
            type="button"
            className={`btn ${inputMode === 'transcript' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setInputMode('transcript')}
          >
            直接貼上逐字稿生成
          </button>
        </div>

        {/* 錯誤訊息顯示 */}
        {error && (
          <div className="error-alert">
            <span>⚠️ {error}</span>
            <button onClick={() => setError(null)}>✕</button>
          </div>
        )}

        {/* === MP4 檔案模式：沿用原本流程 === */}
        {inputMode === 'file' && (
          <>
            {/* 檔案上傳區域 */}
            <div className="card">
              <h2>步驟 1: 上傳 MP4/MP3 檔案</h2>
              <FileUpload
                onUpload={handleUpload}
                disabled={!!currentTask}
              />
              {/* 上傳進度條 - 上傳完成後保留顯示 */}
              {uploadProgress !== null && (
                <div style={{ marginTop: '20px' }}>
                  <h3>上傳進度</h3>
                  <ProgressBar
                    progress={uploadProgress}
                    status={uploadCompleted ? 'completed' : 'processing'}
                    message={uploadCompleted ? '✅ 上傳完成，正在處理逐字稿...' : `上傳中... ${uploadProgress}%`}
                  />
                </div>
              )}
            </div>

            {/* 處理進度顯示 - 有處理任務或處理完成時顯示（移到逐字稿上方） */}
            {(currentTask && currentTask.type === 'processing') || processingCompleted ? (
              <div className="card">
                <h2>🔄 處理進度（轉錄逐字稿）</h2>
                {currentTask && currentTask.type === 'processing' ? (
                  <TaskProgress 
                    taskId={currentTask.taskId} 
                    type={currentTask.type}
                    onProgressUpdate={(progress, status, message) => {
                      // 實時更新處理進度（用於保留顯示）
                      setProcessingProgress(progress);
                    }}
                    onComplete={(taskStatus) => {
                      console.log('TaskProgress onComplete 被調用:', taskStatus);
                      // 處理完成，儲存逐字稿
                      if (taskStatus.result && taskStatus.result.transcript) {
                        setCurrentTranscript(taskStatus.result.transcript);
                      }
                      // 保留處理進度顯示
                      setProcessingCompleted(true);
                      setProcessingProgress(100);
                      // 延遲清除 processingTask，讓進度條保留顯示
                      setTimeout(() => {
                        setProcessingTask(null);
                      }, 3000); // 3秒後清除，讓用戶看到完成狀態
                      
                      // 如果已選擇格式，自動開始生成（僅檢查 MP4 Tab 的格式狀態）
                      if (fileSelectedFormats.length > 0 && taskStatus.result) {
                        handleGenerate(taskStatus.result.transcript, taskStatus.result.transcript_file);
                      }
                    }}
                    onFailed={(taskStatus) => {
                      setError(`任務失敗: ${taskStatus.error || taskStatus.message}`);
                      setProcessingTask(null);
                      setProcessingCompleted(false);
                    }}
                  />
                ) : processingCompleted ? (
                  <ProgressBar
                    progress={processingProgress || 100}
                    status="completed"
                    message="✅ 逐字稿處理完成"
                  />
                ) : null}
              </div>
            ) : null}

            {/* 逐字稿顯示區域 */}
            {currentTranscript && (
              <div className="card">
                <h2>📝 逐字稿</h2>
                <div style={{ 
                  background: '#f8f9fa', 
                  padding: '15px', 
                  borderRadius: '5px',
                  maxHeight: '400px',
                  overflowY: 'auto',
                  marginBottom: '20px',
                  border: '1px solid #e0e0e0'
                }}>
                  <pre style={{ 
                    whiteSpace: 'pre-wrap', 
                    wordWrap: 'break-word',
                    margin: 0,
                    fontFamily: 'inherit',
                    fontSize: '14px',
                    lineHeight: '1.6',
                    color: '#333'
                  }}>
                    {currentTranscript}
                  </pre>
                </div>
                <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                  <button
                    className="btn btn-secondary"
                    onClick={async () => {
                      try {
                        await navigator.clipboard.writeText(currentTranscript);
                        alert('✅ 已複製到剪貼簿！');
                      } catch (err) {
                        console.error('複製失敗:', err);
                        alert('複製失敗，請手動複製');
                      }
                    }}
                  >
                    📋 複製逐字稿
                  </button>
                  <button
                    className="btn btn-secondary"
                    onClick={() => {
                      const blob = new Blob([currentTranscript], { type: 'text/plain;charset=utf-8' });
                      const url = URL.createObjectURL(blob);
                      const link = document.createElement('a');
                      link.href = url;
                      link.download = 'transcript.txt';
                      document.body.appendChild(link);
                      link.click();
                      document.body.removeChild(link);
                      URL.revokeObjectURL(url);
                    }}
                  >
                    💾 下載逐字稿
                  </button>
                </div>
              </div>
            )}

            {/* 格式選擇區域 */}
            {currentTranscript && (
              <div className="card">
                <h2>步驟 2: 選擇要生成的格式</h2>
                <FormatSelector
                  // MP4 模式專用的格式選擇狀態
                  selectedFormats={fileSelectedFormats}
                  onFormatChange={setFileSelectedFormats}
                  disabled={!!currentTask}
                />
                <div style={{ marginTop: '20px', display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                  <button
                    className="btn btn-primary"
                    onClick={() => handleGenerate(currentTranscript)}
                    disabled={!!currentTask || fileSelectedFormats.length === 0}
                  >
                    生成文案
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => {
                      /**
                       * 清除 MP4 Tab 的格式勾選與生成結果
                       * - 僅影響 fileSelectedFormats 與 fileResults
                       * - 不清除逐字稿內容與上傳狀態，方便使用者重新選擇格式再生成
                       */
                      setFileSelectedFormats([]);
                      setFileResults(null);
                    }}
                    disabled={!!currentTask && currentTask.type === 'generating'}
                  >
                    清除本 Tab 結果與勾選
                  </button>
                </div>
              </div>
            )}
            
          </>
        )}

        {/* === 逐字稿貼上模式：使用者直接貼上文字後生成文案 === */}
        {inputMode === 'transcript' && (
          <div className="card">
            <h2>直接貼上逐字稿生成文案</h2>
            <p style={{ marginBottom: '10px', color: '#555', fontSize: '14px' }}>
              已經有逐字稿了嗎？直接把文字貼到下面的框框，選擇要生成的格式，就可以跳過上傳 MP4/MP3 的步驟。
            </p>
            {/* 手動貼上逐字稿輸入框 */}
            <textarea
              value={manualTranscript}
              onChange={(e) => setManualTranscript(e.target.value)}
              placeholder="請將完整逐字稿貼在這裡..."
              style={{
                width: '100%',
                minHeight: '220px',
                padding: '12px',
                borderRadius: '6px',
                border: '1px solid #ccc',
                fontSize: '14px',
                lineHeight: 1.6,
                fontFamily: 'inherit',
                resize: 'vertical',
                boxSizing: 'border-box',
                marginBottom: '16px',
              }}
            />

            {/* 格式選擇共用元件 */}
            <h3 style={{ marginTop: 0 }}>選擇要生成的文案格式：</h3>
            <FormatSelector
              // 手動逐字稿模式專用的格式選擇狀態
              selectedFormats={manualSelectedFormats}
              onFormatChange={setManualSelectedFormats}
              disabled={!!currentTask}
            />

            {/* 生成按鈕：使用手動貼上的逐字稿呼叫新 API 生成文案 */}
            <div style={{ marginTop: '20px', display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
              <button
                className="btn btn-primary"
                onClick={handleGenerateFromManual}
                disabled={!!currentTask || manualSelectedFormats.length === 0}
              >
                生成文案
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => {
                  /**
                   * 清除「直接貼上逐字稿」Tab 的格式勾選與生成結果
                   * - 僅影響 manualSelectedFormats 與 manualResults
                   * - 不清除使用者貼上的逐字稿文字，避免誤刪輸入內容
                   */
                  setManualSelectedFormats([]);
                  setManualResults(null);
                }}
                disabled={!!currentTask && currentTask.type === 'generating'}
              >
                清除本 Tab 結果與勾選
              </button>
            </div>
          </div>
        )}

        {/* 文案生成中提示
            說明：
            - 依照需求，取消顯示 AI 生成進度條，因為無法精準預測生成速度
            - 當有 generatingTask 時，在當前 Tab 顯示簡單的「文案生成中，請稍後...」提示
            - 生成完成後，由 pollTaskStatus 將結果寫入對應的 results state，並清除 generatingTask，提示自然消失 */}
        {generatingTask && inputMode === 'file' && (
          <div className="card">
            <h2>✍️ 文案生成中，請稍後...</h2>
          </div>
        )}
        {generatingTask && inputMode === 'transcript' && (
          <div className="card">
            <h2>✍️ 文案生成中，請稍後...</h2>
          </div>
        )}

        {/* 結果顯示
            說明：
            - MP4 模式與手動逐字稿模式各自有獨立的結果狀態
            - 依目前 inputMode 決定要顯示哪一種結果，避免兩個 Tab 互相覆蓋 */}
        {inputMode === 'file' && fileResults && (
          <div className="card">
            <ResultDisplay
              results={fileResults}
              /**
               * 說明：
               * - MP4 模式下，逐字稿已經在上方獨立卡片中顯示，且有額外的複製 / 下載按鈕
               * - 為避免在「生成結果」區塊重複出現逐字稿複製 / 下載 UI
               * - 這裡不再傳入 transcript，只顯示各種文案生成結果
               */
            />
          </div>
        )}
        {inputMode === 'transcript' && manualResults && (
          <div className="card">
            <ResultDisplay
              results={manualResults}
              /**
               * 說明：
               * - 在「直接貼上逐字稿生成」Tab 中，使用者本來就擁有逐字稿文字
               * - 因此這裡不再傳入 transcript，避免在結果區塊再出現「逐字稿複製/下載」的 UI
               * - 僅顯示生成好的文案結果即可
               */
            />
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * 任務進度組件（內部組件）
 */
function TaskProgress({ taskId, type, onComplete, onFailed, onProgressUpdate }) {
  const [status, setStatus] = useState({
    progress: 0,
    status: 'pending',
    message: '',
    // 新增：保存後端回傳的總秒數與已處理秒數，方便未來在前端顯示更詳細資訊
    totalDuration: null,
    processedDuration: null,
  });
  
  // 使用 useRef 保存回調函數，避免依賴項變化導致重新執行
  const onCompleteRef = React.useRef(onComplete);
  const onFailedRef = React.useRef(onFailed);
  const onProgressUpdateRef = React.useRef(onProgressUpdate);
  
  // 更新 ref 當回調函數變化時
  React.useEffect(() => {
    onCompleteRef.current = onComplete;
    onFailedRef.current = onFailed;
    onProgressUpdateRef.current = onProgressUpdate;
  }, [onComplete, onFailed, onProgressUpdate]);

  useEffect(() => {
    if (!taskId) return;

    let isMounted = true;
    let pollInterval = null;

    const poll = async () => {
      try {
        console.log('輪詢任務狀態，task_id:', taskId);
        const taskStatus = await getTaskStatus(taskId);
        console.log('任務狀態:', taskStatus);
        
        if (!isMounted) return;

        // 更新狀態（確保進度條會更新）
        // 說明：這裡除了 progress/status/message，也把後端的 total_duration / processed_duration 帶進來
        const newStatus = {
          progress: taskStatus.progress || 0,
          status: taskStatus.status,
          message: taskStatus.message || '',
          totalDuration: taskStatus.total_duration ?? null,
          processedDuration: taskStatus.processed_duration ?? null,
        };
        
        console.log('更新進度狀態:', newStatus);
        // 強制更新狀態（每次都更新，確保 React 會重新渲染）
        setStatus(newStatus);
        
        // 通知父組件進度更新
        // 說明：保留原有參數，避免破壞既有呼叫點；如果之後需要，也可以改成傳整個 newStatus
        if (onProgressUpdateRef.current) {
          onProgressUpdateRef.current(
            newStatus.progress,
            newStatus.status,
            newStatus.message
          );
        }

        // 如果任務還在進行中，繼續輪詢
        if (taskStatus.status === 'processing' || taskStatus.status === 'pending') {
          pollInterval = setTimeout(poll, 200); // 每 0.2 秒輪詢一次，更頻繁地更新
        } else {
          // 任務完成或失敗，停止輪詢
          if (taskStatus.status === 'completed') {
            console.log('任務完成:', taskStatus);
            // 確保顯示最終狀態（100%）
            setStatus({
              progress: 100,
              status: 'completed',
              message: taskStatus.message || '處理完成',
            });
            // 通知父組件任務完成（使用 ref 避免依賴問題）
            if (onCompleteRef.current) {
              // 使用 setTimeout 確保狀態更新後再調用回調
              setTimeout(() => {
                onCompleteRef.current(taskStatus);
              }, 200);
            }
          } else if (taskStatus.status === 'failed') {
            console.error('任務失敗:', taskStatus.error || taskStatus.message);
            // 通知父組件任務失敗（使用 ref 避免依賴問題）
            if (onFailedRef.current) {
              setTimeout(() => {
                onFailedRef.current(taskStatus);
              }, 200);
            }
          }
        }
      } catch (err) {
        console.error('查詢進度錯誤:', err);
        console.error('錯誤詳情:', {
          taskId,
          error: err.message,
          response: err.response?.data,
          status: err.response?.status
        });
        if (isMounted) {
          setStatus(prev => ({
            ...prev,
            message: `查詢狀態失敗: ${err.message} (${err.response?.status || '未知錯誤'})`,
          }));
          // 如果是404錯誤，可能是任務還沒初始化，繼續嘗試
          // 如果是其他錯誤，也繼續嘗試（可能是暫時的網路問題）
          if (err.response?.status === 404) {
            console.log('任務未找到，繼續等待...');
            pollInterval = setTimeout(poll, 1000); // 404時更頻繁地查詢
          } else {
            pollInterval = setTimeout(poll, 2000);
          }
        }
      }
    };

    // 立即開始第一次輪詢
    poll();

    // 清理函數
    return () => {
      isMounted = false;
      if (pollInterval) {
        clearTimeout(pollInterval);
      }
    };
  }, [taskId]); // 只依賴 taskId，避免回調函數變化導致重新執行

  return (
    <ProgressBar
      progress={status.progress}
      status={status.status}
      message={status.message}
    />
  );
}

export default App;
