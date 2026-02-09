/**
 * 格式選擇組件
 * 讓用戶選擇要生成的文案格式
 */
import React from 'react';
import './FormatSelector.css';

/**
 * 前端可選擇的文案格式定義
 * - value：送到後端 API 的格式代碼，必須與後端 ContentFormat Enum 對應
 * - label：按鈕上顯示的文字
 * - icon：按鈕上的圖示，純前端顯示使用，可依需求調整
 */
const FORMATS = [
  {
    value: 'community_post',      // 對應後端的 community_post（社團文章類型）
    label: 'App免費社團貼文',      // 顯示文字：原本為「社團文章文案」
    icon: '📱',                   // 使用手機 icon 呼應 App 社團貼文
  },
  {
    value: 'email',               // Email 文案格式
    label: 'Email 文案',
    icon: '✉️',
  },
  {
    value: 'yt_post',             // ★ 新的 YouTube 貼文格式代碼（原本為 yt_shorts）
    label: 'YT 貼文',             // 顯示文字：原本為「YT Shorts 腳本」
    icon: '🧾',                   // 使用播放按鈕 icon 代表 YouTube 內容
  },
  {
    value: 'summary',             // 精華摘要格式
    label: '精華摘要',
    icon: '📋',
  },
];

const FormatSelector = ({ selectedFormats, onFormatChange, disabled }) => {
  /**
   * 處理格式選擇變化
   * @param {string} format - 格式值
   */
  const handleFormatToggle = (format) => {
    if (disabled) return;
    
    if (selectedFormats.includes(format)) {
      onFormatChange(selectedFormats.filter(f => f !== format));
    } else {
      onFormatChange([...selectedFormats, format]);
    }
  };

  return (
    <div className="format-selector">
      <div className="format-grid">
        {FORMATS.map(format => (
          <div
            key={format.value}
            className={`format-card ${selectedFormats.includes(format.value) ? 'selected' : ''} ${disabled ? 'disabled' : ''}`}
            onClick={() => handleFormatToggle(format.value)}
          >
            <div className="format-icon">{format.icon}</div>
            <div className="format-label">{format.label}</div>
            {selectedFormats.includes(format.value) && (
              <div className="checkmark">✓</div>
            )}
          </div>
        ))}
      </div>
      {selectedFormats.length === 0 && (
        <p className="format-hint">請至少選擇一種格式</p>
      )}
    </div>
  );
};

export default FormatSelector;
