from fastapi import FastAPI
from pydantic import BaseModel
from langchain_community.chat_models import ChatOllama

app = FastAPI()

# Ollama config
base_url = "http://localhost:11434"
model = "llama3.2"

llm = ChatOllama(base_url=base_url, model=model)

class Request(BaseModel):
    question: str

@app.post("/ask")
def ask(req: Request):
    response = llm.invoke(req.question)
    return {"answer": response.content}