// App.jsx
import React, { useState, useEffect, useRef } from "react";
import "./App.css";

const API_BASE_URL = "http://localhost:8000";

function App() {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState("");
  const [sessionId, setSessionId] = useState(() => {
    // Generate or retrieve session ID from localStorage
    const savedSessionId = localStorage.getItem("chat_session_id");
    if (savedSessionId) return savedSessionId;
    const newSessionId = `user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    localStorage.setItem("chat_session_id", newSessionId);
    return newSessionId;
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // Auto-scroll to bottom when messages change
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Load chat history on mount
  useEffect(() => {
    loadChatHistory();
  }, [sessionId]);

  const loadChatHistory = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/history/${sessionId}`);
      if (response.ok) {
        const history = await response.json();
        // Convert history to message format
        const formattedHistory = history.map((msg) => ({
          role: msg.role === "human" ? "user" : "assistant",
          content: msg.content,
        }));
        setMessages(formattedHistory);
      }
    } catch (err) {
      console.error("Failed to load history:", err);
      setError("Failed to load chat history");
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
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.response,
        },
      ]);
    } catch (err) {
      console.error("Failed to send message:", err);
      setError("Failed to get response. Please try again.");
      // Remove the user message if failed
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
        } else {
          throw new Error("Failed to clear history");
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

  return (
    <div className="App">
      <div className="chat-container">
        <div className="chat-header">
          <h1>🤖 AI Chatbot Assistant</h1>
          <div className="header-buttons">
            <button onClick={newSession} className="new-session-btn">
              🆕 New Session
            </button>
            <button onClick={clearHistory} className="clear-history-btn">
              🗑️ Clear History
            </button>
          </div>
          <div className="session-info">
            <small>Session ID: {sessionId}</small>
          </div>
        </div>

        <div className="messages-container">
          {messages.length === 0 && !isLoading && (
            <div className="welcome-message">
              <p>Welcome! Start a conversation with the AI assistant.</p>
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
                <p>{message.content}</p>
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
            placeholder="Type your message here..."
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
