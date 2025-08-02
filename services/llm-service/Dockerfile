# services/llm-service/Dockerfile
FROM python:3.10-slim

WORKDIR /app

# 複製依賴文件並安裝
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製所有應用程式碼
COPY . .

# 執行 RabbitMQ 消費者，-u 參數可確保日誌即時輸出
CMD ["python", "-u", "app/main.py"]
