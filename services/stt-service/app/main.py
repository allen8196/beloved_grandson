from fastapi import FastAPI
from app.api import transcribe

app = FastAPI(
    title="Speech-to-Text (STT) Service",
    description="A service to transcribe audio files into text.",
    version="0.1.0"
)

app.include_router(transcribe.router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"message": "Welcome to the STT Service"}
