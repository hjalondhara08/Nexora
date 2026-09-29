import React, { useRef, useState } from 'react';
import {
  Plus,
  Upload,
  FileText,
  MessageSquare,
  Trash2,
  Key,
  Loader2,
} from 'lucide-react';
import { uploadDocument } from '../api';

export default function Sidebar({
  threads,
  activeThreadId,
  onSelectThread,
  onNewChat,
  onDeleteThread,
  onClearAll,
  activeDoc,
  setActiveDoc,
  onOpenApiKeyModal,
}) {
  const fileInputRef = useRef(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setUploadError('');

    try {
      const res = await uploadDocument(file);
      if (res.filename) {
        setActiveDoc(res.path || file.name);
      }
    } catch (err) {
      setUploadError(err.message || 'Upload failed');
      setTimeout(() => setUploadError(''), 4000);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const getDocDisplayName = (path) => {
    if (!path) return 'Atomic_Habit.pdf';
    const parts = path.split('/');
    return parts[parts.length - 1];
  };

  return (
    <aside className="sidebar">
      {/* Sidebar Header */}
      <div className="sidebar-header">
        <span className="sidebar-title">Nexora</span>
      </div>

      {/* New Chat Action */}
      <button className="new-chat-btn" onClick={onNewChat}>
        <Plus size={16} />
        <span>New Chat</span>
      </button>

      {/* 1. Upload Document Section */}
      <div className="sidebar-section">
        <div className="sidebar-section-header">
          <span className="sidebar-section-title">Document</span>
        </div>

        <input
          type="file"
          accept=".pdf"
          ref={fileInputRef}
          style={{ display: 'none' }}
          onChange={handleFileChange}
        />

        <div
          className={`upload-box ${isUploading ? 'uploading' : ''}`}
          onClick={() => !isUploading && fileInputRef.current?.click()}
        >
          {isUploading ? (
            <>
              <Loader2 size={18} className="spinner-icon upload-box-icon" />
              <span className="upload-box-text">Uploading...</span>
            </>
          ) : (
            <>
              <Upload size={18} className="upload-box-icon" />
              <span className="upload-box-text">Upload PDF</span>
            </>
          )}
        </div>

        {uploadError && (
          <div style={{ fontSize: '0.72rem', color: 'var(--danger)', marginTop: 6 }}>
            {uploadError}
          </div>
        )}

        {/* Current Active Document */}
        <div className="active-doc-item">
          <FileText size={15} className="active-doc-icon" />
          <div className="active-doc-info">
            <span className="active-doc-label">Active</span>
            <span className="active-doc-name" title={activeDoc}>
              {getDocDisplayName(activeDoc)}
            </span>
          </div>
        </div>
      </div>

      {/* 2. Chat Panel History Below Document */}
      <div className="sidebar-section" style={{ borderBottom: 'none', paddingBottom: 6 }}>
        <div className="sidebar-section-header">
          <span className="sidebar-section-title">Chat History</span>
          {threads.length > 0 && (
            <button
              className="sidebar-section-action"
              onClick={onClearAll}
              title="Clear history"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      <div className="sidebar-history-container">
        {threads.length === 0 ? (
          <div className="sidebar-history-empty">No conversations</div>
        ) : (
          threads.map((thread) => {
            const isActive = thread.thread_id === activeThreadId;
            return (
              <div
                key={thread.thread_id}
                className={`history-item ${isActive ? 'active' : ''}`}
                onClick={() => onSelectThread(thread.thread_id)}
              >
                <div className="history-item-left">
                  <MessageSquare size={14} className="history-item-icon" />
                  <span className="history-item-title">
                    {thread.label || 'New Conversation'}
                  </span>
                </div>
                <button
                  className="history-delete-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteThread(thread.thread_id);
                  }}
                  title="Delete"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            );
          })
        )}
      </div>

      {/* Minimal Footer */}
      <div className="sidebar-footer">
        <button className="footer-btn" onClick={onOpenApiKeyModal}>
          <Key size={13} />
          <span>API Key</span>
        </button>
      </div>
    </aside>
  );
}
