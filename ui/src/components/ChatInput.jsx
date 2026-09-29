import React, { useState, useRef, useEffect } from 'react';
import { ArrowUp, Square } from 'lucide-react';

export default function ChatInput({
  onSendMessage,
  isGenerating,
  onStop,
  disabled,
}) {
  const [input, setInput] = useState('');
  const textareaRef = useRef(null);

  const handleSubmit = (e) => {
    e?.preventDefault();
    if (!input.trim() || isGenerating || disabled) return;
    onSendMessage(input.trim());
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleChange = (e) => {
    setInput(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`;
    }
  };

  useEffect(() => {
    if (!isGenerating && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [isGenerating]);

  return (
    <div className="chat-input-area">
      <form onSubmit={handleSubmit} className="chat-input-wrapper">
        <textarea
          ref={textareaRef}
          className="chat-textarea"
          rows={1}
          placeholder="Message..."
          value={input}
          disabled={disabled}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
        />
        {isGenerating ? (
          <button
            type="button"
            className="action-btn stop"
            onClick={onStop}
            title="Stop"
          >
            <Square size={13} fill="currentColor" />
          </button>
        ) : (
          <button
            type="submit"
            className="action-btn"
            disabled={!input.trim() || disabled}
            title="Send"
          >
            <ArrowUp size={16} />
          </button>
        )}
      </form>
    </div>
  );
}
