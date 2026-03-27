from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import SQLChatMessageHistory

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# LLM
llm = ChatOllama(
    base_url="http://localhost:11434",
    model="qwen3"
)

# Prompt + chain
template = ChatPromptTemplate.from_template("{prompt}")
chain = template | llm | StrOutputParser()

# History storage
def get_session_history(session_id: str):
    return SQLChatMessageHistory(
        session_id=session_id,
        connection="sqlite:///chat_history.db"
    )

# Wrap with history
chain_with_history = RunnableWithMessageHistory(
    chain,
    get_session_history
)

# Request model
class ChatRequest(BaseModel):
    message: str
    session_id: str

# Chat endpoint
@app.post("/chat")
def chat(req: ChatRequest):
    response = chain_with_history.invoke(
        {"prompt": req.message},
        config={"configurable": {"session_id": req.session_id}}
    )

    return {"response": response}

# Get history endpoint
@app.get("/history/{session_id}")
def get_history(session_id: str):
    history = get_session_history(session_id)
    messages = history.messages

    return [
        {"role": msg.type, "content": msg.content}
        for msg in messages
    ]