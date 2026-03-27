# main.py
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Dict
import logging
from contextlib import asynccontextmanager
import sqlite3
from pathlib import Path
import os
import pandas as pd
from dotenv import load_dotenv
import shutil
from datetime import datetime

# LangChain imports
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_community.document_loaders import DataFrameLoader

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", "chat_history.db"))
RAG_DATA_PATH = Path(os.getenv("RAG_DATA_PATH", "knowledge-base"))  # Changed from rag-dataset
VECTOR_STORE_PATH = Path(os.getenv("VECTOR_STORE_PATH", "vector_stores/health_supplements"))
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("MODEL_NAME", "qwen3")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")

# Pydantic models
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: str = Field(..., min_length=1)
    use_rag: bool = Field(default=False)  # Option to use RAG

class ChatResponse(BaseModel):
    response: str
    session_id: str
    sources: Optional[List[Dict]] = None  # Sources for RAG responses

class Message(BaseModel):
    role: str
    content: str

class RAGQuery(BaseModel):
    query: str
    k: int = Field(default=5, ge=1, le=10)

class DocumentUploadResponse(BaseModel):
    message: str
    files_processed: int
    chunks_created: int
    vector_store_size: int

# Global variables
vector_store = None
text_splitter = None
embeddings = None

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    global vector_store, text_splitter, embeddings
    
    # Startup
    logger.info("Starting up FastAPI application...")
    
    # Ensure directories exist
    DATABASE_PATH.parent.mkdir(exist_ok=True)
    RAG_DATA_PATH.mkdir(exist_ok=True)
    VECTOR_STORE_PATH.parent.mkdir(exist_ok=True)
    
    # Initialize database
    init_database()
    
    # Initialize text splitter
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100,
        length_function=len,
        separators=["\n\n", "\n", " ", ""]
    )
    
    # Initialize embeddings
    try:
        embeddings = OllamaEmbeddings(
            base_url=OLLAMA_BASE_URL,
            model=EMBEDDING_MODEL
        )
        logger.info(f"Embeddings model {EMBEDDING_MODEL} initialized")
    except Exception as e:
        logger.error(f"Failed to initialize embeddings: {e}")
    
    # Load existing vector store if available
    if VECTOR_STORE_PATH.exists():
        try:
            vector_store = FAISS.load_local(
                str(VECTOR_STORE_PATH), 
                embeddings,
                allow_dangerous_deserialization=True
            )
            logger.info(f"Vector store loaded from {VECTOR_STORE_PATH}")
        except Exception as e:
            logger.error(f"Failed to load vector store: {e}")
            vector_store = None
    else:
        logger.info("No existing vector store found. Create one by uploading documents.")
    
    yield
    
    # Shutdown
    logger.info("Shutting down FastAPI application...")

