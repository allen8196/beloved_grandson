# services/web-app/Dockerfile

# 1. 使用官方 Python 映像檔
FROM python:3.13

# 2. 設定工作目錄
WORKDIR /usr/src/app

# 3. 安裝系統依賴 (如果需要編譯某些 Python 套件)
# RUN apt-get update && apt-get install -y ...

# 4. 複製 requirements.txt 並安裝 Python 依賴
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. 複製整個應用程式程式碼
COPY . .

# 6. 設定環境變數
EXPOSE 5000

ENTRYPOINT ["/usr/src/app/entrypoint.sh"]

# CMD 會在容器啟動時執行
CMD ["sh", "-c", "if [ \"$FLASK_ENV\" = \"development\" ]; then flask run --host=0.0.0.0 --port=5000 --debug; else gunicorn --bind 0.0.0.0:5000 wsgi:app; fi"]
