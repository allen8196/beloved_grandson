# services/web-app/Dockerfile

# 使用官方 Python 映像檔
FROM python:3.13

# 設定工作目錄
WORKDIR /usr/src/app

# 安裝系統依賴 (如果需要編譯某些 Python 套件)
# RUN apt-get update && apt-get install -y ...

COPY . .

RUN pip install --no-cache-dir -r requirements.txt \
    && sed -i 's/\r$//' entrypoint.sh \
    && chmod +x entrypoint.sh

EXPOSE 5000

# 在開發環境中，啟動命令由 docker-compose.dev.yml 的 command 覆蓋
CMD ["gunicorn", "--worker-class", "gevent", "--workers", "1", "--bind", "0.0.0.0:5000", "wsgi:app"]
