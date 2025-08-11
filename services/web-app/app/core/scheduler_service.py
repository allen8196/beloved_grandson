# services/web-app/app/core/scheduler_service.py
import logging

# 配置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def scheduled_task():
    """
    這是一個範例排程任務，每分鐘會被執行一次。
    在實際應用中，這裡可以放置需要定期執行的程式碼，
    例如：清理過期資料、傳送每日報告、同步外部資料等。
    """
    print("-------------------------------------------------")
    logger.info("排程任務執行中... 這條訊息每一分鐘會出現一次。")
