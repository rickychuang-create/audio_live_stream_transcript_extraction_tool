/**
 * 主應用程式組件
 * 整合所有功能：檔案上傳、處理、文案生成
 */
import React, { useState, useEffect } from 'react';
import { flushSync } from 'react-dom';
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
  // 新增：SSE 串流轉錄
  transcribeStream,
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
   * - fileSelectedFormats：MP3 上傳 → 逐字稿 → 生成文案流程專用
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
   * - fileResults：檔案上傳流程生成的文案結果
   * - manualResults：手動貼上逐字稿流程生成的文案結果
   *
   * 註：切換 Tab 時，不互相覆蓋，讓使用者可以回到各自 Tab 查看當時生成的內容
   */
  const [fileResults, setFileResults] = useState(null);
  const [manualResults, setManualResults] = useState(null);
  const [error, setError] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(null); // 上傳進度
  const [streamingTranscript, setStreamingTranscript] = useState(''); // 即時串流逐字稿
  const [eventSource, setEventSource] = useState(null); // SSE 連線
  
  // 清理 SSE 連線（組件卸載時）
  useEffect(() => {
    return () => {
      if (eventSource) {
        eventSource.close();
        setEventSource(null);
      }
    };
  }, [eventSource]);
  const [uploadCompleted, setUploadCompleted] = useState(false); // 上傳完成標記
  const [processingCompleted, setProcessingCompleted] = useState(false); // 處理完成標記
  const [, setProcessingProgress] = useState(null); // 處理進度（目前僅需 setter，避免 ESLint 未使用警告）
  /**
   * 輸入模式
   * - file：使用 MP3 檔案 → 轉逐字稿 → 生成文案（既有流程）
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
      setUploadProgress(90); // 檔案上傳到後端完成，設為 90%（剩餘 10% 留給 Gemini 上傳）
      setUploadCompleted(false); // 尚未完成（等待 Gemini 上傳完成）
      
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
   * 處理檔案（使用 SSE 即時串流轉錄結果）
   * @param {string} fileId - 檔案 ID
   */
  const handleProcess = async (fileId) => {
    try {
      setError(null);
      setProcessingCompleted(false); // 重置處理完成狀態
      setProcessingProgress(null); // 重置處理進度
      setStreamingTranscript(''); // 重置串流逐字稿
      setCurrentTranscript(null); // 重置完整逐字稿，確保顯示邏輯正確
      
      // 關閉之前的 SSE 連線（如果存在）
      if (eventSource) {
        eventSource.close();
        setEventSource(null);
      }
      
      // 啟動處理任務（上傳到 Gemini）
      const response = await processFile(fileId, false);
      const taskId = response.task_id; // 使用局部變數存儲 task_id
      console.log('處理任務已啟動，task_id:', taskId);
      
      // 等待上傳完成（輪詢任務狀態直到 Gemini 收到檔案）
      const waitForUpload = async () => {
        const maxWait = 60; // 最多等待 60 秒
        let waitCount = 0;
        let isGeminiReady = false;
        
        while (!isGeminiReady && waitCount < maxWait) {
          try {
            const status = await getTaskStatus(taskId);
            
            // 更新上傳進度條的最後一哩路（例如 90% → 95% → 100%）
            if (status.progress !== undefined && status.progress !== null) {
              // 將後端進度映射到前端進度（後端 0-100% 對應前端 90-100%）
              const mappedProgress = Math.min(90 + (status.progress * 0.1), 100);
              setUploadProgress(mappedProgress);
            }
            
            // 當後端狀態變成 completed，代表 Gemini 已經收到檔案了（上傳階段完成）
            if (status.status === 'completed') {
              setUploadProgress(100);
              setUploadCompleted(true);
              isGeminiReady = true;
              console.log('上傳完成，開始建立 SSE 連線');
              return;
            }
            if (status.status === 'failed') {
              throw new Error(status.error || status.message || 'Gemini 接收失敗');
            }
          } catch (err) {
            console.error('查詢上傳狀態錯誤:', err);
          }
          
          await new Promise(resolve => setTimeout(resolve, 1000)); // 等待 1 秒
          waitCount++;
        }
        
        if (!isGeminiReady) {
          throw new Error('上傳超時');
        }
      };
      
      await waitForUpload();
      
      // === 關鍵修正處 ===
      // 直到上傳完全完成，才設定這個狀態，讓下方的「逐字稿卡片」顯現
      setProcessingTask(taskId);
      
      // 使用 SSE 即時接收轉錄結果
      // 使用局部變數保存 EventSource 實例，確保回調函數中能正確關閉連線
      console.log('[App] 準備建立 SSE 連線，taskId:', taskId);
      const es = transcribeStream(taskId, {
        onProgress: (message) => {
          console.log('[App] 轉錄進度:', message);
          // 可以更新進度訊息，但主要依賴 TaskProgress 組件
        },
        onChunk: (text) => {
          // 即時更新逐字稿
          // 轉錄進行中時，只更新 streamingTranscript，確保即時顯示
          // 不要同時更新 currentTranscript，避免顯示邏輯衝突
          console.log('[App] ✅ onChunk 回調被調用！收到 chunk，長度:', text?.length || 0, '預覽:', text?.substring(0, 50) || '');
          
          // 使用 flushSync 強制同步更新，確保每個 chunk 都能立即在 UI 上顯示
          // 這可以避免 React 18 的自動批量更新將多個狀態更新合併到一次渲染中
          flushSync(() => {
            setStreamingTranscript(prev => {
              const newValue = (prev || '') + (text || '');
              console.log('[App] 更新 streamingTranscript，從', prev?.length || 0, '字元增加到', newValue.length, '字元');
              // 強制觸發重新渲染（通過返回新字串）
              return newValue;
            });
          });
          
          // flushSync 會立即觸發同步渲染，不需要額外的延遲
        },
        onComplete: (fullText, filePath) => {
          console.log('[App] 轉錄完成:', fullText.length, '字元');
          // 轉錄完成後，先將完整文字設置到 currentTranscript
          setCurrentTranscript(fullText);
          // 然後清空 streamingTranscript，這樣顯示邏輯會切換到 currentTranscript
          setStreamingTranscript('');
          setProcessingCompleted(true);
          setProcessingProgress(100);
          setProcessingTask(null); // 清除任務，但保留逐字稿卡片顯示
          
          // 使用局部變數 es 來關閉連線，而不是依賴 state（因為 state 更新是異步的）
          if (es) {
            es.close();
            setEventSource(null);
          }
          
          // 如果已選擇格式，自動開始生成
          if (fileSelectedFormats.length > 0 && fullText) {
            handleGenerate(fullText, fileId); // 使用 fileId 作為 transcriptId
          }
        },
        onError: (errorMsg) => {
          console.error('轉錄錯誤:', errorMsg);
          setError(`轉錄失敗: ${errorMsg}`);
          setProcessingTask(null);
          setStreamingTranscript('');
          
          // 使用局部變數 es 來關閉連線，而不是依賴 state
          if (es) {
            es.close();
            setEventSource(null);
          }
        }
      });
      
      // 將 EventSource 實例保存到 state，用於組件卸載時清理
      setEventSource(es);
      
    } catch (err) {
      setError(`處理失敗: ${err.message}`);
      console.error('處理錯誤:', err);
      setProcessingTask(null);
      setStreamingTranscript('');
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
    // 僅檢查檔案上傳流程對應的格式勾選狀態
    if (fileSelectedFormats.length === 0) {
      setError('請至少選擇一種要生成的格式');
      return;
    }

    try {
      setError(null);
      const transcriptIdToUse = transcriptId || currentFileId;
      // 使用檔案上傳流程專用的格式清單
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
   * - 不需要 transcript_id，也不經過檔案上傳 / 轉錄流程
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
          <p>將 MP3 轉換為逐字稿，並生成多種格式的文案</p>
        </header>

        {/* 輸入模式切換：上傳 MP3 檔案或直接貼上逐字稿 */}
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

        {/* === MP3 檔案模式：上傳並轉錄 === */}
        {inputMode === 'file' && (
          <>
            {/* 檔案上傳區域 */}
            <div className="card">
              <h2>步驟 1: 上傳 MP3 檔案</h2>
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
                    message={uploadCompleted ? '✅ 上傳完成！' : `上傳中... ${uploadProgress}%`}
                  />
                </div>
              )}
            </div>

            {/* 逐字稿顯示區域 - 支援即時串流顯示 */}
            {/* 只要有處理任務、串流逐字稿或完整逐字稿，就顯示這個區域 */}
            {(processingTask || streamingTranscript || currentTranscript) && (
              <div className="card">
                <h2>
                  📝 逐字稿
                  <StatusTag 
                    isProcessing={!!processingTask && !processingCompleted} 
                    isCompleted={processingCompleted && !!currentTranscript} 
                  />
                </h2>
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
                    {/* 
                      轉錄進行中時優先顯示 streamingTranscript，完成後顯示 currentTranscript
                      使用 key 強制重新渲染，確保內容更新時能立即顯示
                    */}
                    <span key={`transcript-${streamingTranscript.length}-${currentTranscript?.length || 0}`}>
                      {streamingTranscript || currentTranscript || ''}
                    </span>
                  </pre>
                </div>
                <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                  <button
                    className="btn btn-secondary"
                    onClick={async () => {
                      try {
                        // 優先使用 streamingTranscript（轉錄進行中），否則使用 currentTranscript
                        const textToCopy = streamingTranscript || currentTranscript;
                        await navigator.clipboard.writeText(textToCopy);
                        alert('✅ 已複製到剪貼簿！');
                      } catch (err) {
                        console.error('複製失敗:', err);
                        alert('複製失敗，請手動複製');
                      }
                    }}
                    disabled={!currentTranscript && !streamingTranscript}
                  >
                    📋 複製逐字稿
                  </button>
                  <button
                    className="btn btn-secondary"
                    onClick={() => {
                      // 優先使用 streamingTranscript（轉錄進行中），否則使用 currentTranscript
                      const textToDownload = streamingTranscript || currentTranscript;
                      const blob = new Blob([textToDownload], { type: 'text/plain;charset=utf-8' });
                      const url = URL.createObjectURL(blob);
                      const link = document.createElement('a');
                      link.href = url;
                      link.download = 'transcript.txt';
                      document.body.appendChild(link);
                      link.click();
                      document.body.removeChild(link);
                      URL.revokeObjectURL(url);
                    }}
                    disabled={!currentTranscript && !streamingTranscript}
                  >
                    💾 下載逐字稿
                  </button>
                </div>
              </div>
            )}

            {/* 格式選擇區域 */}
            {currentTranscript && !streamingTranscript && (
              <div className="card">
                <h2>步驟 2: 選擇要生成的格式</h2>
                <FormatSelector
                  // 檔案上傳模式專用的格式選擇狀態
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
                       * 清除檔案上傳 Tab 的格式勾選與生成結果
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
              已經有逐字稿了嗎？直接把文字貼到下面的框框，選擇要生成的格式，就可以跳過上傳 MP3 的步驟。
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
            - 檔案上傳模式與手動逐字稿模式各自有獨立的結果狀態
            - 依目前 inputMode 決定要顯示哪一種結果，避免兩個 Tab 互相覆蓋 */}
        {inputMode === 'file' && fileResults && (
          <div className="card">
            <ResultDisplay
              results={fileResults}
              /**
               * 說明：
               * - 檔案上傳模式下，逐字稿已經在上方獨立卡片中顯示，且有額外的複製 / 下載按鈕
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
 * 狀態標籤組件（內部組件）
 */
function StatusTag({ isProcessing, isCompleted }) {
  if (isProcessing) {
    return (
      <span className="badge badge-processing">
        <span className="dot pulse"></span>
        AI助手聽取中...
      </span>
    );
  }
  if (isCompleted) {
    return (
      <span className="badge badge-completed">
        <span className="dot"></span>
        已完成！
      </span>
    );
  }
  return null;
}

/**
 * 任務進度組件（內部組件）
 */
export default App;
