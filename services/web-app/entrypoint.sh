#!/bin/sh

# 讓 Flask-Migrate 執行資料庫遷移
# 這裡可以加入重試邏輯，以防資料庫容器還沒完全準備好
echo "Applying database migrations..."
flask db upgrade

# 執行 Dockerfile 中 CMD 指定的指令 (例如啟動 gunicorn)
echo "Starting application..."
exec "$@"
