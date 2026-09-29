import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import ChatArea from './components/ChatArea';
import ChatInput from './components/ChatInput';
import ApiKeyModal from './components/ApiKeyModal';
import {
  fetchThreads,
  fetchThreadMessages,
  createThread,
  deleteThread,
  clearAllThreads,
  fetchActiveDoc,
  streamChat,
} from './api';

export default function App() {
  const [threads, setThreads] = useState([]);
  const [activeThreadId, setActiveThreadId] = useState('');
  const [messages, setMessages] = useState([]);
  const [activeDoc, setActiveDoc] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [toolStatus, setToolStatus] = useState(null);
  const [isApiKeyModalOpen, setIsApiKeyModalOpen] = useState(false);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);

  useEffect(() => {
    async function init() {
      try {
        const docRes = await fetchActiveDoc().catch(() => ({ filename: 'Atomic_Habit.pdf' }));
        if (docRes.path) setActiveDoc(docRes.path);

        const threadList = await fetchThreads().catch(() => []);
        setThreads(threadList);

        if (threadList.length > 0) {
          const firstId = threadList[0].thread_id;
          setActiveThreadId(firstId);
          loadThreadHistory(firstId);
        } else {
          startNewChat(false);
        }
      } catch (err) {
        console.error('Initialization error:', err);
      }
    }
    init();
  }, []);

  const loadThreadHistory = async (threadId) => {
    setIsLoadingMessages(true);
    try {
      const res = await fetchThreadMessages(threadId);
      setMessages(res.messages || []);
    } catch (err) {
      console.error('Failed to load messages:', err);
      setMessages([]);
    } finally {
      setIsLoadingMessages(false);
    }
  };

  const startNewChat = async (persist = true) => {
    try {
      const newThread = await createThread();
      const newId = newThread.thread_id;
      setActiveThreadId(newId);
      setMessages([]);
      if (persist) {
        setThreads((prev) => [newThread, ...prev.filter((t) => t.thread_id !== newId)]);
      }
    } catch (err) {
      const fallbackId = 'thread-' + Date.now();
      setActiveThreadId(fallbackId);
      setMessages([]);
    }
  };

  const handleSelectThread = (threadId) => {
    if (threadId === activeThreadId || isGenerating) return;
    setActiveThreadId(threadId);
    loadThreadHistory(threadId);
  };

  const handleDeleteThread = async (threadId) => {
    try {
      await deleteThread(threadId);
      const updated = threads.filter((t) => t.thread_id !== threadId);
      setThreads(updated);
      if (activeThreadId === threadId) {
        if (updated.length > 0) {
          setActiveThreadId(updated[0].thread_id);
          loadThreadHistory(updated[0].thread_id);
        } else {
          startNewChat(false);
        }
      }
    } catch (err) {
      console.error('Failed to delete thread:', err);
    }
  };

  const handleClearAll = async () => {
    if (!window.confirm('Clear all conversation history?')) return;
    try {
      await clearAllThreads();
      setThreads([]);
      startNewChat(false);
    } catch (err) {
      console.error('Failed to clear conversations:', err);
    }
  };

  const handleSendMessage = async (text) => {
    if (!text.trim() || isGenerating) return;

    let currentThreadId = activeThreadId;
    if (!currentThreadId) {
      const newThread = await createThread();
      currentThreadId = newThread.thread_id;
      setActiveThreadId(currentThreadId);
      setThreads((prev) => [newThread, ...prev]);
    }

    const userMessage = { role: 'user', content: text };
    setMessages((prev) => [...prev, userMessage]);

    setThreads((prev) =>
      prev.map((t) => {
        if (t.thread_id === currentThreadId && (!t.label || t.label.startsWith('thread-') || t.label.length < 5)) {
          return { ...t, label: text.slice(0, 30) + (text.length > 30 ? '...' : '') };
        }
        return t;
      })
    );

    setIsGenerating(true);
    setToolStatus(null);
    setMessages((prev) => [...prev, { role: 'assistant', content: '' }]);

    await streamChat({
      message: text,
      threadId: currentThreadId,
      activeDoc: activeDoc,
      onToolCall: (data) => {
        setToolStatus({
          tool: data.tool,
          message: data.message,
        });
      },
      onDelta: (chunk) => {
        setToolStatus(null);
        setMessages((prev) => {
          const next = [...prev];
          const lastIdx = next.length - 1;
          if (lastIdx >= 0 && next[lastIdx].role === 'assistant') {
            next[lastIdx] = {
              ...next[lastIdx],
              content: next[lastIdx].content + chunk,
            };
          }
          return next;
        });
      },
      onDone: () => {
        setIsGenerating(false);
        setToolStatus(null);
        fetchThreads()
          .then((updated) => setThreads(updated))
          .catch(() => {});
      },
      onError: (err) => {
        setIsGenerating(false);
        setToolStatus(null);
        setMessages((prev) => {
          const next = [...prev];
          const lastIdx = next.length - 1;
          if (lastIdx >= 0 && next[lastIdx].role === 'assistant') {
            next[lastIdx] = {
              ...next[lastIdx],
              content:
                next[lastIdx].content +
                `\n\nError: ${err.message || 'Request failed.'}`,
            };
          }
          return next;
        });
      },
    });
  };

  const handleStop = () => {
    setIsGenerating(false);
    setToolStatus(null);
  };

  const activeThread = threads.find((t) => t.thread_id === activeThreadId);
  const activeDocName = activeDoc ? activeDoc.split('/').pop() : '';

  return (
    <div className="app-container">
      {/* Left Sidebar: Document Upload on top, Chat History below */}
      <Sidebar
        threads={threads}
        activeThreadId={activeThreadId}
        onSelectThread={handleSelectThread}
        onNewChat={() => startNewChat(true)}
        onDeleteThread={handleDeleteThread}
        onClearAll={handleClearAll}
        activeDoc={activeDoc}
        setActiveDoc={setActiveDoc}
        onOpenApiKeyModal={() => setIsApiKeyModalOpen(true)}
      />

      {/* Right Section: Chat */}
      <main className="chat-main">
        <header className="chat-header">
          <span className="chat-header-title">
            {activeThread?.label || 'New Conversation'}
          </span>
          {activeDocName && (
            <span className="chat-header-badge" title={activeDocName}>
              {activeDocName}
            </span>
          )}
        </header>

        <ChatArea
          messages={messages}
          isGenerating={isGenerating}
          toolStatus={toolStatus}
        />

        <ChatInput
          onSendMessage={handleSendMessage}
          isGenerating={isGenerating}
          onStop={handleStop}
          disabled={isLoadingMessages}
        />
      </main>

      <ApiKeyModal
        isOpen={isApiKeyModalOpen}
        onClose={() => setIsApiKeyModalOpen(false)}
      />
    </div>
  );
}
