from fastapi import FastAPI
from app.api import synthesize

app = FastAPI(
    title="Text-to-Speech (TTS) Service",
    description="A service to synthesize text into audio.",
    version="0.1.0"
)

app.include_router(synthesize.router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"message": "Welcome to the TTS Service"}
