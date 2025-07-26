from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.core.llm_service import LLMService
from app.dependencies import get_service # 從新的依賴檔案匯入

# 定義請求的資料模型
class ChatRequest(BaseModel):
    text: str

router = APIRouter()

@router.post("/chat")
async def chat_endpoint(
    request: ChatRequest,
    service: LLMService = Depends(get_service) # 使用新的依賴函式
):
    """
    Handles chat requests by calling the LLMService.
    """
    response_text = service.generate_response(request.text)
    return {"message": response_text}
