import os
from typing import Dict, Any

# 兼容「模組方式」與「直接腳本」兩種執行情境
try:
    from .chat_pipeline import AgentManager, handle_user_message
except Exception:
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))  # 加入 /app/worker 到 sys.path
    from llm_app.chat_pipeline import AgentManager, handle_user_message


class LLMService:
    def __init__(self) -> None:
        self.agent_manager = AgentManager()

    def generate_response(self, task_data: Dict[str, Any]) -> str:
        """直接串接 Final 專案的對話管線。

        期待的 task_data 欄位對應：
        - patient_id -> 對應 Final 的 user_id
        - text -> 對應 Final 的 query（可選）
        - object_name -> 對應 Final 的 audio_id（可選）
        """
        if not isinstance(task_data, dict):
            return "參數格式錯誤"

        user_id = str(task_data.get("patient_id") or task_data.get("user_id") or "unknown_user")
        query = str(task_data.get("text") or "").strip()
        audio_id = None
        # 優先使用 object_name 當 audio_id；若沒有且為純文字則由流程自動以 hash 產生
        if task_data.get("object_name"):
            audio_id = str(task_data.get("object_name"))

        if not query and not audio_id:
            return "缺少必要輸入（text 或 object_name 至少一項）"

        try:
            # 為了與 Final 對齊，若沒有 text 但有語音 audio_id，這裡的 query 可為空字串，流程會合併 buffer
            response_text = handle_user_message(
                agent_manager=self.agent_manager,
                user_id=user_id,
                query=query,
                audio_id=audio_id,
                is_final=True,
            )
            return response_text
        except Exception as e:
            print(f"[LLMService] 發生錯誤：{e}")
            return "抱歉，無法生成回應。"

if __name__ == "__main__":
    # 多輪測試（涵蓋：純文字、多輪、含 audio_id 的案例）
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass

    # 測試 LLMService
    # 0. .env.example 改成 .env ，可以不做任何設定
    # 1. 啟動ai-worker和相關的容器
    # docker-compose -f docker-compose.dev.yml up -d --build ai-worker

    # 2. 執行測試腳本
    # docker-compose -f docker-compose.dev.yml exec ai-worker python worker/llm_app/llm_service.py

    #! task_data： LLM RAG 需要什麼內容，請找做後端的人要，後端會處理並將資料放置在task_data裡面
    # task_data = {'patient_id': 1, 'text': '台式晚餐有哪些'}  # 文字訊息
    task_data = {
        'patient_id': 1,
        'text': '台式晚餐有哪些',
        'object_name': '1_6ec5df00-a2fa-4ee3-9191-7beed37bb42f.m4a'
    }
    llm_service = LLMService()

    test_cases = [
        {  # 純文字：一般健康諮詢
            'patient_id': 1,
            'text': '我最近常常咳嗽，該注意什麼？'
        },
        {  # 純文字：含情緒表達
            'patient_id': 1,
            'text': '最近心情不好，睡也睡不好，該怎樣調整？'
        },
        {  # 純文字：與 COPD 相關，測試 Milvus 搜尋
            'patient_id': 1,
            'text': '慢阻肺的日常保養要注意什麼？'
        },
        {  # 含 audio_id（模擬語音情境，同時給予文字作為 STT 結果）
            'patient_id': 1,
            'text': '我運動時會喘，該怎麼安排運動？',
            'object_name': '1_demo_audio_001.m4a'
        },
        {  # 含 audio_id：不同一輪，檢視緩存/歷史行為
            'patient_id': 1,
            'text': '最近食慾不好，晚餐想吃清淡一點，有什麼建議？',
            'object_name': '1_demo_audio_002.m4a'
        },
    ]

    for i, tc in enumerate(test_cases, start=1):
        print(f"\n===== 第 {i} 輪 測試開始 =====")
        print(f"用戶輸入: {tc.get('text','')}")
        if tc.get('object_name'):
            print(f"音檔ID: {tc['object_name']}")
        reply = llm_service.generate_response(task_data=tc)
        print(f"AI 回應: {reply}")
        print(f"===== 第 {i} 輪 測試結束 =====\n")
