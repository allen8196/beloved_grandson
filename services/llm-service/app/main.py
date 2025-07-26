from fastapi import FastAPI
from app.api import chat

app = FastAPI(
    title="LLM Service",
    description="A service to interact with large language models.",
    version="0.1.0"
)

# 包含來自 api/chat.py 的路由，並加上 /api/v1 前綴
app.include_router(chat.router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"message": "Welcome to the LLM Service"}
