import { useState, useEffect } from "react";

const SESSION_ID = "thabo_user_1";

function App() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([]);

  // Load history on start
  useEffect(() => {
    fetch(`http://localhost:8000/history/${SESSION_ID}`)
      .then((res) => res.json())
      .then((data) => {
        setMessages(data);
      });
  }, []);

  const sendMessage = async () => {
    const userMessage = { role: "human", content: input };

    setMessages((prev) => [...prev, userMessage]);

    const res = await fetch("http://localhost:8000/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message: input,
        session_id: SESSION_ID,
      }),
    });

    const data = await res.json();

    const aiMessage = { role: "ai", content: data.response };

    setMessages((prev) => [...prev, aiMessage]);

    setInput("");
  };

  return (
    <div>
      <h1>Chat with Memory</h1>

      <div
        style={{
          height: "300px",
          overflowY: "scroll",
          border: "1px solid #ccc",
        }}
      >
        {messages.map((msg, i) => (
          <p key={i}>
            <b>{msg.role}:</b> {msg.content}
          </p>
        ))}
      </div>

      <input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="Type message..."
      />

      <button onClick={sendMessage}>Send</button>
    </div>
  );
}

export default App;
