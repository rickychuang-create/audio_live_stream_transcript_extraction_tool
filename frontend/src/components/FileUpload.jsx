/**
 * 檔案上傳組件
 * 支援拖放和點擊上傳
 */
import React, { useRef, useState } from 'react';
import './FileUpload.css';

const FileUpload = ({ onUpload, disabled }) => {
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const fileInputRef = useRef(null);

  /**
   * 處理檔案選擇
   * @param {FileList} files - 選中的檔案列表
   */
  const handleFiles = (files) => {
    const fileArray = Array.from(files).filter(file => 
      file.type === 'video/mp4' || 
      file.name.endsWith('.mp4') ||
      file.type === 'audio/mpeg' ||
      file.name.endsWith('.mp3')
    );
    
    if (fileArray.length === 0) {
      alert('請選擇 MP4 或 MP3 格式的檔案');
      return;
    }
    
    setSelectedFiles(fileArray);
  };

  /**
   * 處理拖放事件
   */
  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    
    const files = e.dataTransfer.files;
    handleFiles(files);
  };

  /**
   * 處理檔案輸入變化
   */
  const handleFileInputChange = (e) => {
    const files = e.target.files;
    handleFiles(files);
  };

  /**
   * 處理上傳按鈕點擊
   */
  const handleUploadClick = () => {
    if (selectedFiles.length === 0) {
      fileInputRef.current?.click();
      return;
    }
    
    // 只處理單個檔案上傳
    if (selectedFiles.length === 1 && onUpload) {
      onUpload(selectedFiles[0]);
      setSelectedFiles([]);
    } else if (selectedFiles.length > 1) {
      alert('請一次只上傳一個檔案');
      setSelectedFiles([]);
    }
  };

  /**
   * 移除選中的檔案
   */
  const removeFile = (index) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index));
  };

  return (
    <div className="file-upload-container">
      <div
        className={`file-upload-area ${isDragging ? 'dragging' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !disabled && fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".mp4,.mp3,video/mp4,audio/mpeg"
          onChange={handleFileInputChange}
          style={{ display: 'none' }}
          disabled={disabled}
        />
        
        <div className="upload-content">
          <div className="upload-icon">📁</div>
          <p className="upload-text">
            {isDragging ? '放開以上傳檔案' : '拖放 MP4 或 MP3 檔案到這裡，或點擊選擇檔案'}
          </p>
          <p className="upload-hint">一次上傳一個 MP4 或 MP3 檔案</p>
        </div>
      </div>

      {selectedFiles.length > 0 && (
        <div className="selected-files">
          <h4>已選擇的檔案 ({selectedFiles.length})：</h4>
          <ul>
            {selectedFiles.map((file, index) => (
              <li key={index}>
                <span>{file.name}</span>
                <span className="file-size">
                  ({(file.size / 1024 / 1024).toFixed(2)} MB)
                </span>
                <button
                  className="remove-btn"
                  onClick={() => removeFile(index)}
                  disabled={disabled}
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
          <button
            className="btn btn-primary"
            onClick={handleUploadClick}
            disabled={disabled || selectedFiles.length !== 1}
          >
            上傳並處理
          </button>
        </div>
      )}
    </div>
  );
};

export default FileUpload;
