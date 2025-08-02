# services/web-app/Dockerfile

# 使用官方 Python 映像檔
FROM python:3.13

# 設定工作目錄
WORKDIR /usr/src/app

# 安裝系統依賴 (如果需要編譯某些 Python 套件)
# RUN apt-get update && apt-get install -y ...

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 5000

ENTRYPOINT ["/usr/src/app/entrypoint.sh"]

# CMD 提供容器的預設啟動命令。
# 這個命令會被 docker-compose.yml 中的 'command' 指令覆蓋。
# 我們將其設定為生產環境的啟動命令作為一個合理的預設值。
CMD ["gunicorn", "--worker-class", "gevent", "--workers", "1", "--bind", "0.0.0.0:5000", "wsgi:app"]