app = FastAPI(
    title="Chatbot API with RAG",
    description="API for interacting with Ollama-powered chatbot with RAG capabilities",
    version="2.0.0",
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

def load_excel_files():
    """Load all Excel files from the RAG dataset folder and its subdirectories"""
    documents = []
    
    # Recursively find all Excel files in RAG_DATA_PATH and subdirectories
    excel_files = list(RAG_DATA_PATH.rglob("*.xlsx")) + list(RAG_DATA_PATH.rglob("*.xls"))
    
    if not excel_files:
        logger.warning(f"No Excel files found in {RAG_DATA_PATH}")
        return documents
    
    for file_path in excel_files:
        try:
            # Get relative path for better context in metadata
            relative_path = file_path.relative_to(RAG_DATA_PATH)
            folder_path = str(relative_path.parent) if relative_path.parent != Path('.') else 'root'
            
            logger.info(f"Processing {relative_path}...")
            
            # Read Excel file
            df = pd.read_excel(file_path, sheet_name=None)  # Read all sheets
            
            for sheet_name, sheet_df in df.items():
                # Convert each row to text
                for idx, row in sheet_df.iterrows():
                    # Create a more informative text representation
                    row_text = f"File: {relative_path}\n"
                    row_text += f"Folder: {folder_path}\n"
                    row_text += f"Sheet: {sheet_name}\n"
                    row_text += f"Row: {idx + 1}\n\n"
                    
                    # Add row data
                    for col in sheet_df.columns:
                        if pd.notna(row[col]):
                            # Handle different data types
                            value = str(row[col]).strip()
                            if value:
                                row_text += f"{col}: {value}\n"
                    
                    # Create document with comprehensive metadata
                    doc = Document(
                        page_content=row_text,
                        metadata={
                            "source": str(relative_path),
                            "folder": folder_path,
                            "sheet": sheet_name,
                            "row_number": idx + 1,
                            "file_type": "excel",
                            "full_path": str(file_path)
                        }
                    )
                    documents.append(doc)
            
            logger.info(f"Loaded {len(sheet_df)} rows from {relative_path}")
            
        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")
    
    logger.info(f"Total documents loaded: {len(documents)}")
    return documents

def process_and_index_documents():
    """Process documents, split into chunks, and index in FAISS"""
    global vector_store
    
    if not embeddings:
        raise HTTPException(status_code=500, detail="Embeddings model not initialized")
    
    # Load documents from Excel files
    documents = load_excel_files()
    
    if not documents:
        raise HTTPException(status_code=404, detail="No documents found to process")
    
    # Split documents into chunks
    chunks = text_splitter.split_documents(documents)
    logger.info(f"Created {len(chunks)} chunks from {len(documents)} documents")
    
    # Count tokens for each chunk (approximate)
    for i, chunk in enumerate(chunks):
        # Approximate token count (4 chars ≈ 1 token)
        token_count = len(chunk.page_content) // 4
        chunk.metadata["token_count"] = token_count
        logger.debug(f"Chunk {i}: {token_count} tokens")
    
    # Create or update vector store
    if vector_store is None:
        vector_store = FAISS.from_documents(chunks, embeddings)
    else:
        vector_store.add_documents(chunks)
    
    # Save vector store locally
    vector_store.save_local(str(VECTOR_STORE_PATH))
    logger.info(f"Vector store saved to {VECTOR_STORE_PATH} with {vector_store.index.ntotal} vectors")
    
    return {
        "documents_processed": len(documents),
        "chunks_created": len(chunks),
        "vector_store_size": vector_store.index.ntotal
    }

def retrieve_relevant_context(query: str, k: int = 5):
    """Retrieve relevant chunks from vector store"""
    global vector_store
    
    if vector_store is None:
        return []
    
    try:
        # Search for relevant documents
        docs_with_scores = vector_store.similarity_search_with_score(query, k=k)
        
        # Format results
        results = []
        for doc, score in docs_with_scores:
            results.append({
                "content": doc.page_content,
                "metadata": doc.metadata,
                "relevance_score": float(score)
            })
        
        return results
    except Exception as e:
        logger.error(f"Error retrieving context: {e}")
        return []

def create_rag_prompt(query: str, context: List[Dict]):
    """Create a prompt with retrieved context"""
    if not context:
        return query
    
    # Format context
    context_text = "\n\n".join([
        f"Source: {item['metadata'].get('source', 'Unknown')}\n"
        f"Sheet: {item['metadata'].get('sheet', 'Unknown')}\n"
        f"Content: {item['content']}"
        for item in context
    ])
    
    # Create RAG 
    promptrag_prompt = f"""You are a helpful assistant analyzing Excel spreadsheet data. Use the information from the Excel files below to answer questions accurately.


Context from documents:
{context_text}

Question: {query}

Please answer the question based on the context provided above. If the answer cannot be found in the context, say so politely and suggest what information might be helpful.
"""
    
    return promptrag_prompt

def create_chain():
    """Create the base chain"""
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

# API Endpoints
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Chatbot API with RAG",
        "version": "2.0.0",
        "status": "operational",
        "features": ["chat", "rag", "document_upload", "vector_search"],
        "endpoints": [
            "/chat",
            "/rag/query",
            "/rag/upload",
            "/rag/index",
            "/history/{session_id}",
            "/health"
        ]
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        llm = get_llm()
        status = {
            "status": "healthy",
            "llm_status": "connected",
            "vector_store_status": "available" if vector_store else "not_initialized",
            "vector_store_size": vector_store.index.ntotal if vector_store else 0,
            "embedding_model": EMBEDDING_MODEL
        }
        return status
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Chat endpoint with optional RAG support"""
    try:
        user_query = req.message
        sources = None
        
        # If RAG is enabled, retrieve context first
        if req.use_rag and vector_store:
            context = retrieve_relevant_context(user_query, k=5)
            if context:
                # Enhance the query with context
                enhanced_query = create_rag_prompt(user_query, context)
                sources = [
                    {
                        "source": item["metadata"].get("source", "Unknown"),
                        "sheet": item["metadata"].get("sheet", "Unknown"),
                        "relevance_score": item["relevance_score"]
                    }
                    for item in context
                ]
            else:
                enhanced_query = user_query
        else:
            enhanced_query = user_query
        
        # Get response from LLM
        response = chain_with_history.invoke(
            {"input": enhanced_query},
            config={"configurable": {"session_id": req.session_id}}
        )
        
        return ChatResponse(
            response=response,
            session_id=req.session_id,
            sources=sources
        )
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")

@app.post("/rag/upload")
async def upload_documents(files: List[UploadFile] = File(...)):
    """Upload Excel files to the RAG dataset folder"""
    uploaded_files = []
    
    for file in files:
        if not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
            continue
        
        file_path = RAG_DATA_PATH / file.filename
        
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        uploaded_files.append(file.filename)
        logger.info(f"Uploaded {file.filename}")
    
    return {
        "message": f"Uploaded {len(uploaded_files)} files",
        "files": uploaded_files
    }

@app.post("/rag/index", response_model=DocumentUploadResponse)
async def index_documents():
    """Process all Excel files in the RAG dataset folder and create vector index"""
    try:
        result = process_and_index_documents()
        
        return DocumentUploadResponse(
            message="Documents processed and indexed successfully",
            files_processed=result["documents_processed"],
            chunks_created=result["chunks_created"],
            vector_store_size=result["vector_store_size"]
        )
    except Exception as e:
        logger.error(f"Indexing error: {e}")
        raise HTTPException(status_code=500, detail=f"Indexing failed: {str(e)}")

@app.post("/rag/query")
async def rag_query(query: RAGQuery):
    """Query the vector store directly without LLM"""
    if not vector_store:
        raise HTTPException(status_code=404, detail="Vector store not initialized")
    
    results = retrieve_relevant_context(query.query, k=query.k)
    
    return {
        "query": query.query,
        "results": results,
        "total_found": len(results)
    }

@app.get("/rag/status")
async def rag_status():
    """Get RAG system status with folder structure"""
    # Get all Excel files recursively
    excel_files = list(RAG_DATA_PATH.rglob("*.xlsx")) + list(RAG_DATA_PATH.rglob("*.xls"))
    
    # Group files by folder
    files_by_folder = {}
    for file_path in excel_files:
        relative_path = file_path.relative_to(RAG_DATA_PATH)
        folder = str(relative_path.parent) if relative_path.parent != Path('.') else 'root'
        
        if folder not in files_by_folder:
            files_by_folder[folder] = []
        files_by_folder[folder].append(str(relative_path.name))
    
    return {
        "vector_store_initialized": vector_store is not None,
        "vector_store_size": vector_store.index.ntotal if vector_store else 0,
        "embedding_model": EMBEDDING_MODEL,
        "data_folder": str(RAG_DATA_PATH),
        "vector_store_path": str(VECTOR_STORE_PATH),
        "folder_structure": files_by_folder,
        "total_files": len(excel_files)
    }

@app.delete("/rag/clear")
async def clear_vector_store():
    """Clear the vector store"""
    global vector_store
    
    try:
        if vector_store:
            vector_store = None
            # Remove vector store files
            if VECTOR_STORE_PATH.exists():
                shutil.rmtree(VECTOR_STORE_PATH)
            logger.info("Vector store cleared")
        
        return {"message": "Vector store cleared successfully"}
    except Exception as e:
        logger.error(f"Failed to clear vector store: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear: {str(e)}")

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