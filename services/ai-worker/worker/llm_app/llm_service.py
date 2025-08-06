import os
import logging
from typing import Optional
import asyncio

class LLMService:
    def __init__(self):
        """
        初始化LLM服務
        這裡可以配置各種LLM API，如OpenAI、Claude、本地模型等
        """
        self.api_key = os.environ.get("OPENAI_API_KEY")
        self.model = os.environ.get("LLM_MODEL", "gpt-3.5-turbo")
        self.max_tokens = int(os.environ.get("LLM_MAX_TOKENS", "150"))
        self.temperature = float(os.environ.get("LLM_TEMPERATURE", "0.7"))
        
    async def generate_response(
        self, 
        message: str, 
        patient_id: Optional[str] = None,
        conversation_id: Optional[str] = None
    ) -> str:
        """
        生成AI回應
        
        Args:
            message: 用戶輸入的訊息
            patient_id: 患者ID（可選）
            conversation_id: 對話ID（可選）
            
        Returns:
            AI生成的回應文字
        """
        try:
            # 這裡可以整合真正的LLM API
            # 例如 OpenAI GPT、Claude、或本地部署的模型
            
            # 構建系統提示詞
            system_prompt = self._build_system_prompt(patient_id)
            
            # 模擬LLM回應（實際使用時需要調用真正的LLM API）
            if self.api_key and self._is_api_available():
                response = await self._call_openai_api(system_prompt, message)
            else:
                response = self._generate_fallback_response(message)
            
            logging.info(f"LLM response generated for patient {patient_id}: {response[:100]}...")
            return response
            
        except Exception as e:
            logging.error(f"LLM generation error: {e}", exc_info=True)
            return self._generate_fallback_response(message)
    
    def _build_system_prompt(self, patient_id: Optional[str]) -> str:
        """
        構建系統提示詞
        """
        base_prompt = """你是一個友善、專業的AI健康助理。請用中文回應用戶的問題。
        
特點：
- 保持溫暖、關懷的語調
- 提供有用的健康建議
- 如果涉及嚴重健康問題，建議諮詢專業醫師
- 回應簡潔明瞭，適合語音交互
- 不要超過100字
        """
        
        if patient_id and patient_id != "anonymous":
            base_prompt += f"\n\n當前與患者 {patient_id} 對話。"
        
        return base_prompt
    
    def _is_api_available(self) -> bool:
        """
        檢查API是否可用
        """
        # 這裡可以添加實際的API可用性檢查
        return False  # 暫時返回False使用fallback
    
    async def _call_openai_api(self, system_prompt: str, message: str) -> str:
        """
        調用OpenAI API
        """
        try:
            # 這裡需要實際的OpenAI API調用
            # import openai
            # 
            # response = await openai.ChatCompletion.acreate(
            #     model=self.model,
            #     messages=[
            #         {"role": "system", "content": system_prompt},
            #         {"role": "user", "content": message}
            #     ],
            #     max_tokens=self.max_tokens,
            #     temperature=self.temperature
            # )
            # 
            # return response.choices[0].message.content.strip()
            
            # 暫時模擬API回應
            await asyncio.sleep(0.1)  # 模擬API延遲
            return f"[AI回應] 我理解您說的「{message}」。作為您的健康助理，我建議您保持良好的作息和飲食習慣。如有任何健康疑慮，請諮詢專業醫師。"
            
        except Exception as e:
            logging.error(f"OpenAI API error: {e}")
            raise
    
    def _generate_fallback_response(self, message: str) -> str:
        """
        生成備用回應（當LLM API不可用時）
        """
        # 基於關鍵詞的簡單回應規則
        message_lower = message.lower()
        
        if any(word in message_lower for word in ['你好', '哈囉', 'hello', '嗨']):
            return "您好！我是您的AI健康助理，很高興為您服務。請問有什麼可以幫助您的嗎？"
        
        elif any(word in message_lower for word in ['謝謝', '感謝', '謝了']):
            return "不客氣！我很高興能夠幫助您。如果還有其他問題，請隨時告訴我。"
        
        elif any(word in message_lower for word in ['再見', '拜拜', 'bye']):
            return "再見！祝您身體健康，有需要時隨時回來找我。"
        
        elif any(word in message_lower for word in ['頭痛', '痛', '不舒服']):
            return "我理解您感到不適。建議您適當休息，如果症狀持續或加重，請儘快諮詢醫師。"
        
        elif any(word in message_lower for word in ['睡眠', '失眠', '睡不著']):
            return "良好的睡眠很重要。建議建立規律作息，避免睡前使用3C產品，如持續失眠請諮詢醫師。"
        
        elif any(word in message_lower for word in ['運動', '健身']):
            return "規律運動對健康很有益！建議每週至少150分鐘中等強度運動。請根據自己的身體狀況適量運動。"
        
        elif any(word in message_lower for word in ['飲食', '吃', '營養']):
            return "均衡飲食很重要！建議多吃蔬果、適量蛋白質，少糖少油。如有特殊飲食需求，請諮詢營養師。"
        
        else:
            return f"我聽到您說：「{message}」。作為AI健康助理，我建議保持良好生活習慣。如有健康疑慮，請諮詢專業醫師。"

# 單例模式
_llm_service_instance = LLMService()

def get_llm_service() -> LLMService:
    """Factory function to get the LLMService instance."""
    return _llm_service_instance