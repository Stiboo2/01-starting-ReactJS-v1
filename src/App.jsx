import { useState } from "react";

function App() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");

  const askAI = async () => {
    const res = await fetch("http://localhost:8000/ask", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ question }),
    });

    const data = await res.json();
    setAnswer(data.answer);
  };

  return (
    <div>
      <header>
        <img
          src="/src/assets/react-core-concepts.png"
          alt="React logo"
          width="100"
        />
        <h1>Thabo React Essentials</h1>
        <p>
          Fundamental React concepts you will need for almost any app you are
          going to build!
        </p>
      </header>

      <main>
        <h2>AI Chat</h2>

        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask something..."
        />

        <button onClick={askAI}>Ask</button>

        <p><b>Answer:</b> {answer}</p>
      </main>
    </div>
  );
}

export default App;