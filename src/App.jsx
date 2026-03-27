// App.jsx
import React, { useState, useEffect, useRef } from "react";
import "./App.css";

const API_BASE_URL = "http://localhost:8000";

function App() {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState("");
  const [sessionId, setSessionId] = useState(() => {
    const savedSessionId = localStorage.getItem("chat_session_id");
    if (savedSessionId) return savedSessionId;
    const newSessionId = `user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    localStorage.setItem("chat_session_id", newSessionId);
    return newSessionId;
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [useRAG, setUseRAG] = useState(false);
  const [ragStatus, setRagStatus] = useState(null);
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const fileInputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    loadChatHistory();
    checkRAGStatus();
  }, [sessionId]);

  const loadChatHistory = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/history/${sessionId}`);
      if (response.ok) {
        const history = await response.json();
        const formattedHistory = history.map((msg) => ({
          role: msg.role === "human" ? "user" : "assistant",
          content: msg.content,
        }));
        setMessages(formattedHistory);
      }
    } catch (err) {
      console.error("Failed to load history:", err);
    }
  };

  const checkRAGStatus = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/rag/status`);
      if (response.ok) {
        const status = await response.json();
        setRagStatus(status);
      }
    } catch (err) {
      console.error("Failed to check RAG status:", err);
    }
  };

  const sendMessage = async (e) => {
    e.preventDefault();

    if (!inputMessage.trim()) return;

    const userMessage = inputMessage.trim();
    setInputMessage("");
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: userMessage,
          session_id: sessionId,
          use_rag: useRAG,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      // Format response with sources if available
      let responseContent = data.response;
      if (data.sources && data.sources.length > 0) {
        responseContent += "\n\n📚 **Sources:**\n";
        data.sources.forEach((source, idx) => {
          responseContent += `${idx + 1}. ${source.source} (${source.sheet}) - Relevance: ${(source.relevance_score * 100).toFixed(1)}%\n`;
        });
      }

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: responseContent,
        },
      ]);
    } catch (err) {
      console.error("Failed to send message:", err);
      setError("Failed to get response. Please try again.");
      setMessages((prev) => prev.slice(0, -1));
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  };

  const clearHistory = async () => {
    if (window.confirm("Are you sure you want to clear the chat history?")) {
      try {
        const response = await fetch(`${API_BASE_URL}/history/${sessionId}`, {
          method: "DELETE",
        });

        if (response.ok) {
          setMessages([]);
          setError(null);
        }
      } catch (err) {
        console.error("Failed to clear history:", err);
        setError("Failed to clear chat history");
      }
    }
  };

  const newSession = () => {
    if (
      window.confirm("Start a new session? This will clear the current chat.")
    ) {
      const newSessionId = `user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      localStorage.setItem("chat_session_id", newSessionId);
      setSessionId(newSessionId);
      setMessages([]);
      setError(null);
    }
  };

  const uploadFiles = async (event) => {
    const files = Array.from(event.target.files);
    if (files.length === 0) return;

    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));

    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/rag/upload`, {
        method: "POST",
        body: formData,
      });

      if (response.ok) {
        const result = await response.json();
        setUploadedFiles(result.files);
        setError(null);

        // Ask if user wants to index immediately
        if (window.confirm("Files uploaded. Do you want to index them now?")) {
          await indexDocuments();
        }
      } else {
        throw new Error("Upload failed");
      }
    } catch (err) {
      console.error("Failed to upload files:", err);
      setError("Failed to upload files");
    } finally {
      setIsLoading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const indexDocuments = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/rag/index`, {
        method: "POST",
      });

      if (response.ok) {
        const result = await response.json();
        setError(null);
        alert(
          `Successfully indexed ${result.files_processed} documents with ${result.chunks_created} chunks!`,
        );
        await checkRAGStatus();
      } else {
        throw new Error("Indexing failed");
      }
    } catch (err) {
      console.error("Failed to index documents:", err);
      setError("Failed to index documents");
    } finally {
      setIsLoading(false);
    }
  };

  const clearVectorStore = async () => {
    if (
      window.confirm(
        "Are you sure you want to clear the vector store? This will remove all indexed documents.",
      )
    ) {
      try {
        const response = await fetch(`${API_BASE_URL}/rag/clear`, {
          method: "DELETE",
        });

        if (response.ok) {
          setError(null);
          await checkRAGStatus();
          alert("Vector store cleared successfully");
        }
      } catch (err) {
        console.error("Failed to clear vector store:", err);
        setError("Failed to clear vector store");
      }
    }
  };

  return (
    <div className="App">
      <div className="chat-container">
        <div className="chat-header">
          <h1>🤖 AI Chatbot Assistant with RAG</h1>
          <div className="header-buttons">
            <button onClick={newSession} className="new-session-btn">
              🆕 New Session
            </button>
            <button onClick={clearHistory} className="clear-history-btn">
              🗑️ Clear History
            </button>
          </div>

          {/* RAG Controls */}
          <div className="rag-controls">
            <label className="rag-toggle">
              <input
                type="checkbox"
                checked={useRAG}
                onChange={(e) => setUseRAG(e.target.checked)}
              />
              Enable RAG (Query Documents)
            </label>

            {ragStatus && (
              <div className="rag-status">
                📊 Vector Store:{" "}
                {ragStatus.vector_store_initialized
                  ? `${ragStatus.vector_store_size} chunks`
                  : "Not initialized"}
              </div>
            )}

            <div className="rag-actions">
              <input
                type="file"
                ref={fileInputRef}
                onChange={uploadFiles}
                accept=".xlsx,.xls"
                multiple
                style={{ display: "none" }}
                id="file-upload"
              />
              <button
                onClick={() => document.getElementById("file-upload").click()}
                className="upload-btn"
                disabled={isLoading}
              >
                📤 Upload Excel Files
              </button>
              <button
                onClick={indexDocuments}
                className="index-btn"
                disabled={isLoading}
              >
                🔄 Index Documents
              </button>
              <button
                onClick={clearVectorStore}
                className="clear-rag-btn"
                disabled={isLoading}
              >
                🗑️ Clear Vector Store
              </button>
            </div>
          </div>

          <div className="session-info">
            <small>Session ID: {sessionId}</small>
          </div>
        </div>

        <div className="messages-container">
          {messages.length === 0 && !isLoading && (
            <div className="welcome-message">
              <p>Welcome! Start a conversation with the AI assistant.</p>
              {useRAG && ragStatus?.vector_store_initialized && (
                <p className="rag-info">
                  🔍 RAG mode is enabled! I can answer questions based on your
                  uploaded Excel documents.
                </p>
              )}
              <p className="example-prompts">
                Try asking: "What can you help me with?" or "Tell me a fun
                fact!"
              </p>
            </div>
          )}

          {messages.map((message, index) => (
            <div
              key={index}
              className={`message ${message.role === "user" ? "user-message" : "assistant-message"}`}
            >
              <div className="message-content">
                <strong>
                  {message.role === "user" ? "You" : "Assistant"}:
                </strong>
                <p style={{ whiteSpace: "pre-wrap" }}>{message.content}</p>
              </div>
            </div>
          ))}

          {isLoading && (
            <div className="message assistant-message loading">
              <div className="message-content">
                <strong>Assistant:</strong>
                <div className="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          )}

          {error && <div className="error-message">⚠️ {error}</div>}

          <div ref={messagesEndRef} />
        </div>

        <form onSubmit={sendMessage} className="input-form">
          <input
            ref={inputRef}
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            placeholder={
              useRAG
                ? "Ask about your documents..."
                : "Type your message here..."
            }
            disabled={isLoading}
            className="message-input"
          />
          <button type="submit" disabled={isLoading || !inputMessage.trim()}>
            {isLoading ? "Sending..." : "Send"}
          </button>
        </form>
      </div>
    </div>
  );
}

export default App;
