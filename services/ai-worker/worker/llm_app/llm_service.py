import google.generativeai as genai
import os

class LLMService:
    def generate_response(self, text: str) -> str:
        """
        Generates a response from the LLM.
        This is a placeholder implementation.
        """
        # 實際的 LLM 呼叫邏輯會在這裡
        genai.configure(api_key=os.environ.get("GOOGLE_API_KEY", ""))
        model = genai.GenerativeModel('gemini-2.5-flash')

        print(f"提示詞：{text}")
        try:
            response = model.generate_content(text)

        except Exception as e:
            print(f"發生錯誤：{e}")
            return "抱歉，無法生成回應。"
        print(f"生成回應的提示詞：{response.text}")
        return response.text
