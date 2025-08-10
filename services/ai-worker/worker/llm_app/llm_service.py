import google.generativeai as genai
import os

class LLMService:
    def generate_response(self, task_data={}) -> str:
        """
        Generates a response from the LLM.
        This is a placeholder implementation.
        """
        # 實際的 LLM 呼叫邏輯會在這裡
        genai.configure(api_key=os.environ.get("GOOGLE_API_KEY", ""))
        model = genai.GenerativeModel('gemini-2.5-flash')

        print(f"提示詞：{task_data["text"]}")
        try:
            response = model.generate_content(task_data["text"])

        except Exception as e:
            print(f"發生錯誤：{e}")
            return "抱歉，無法生成回應。"
        print(f"生成回應的提示詞：{response.text}")
        return response.text

if __name__ == "__main__":
    # 測試 LLMService

    # 0. .env.example 改成 .env ，可以不做任何設定

    # 1. 啟動ai-worker和相關的容器
    # docker-compose -f docker-compose.dev.yml up -d --build ai-worker

    # 2. 執行測試腳本
    # docker-compose -f docker-compose.dev.yml exec ai-worker python worker/llm_app/llm_service.py

    #! task_data： LLM RAG 需要什麼內容，請找做後端的人要，後端會處理並將資料放置在task_data裡面
    # task_data = {'patient_id': 1, 'text': '台式晚餐有哪些'} # 文字訊息
    task_data = {'patient_id': 1, 'object_name': '1_6ec5df00-a2fa-4ee3-9191-7beed37bb42f.m4a', 'bucket_name': 'audio-uploads', 'duration_ms': 2560} # 語音訊息

    llm_service = LLMService()

    # 測試生成回應
    test_message_1 = "你好，我最近睡眠不好，該怎麼辦？"
    response_1 = llm_service.generate_response(task_data=task_data)
    print(f"用戶訊息: {test_message_1}")
    print(f"AI 回應: {response_1}\n")
