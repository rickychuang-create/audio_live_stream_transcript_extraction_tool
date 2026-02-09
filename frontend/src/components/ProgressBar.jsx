/**
 * 進度條組件
 * 顯示任務處理進度
 */
import React from 'react';
import './ProgressBar.css';

const ProgressBar = ({ progress, status, message }) => {
  // 使用 useMemo 確保每次 progress 變化時都重新計算
  const progressValue = React.useMemo(() => Math.max(0, Math.min(100, progress || 0)), [progress]);
  
  /**
   * 根據狀態取得進度條顏色
   */
  const getProgressColor = () => {
    if (status === 'failed') return '#dc3545';
    if (status === 'completed') return '#28a745';
    return '#007bff';
  };

  /**
   * 根據狀態取得狀態文字
   */
  const getStatusText = () => {
    switch (status) {
      case 'pending':
        return '等待中';
      case 'processing':
        return '處理中';
      case 'completed':
        return '完成';
      case 'failed':
        return '失敗';
      default:
        return '未知';
    }
  };

  return (
    <div className="progress-container">
      <div className="progress-header">
        <span className="progress-status">{getStatusText()}</span>
        <span className="progress-percentage">{Math.round(progressValue)}%</span>
      </div>
      <div className="progress-bar">
        <div
          className="progress-fill"
          key={`progress-${progressValue}`} // 使用 key 強制重新渲染
          style={{
            width: `${progressValue}%`,
            backgroundColor: getProgressColor(),
            transition: 'width 0.3s ease-in-out', // 添加平滑過渡動畫
          }}
        >
          {progressValue > 10 && `${Math.round(progressValue)}%`}
        </div>
      </div>
      {message && (
        <p className="progress-message">{message}</p>
      )}
    </div>
  );
};

export default ProgressBar;
