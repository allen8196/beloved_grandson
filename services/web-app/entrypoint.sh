#!/bin/sh

# 讓 Flask-Migrate 執行資料庫遷移
echo "Applying database migrations..."
flask db upgrade

# 啟動 Gunicorn，並使用 gevent 作為 worker 類別
# 這對於支援 Flask-SocketIO 至關重要
echo "Starting Gunicorn with gevent worker..."
exec gunicorn --worker-class gevent --workers 1 --bind 0.0.0.0:5000 wsgi:app
