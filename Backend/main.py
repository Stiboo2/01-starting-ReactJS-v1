# main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import logging
from contextlib import asynccontextmanager
import sqlite3
from pathlib import Path
import os
from dotenv import load_dotenv

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import SQLChatMessageHistory

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", "chat_history.db"))
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("MODEL_NAME", "qwen3")

# Pydantic models
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: str = Field(..., min_length=1)

class ChatResponse(BaseModel):
    response: str
    session_id: str

class Message(BaseModel):
    role: str
    content: str

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up FastAPI application...")
    
    # Ensure database directory exists
    DATABASE_PATH.parent.mkdir(exist_ok=True)
    
    # Initialize database
    init_database()
    
    yield
    
    # Shutdown
    logger.info("Shutting down FastAPI application...")

app = FastAPI(
    title="Chatbot API",
    description="API for interacting with Ollama-powered chatbot",
    version="1.0.0",
    lifespan=lifespan
)

# CORS - Allow React app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def init_database():
    """Initialize database with proper schema"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS message_store (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                message_type TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_session_id 
            ON message_store(session_id)
        """)
        
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")

def get_llm():
    """Get LLM instance"""
    try:
        return ChatOllama(
            base_url=OLLAMA_BASE_URL,
            model=DEFAULT_MODEL,
            temperature=0.7,
            timeout=60
        )
    except Exception as e:
        logger.error(f"Failed to initialize LLM: {e}")
        raise HTTPException(status_code=503, detail="LLM service unavailable")

def get_session_history(session_id: str):
    """Get session history"""
    try:
        return SQLChatMessageHistory(
            session_id=session_id,
            connection=f"sqlite:///{DATABASE_PATH}"
        )
    except Exception as e:
        logger.error(f"Failed to get session history: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve history")

def create_chain():
    """Create the chain with proper prompting"""
    system = SystemMessagePromptTemplate.from_template(
        "You are a helpful, friendly assistant. Provide clear and concise responses."
    )
    human = HumanMessagePromptTemplate.from_template("{input}")
    
    messages = [
        system,
        MessagesPlaceholder(variable_name="history"),
        human
    ]
    
    prompt = ChatPromptTemplate(messages=messages)
    llm = get_llm()
    
    return prompt | llm | StrOutputParser()

# Initialize chain
chain = create_chain()

chain_with_history = RunnableWithMessageHistory(
    chain,
    get_session_history,
    input_messages_key="input",
    history_messages_key="history"
)

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Chatbot API",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": ["/chat", "/history/{session_id}", "/health"]
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test LLM connection with sync call
        llm = get_llm()
        # Use sync invoke instead of ainvoke to avoid async issues
        response = llm.invoke("Test connection")
        return {"status": "healthy", "llm_status": "connected"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Chat endpoint - using sync invoke to avoid async issues"""
    try:
        # Use sync invoke instead of ainvoke
        response = chain_with_history.invoke(
            {"input": req.message},
            config={"configurable": {"session_id": req.session_id}}
        )
        
        return ChatResponse(
            response=response,
            session_id=req.session_id
        )
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")

@app.get("/history/{session_id}", response_model=List[Message])
async def get_history(session_id: str, limit: Optional[int] = 50):
    """Get conversation history"""
    try:
        history = get_session_history(session_id)
        messages = history.messages[-limit:]
        
        return [
            Message(role=msg.type, content=msg.content)
            for msg in messages
        ]
    except Exception as e:
        logger.error(f"Failed to get history: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve history")

@app.delete("/history/{session_id}")
async def clear_history(session_id: str):
    """Clear conversation history"""
    try:
        history = get_session_history(session_id)
        history.clear()
        return {"message": "History cleared successfully", "session_id": session_id}
    except Exception as e:
        logger.error(f"Failed to clear history: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear history")