/**
 * 結果展示組件
 * 顯示生成的文案內容，提供預覽和下載功能
 */
import React from 'react';
import './ResultDisplay.css';

const ResultDisplay = ({ results, transcript }) => {

  /**
   * 下載內容
   * @param {string} content - 要下載的內容
   * @param {string} filename - 檔案名稱
   */
  const downloadContent = (content, filename) => {
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  /**
   * 複製內容到剪貼簿
   * @param {string} content - 要複製的內容
   */
  const copyToClipboard = async (content) => {
    try {
      await navigator.clipboard.writeText(content);
      alert('已複製到剪貼簿！');
    } catch (err) {
      console.error('複製失敗:', err);
      alert('複製失敗，請手動複製');
    }
  };

  if (!results || Object.keys(results).length === 0) {
    return null;
  }

  /**
   * 將格式代碼對應到在結果畫面上顯示的標題文字
   * key 必須與前端選擇的 value 以及後端的 ContentFormat Enum 值一致
   */
  const formatLabels = {
    community_post: 'App免費社團貼文', // 原本「社團文章文案」
    email: 'Email 文案',
    yt_post: 'YT 貼文',              // 新的 YT 貼文格式（原本 key 為 yt_shorts）
    summary: '精華摘要',
  };

  return (
    <div className="result-display">
      <h2>生成結果</h2>
      
      {/* 逐字稿顯示 */}
      {transcript && (
        <div className="result-section">
          <h4>逐字稿</h4>
          <div className="result-actions">
            <button
              className="btn btn-secondary"
              onClick={() => copyToClipboard(transcript)}
            >
              複製
            </button>
            <button
              className="btn btn-secondary"
              onClick={() => downloadContent(transcript, 'transcript.txt')}
            >
              下載
            </button>
          </div>
          <div className="result-content">
            <pre>{transcript}</pre>
          </div>
        </div>
      )}

      {/* 生成的文案顯示 */}
      {Object.entries(results).map(([format, data]) => {
        if (data.error) {
          return (
            <div key={format} className="result-section error">
              <h4>{formatLabels[format] || format}</h4>
              <p className="error-message">生成失敗: {data.error}</p>
            </div>
          );
        }

        const content = data.content || '';

        return (
          <div key={format} className="result-section">
            <div className="result-header">
              <h4>{formatLabels[format] || format}</h4>
              <div className="result-actions">
                <button
                  className="btn btn-secondary"
                  onClick={() => copyToClipboard(content)}
                >
                  複製
                </button>
                <button
                  className="btn btn-secondary"
                  onClick={() => downloadContent(content, `${format}.txt`)}
                >
                  下載
                </button>
              </div>
            </div>
            {/*
              說明：
              - 原本內容長度超過 500 字時，預設會收合，並提供「展開 / 收合」按鈕切換
              - 依照需求調整為：所有生成文案預設全展開顯示，且不再顯示展開/收合按鈕
              - 因此這裡僅保留單純的內容容器，不再套用 `collapsed` 樣式
            */}
            <div className="result-content">
              <pre>{content}</pre>
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default ResultDisplay;
