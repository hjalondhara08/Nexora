/**
 * Nexora API Client
 * =================
 * Handles communication with the async FastAPI backend.
 */

const API_BASE = '/api';

export function getApiKey() {
  return localStorage.getItem('nexora_api_key') || 'nexora-secret-key-2026';
}

export function setApiKey(key) {
  if (key) {
    localStorage.setItem('nexora_api_key', key);
  } else {
    localStorage.removeItem('nexora_api_key');
  }
}

function getHeaders(customHeaders = {}) {
  const headers = {
    'X-API-Key': getApiKey(),
    ...customHeaders,
  };
  return headers;
}

export async function fetchThreads() {
  const res = await fetch(`${API_BASE}/threads`, {
    headers: getHeaders(),
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch threads: ${res.statusText}`);
  }
  return await res.json();
}

export async function fetchThreadMessages(threadId) {
  const res = await fetch(`${API_BASE}/threads/${threadId}`, {
    headers: getHeaders(),
  });
  if (!res.ok) {
    throw new Error(`Failed to load conversation: ${res.statusText}`);
  }
  return await res.json();
}

export async function createThread() {
  const res = await fetch(`${API_BASE}/threads`, {
    method: 'POST',
    headers: getHeaders({ 'Content-Type': 'application/json' }),
  });
  if (!res.ok) {
    throw new Error(`Failed to create thread: ${res.statusText}`);
  }
  return await res.json();
}

export async function deleteThread(threadId) {
  const res = await fetch(`${API_BASE}/threads/${threadId}`, {
    method: 'DELETE',
    headers: getHeaders(),
  });
  if (!res.ok) {
    throw new Error(`Failed to delete thread: ${res.statusText}`);
  }
  return await res.json();
}

export async function clearAllThreads() {
  const res = await fetch(`${API_BASE}/threads`, {
    method: 'DELETE',
    headers: getHeaders(),
  });
  if (!res.ok) {
    throw new Error(`Failed to clear conversations: ${res.statusText}`);
  }
  return await res.json();
}

export async function fetchActiveDoc() {
  const res = await fetch(`${API_BASE}/active-doc`, {
    headers: getHeaders(),
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch active document: ${res.statusText}`);
  }
  return await res.json();
}

export async function uploadDocument(file) {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${API_BASE}/upload`, {
    method: 'POST',
    headers: {
      'X-API-Key': getApiKey(),
    },
    body: formData,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Upload failed: ${res.statusText}`);
  }
  return await res.json();
}

export async function streamChat({
  message,
  threadId,
  activeDoc,
  onToolCall,
  onDelta,
  onDone,
  onError,
}) {
  try {
    const res = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers: getHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        message,
        thread_id: threadId,
        active_doc: activeDoc,
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Chat request failed with ${res.status}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || ''; // Keep partial line

      let currentEvent = 'message';

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;

        if (trimmed.startsWith('event:')) {
          currentEvent = trimmed.slice(6).trim();
        } else if (trimmed.startsWith('data:')) {
          const rawData = trimmed.slice(5).trim();
          try {
            const parsed = JSON.parse(rawData);

            if (currentEvent === 'tool' && onToolCall) {
              onToolCall(parsed);
            } else if (currentEvent === 'delta' && onDelta) {
              onDelta(parsed.content || '');
            } else if (currentEvent === 'done' && onDone) {
              onDone(parsed);
            } else if (currentEvent === 'error' && onError) {
              onError(new Error(parsed.error || 'Server stream error'));
            }
          } catch (e) {
            console.error('Failed to parse SSE payload:', rawData, e);
          }
        }
      }
    }
  } catch (err) {
    if (onError) onError(err);
    else throw err;
  }
}
