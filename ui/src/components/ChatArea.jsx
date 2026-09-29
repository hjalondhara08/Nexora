import React, { useEffect, useRef } from 'react';
import { Copy, Check, Loader2 } from 'lucide-react';

function MessageContent({ content }) {
  const [copied, setCopied] = React.useState(false);

  const handleCopy = (text) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const parts = content.split(/(```[\s\S]*?```)/g);

  return (
    <div>
      {parts.map((part, index) => {
        if (part.startsWith('```') && part.endsWith('```')) {
          const lines = part.slice(3, -3).trim().split('\n');
          const firstLine = lines[0].trim();
          const language = firstLine && !firstLine.includes(' ') ? firstLine : '';
          const codeContent = language ? lines.slice(1).join('\n') : lines.join('\n');

          return (
            <div key={index} className="code-block-wrapper">
              <div className="code-block-header">
                <span>{language || 'code'}</span>
                <button
                  className="code-copy-btn"
                  onClick={() => handleCopy(codeContent)}
                  title="Copy code"
                >
                  {copied ? <Check size={12} color="#4ade80" /> : <Copy size={12} />}
                  <span>{copied ? 'Copied' : 'Copy'}</span>
                </button>
              </div>
              <pre>
                <code>{codeContent}</code>
              </pre>
            </div>
          );
        }

        return (
          <div key={index} style={{ whiteSpace: 'pre-wrap' }}>
            {part}
          </div>
        );
      })}
    </div>
  );
}

export default function ChatArea({
  messages,
  isGenerating,
  toolStatus,
}) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isGenerating, toolStatus]);

  return (
    <div className="messages-container">
      <div className="messages-inner">
        {messages.length === 0 ? (
          <div className="empty-state">
            <h1 className="empty-state-title">Nexora</h1>
            <p className="empty-state-subtitle">
              How can I help you today?
            </p>
          </div>
        ) : (
          messages.map((msg, index) => {
            const isUser = msg.role === 'user';
            // If assistant message is currently empty while generating, don't show empty bubble
            if (!isUser && !msg.content && isGenerating) return null;

            return (
              <div
                key={index}
                className={`message-row ${isUser ? 'user' : 'assistant'}`}
              >
                <div className="message-bubble">
                  <MessageContent content={msg.content} />
                </div>
              </div>
            );
          })
        )}

        {/* Live Generation / Tool Indicator */}
        {(isGenerating || toolStatus) && (
          <div className="message-row assistant">
            <div className="tool-status-bar">
              <Loader2 size={13} className="spinner-icon" />
              <span>{toolStatus?.tool ? `Using ${toolStatus.tool}...` : 'Thinking...'}</span>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  );
}
