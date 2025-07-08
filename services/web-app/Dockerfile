# services/web-app/Dockerfile
# 這是一個佔位用的 Dockerfile，請根據實際的應用程式需求進行修改。
# 例如：安裝 Python 依賴、複製程式碼、設定啟動命令等。

FROM python:3.10-slim

# 1. 設定工作目錄
WORKDIR /app

# 2. 複製依賴需求檔案
COPY requirements.txt .

# 3. 安裝依賴 (此處註解，因 requirements.txt 為空)
# RUN pip install --no-cache-dir -r requirements.txt

# 4. 複製應用程式原始碼
# COPY . .

# 5. 設定啟動命令 (範例)
# CMD ["flask", "run", "--host=0.0.0.0"]

# 暫時的啟動命令，讓容器保持運行以供開發
CMD ["tail", "-f", "/dev/null"]
