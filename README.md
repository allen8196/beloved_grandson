# Beloved Grandson 專案

## 專案概述

「Beloved Grandson」是一個基於 Docker Compose 部署的微服務 AI 對話應用。它整合了語音轉文字 (STT)、大型語言模型 (LLM，支援 TAIDE 與 RAG)、文字轉語音 (TTS) 等核心 AI 功能，並透過訊息佇列實現服務間的解耦與非同步處理。本專案旨在提供一個高效、可擴展且易於維護的 AI 應用開發與部署框架。

### 核心架構組件

*   **前端/API Gateway**: `web-app` (Flask)，處理使用者請求、狀態協調、WebSocket 通訊。
*   **非同步任務處理**: `ai-worker`，消費來自 RabbitMQ 的任務，調度 AI 服務。
*   **AI 核心服務**: `stt-service` (語音轉文字)、`llm-service` (核心語言模型，整合 TAIDE 與 RAG)、`tts-service` (文字轉語音)。
*   **資料庫**: PostgreSQL (主要資料)、Redis (快取/任務結果)、Milvus (向量資料庫)、MinIO (物件儲存)。
*   **訊息佇列**: RabbitMQ。
*   **反向代理**: Nginx (生產環境)。

## 環境需求

在開始之前，請確保您的系統已安裝以下軟體：

*   **Docker**: 版本 20.10.0 或更高。
*   **Docker Compose**: 版本 1.29.0 或更高 (或 Docker Compose V2)。

## 安裝與設定

### 1. 複製專案

```bash
git clone <您的專案 Git URL>
cd beloved_grandson
```

### 2. 設定環境變數 (`.env` 檔案)

本專案使用 `.env` 檔案來管理敏感資訊和環境特定的配置。請根據 `.env.example` 檔案建立一個 `.env` 檔案，並填寫您的配置。

```bash
cp .env.example .env
```

編輯 `.env` 檔案，填寫以下變數：

```ini
# PostgreSQL 資料庫設定
POSTGRES_USER=admin
POSTGRES_PASSWORD=secret
POSTGRES_DB=ai_assistant_db

# RabbitMQ 設定 (生產環境建議修改預設值)
RABBITMQ_DEFAULT_USER=guest
RABBITMQ_DEFAULT_PASS=guest

# MinIO 設定 (生產環境建議修改預設值)
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# Flask 應用程式密鑰 (生產環境務必修改為強密鑰)
SECRET_KEY=your_super_secret_key_here
```

**重要提示**：在生產環境中，請務必將 `RABBITMQ_DEFAULT_USER`、`RABBITMQ_DEFAULT_PASS`、`MINIO_ACCESS_KEY`、`MINIO_SECRET_KEY` 和 `SECRET_KEY` 設定為複雜且安全的密碼。

## 環境啟動與管理

本專案提供兩種 Docker Compose 配置，分別用於**開發環境**和**生產環境**。

### 1. 開發環境 (Development Environment)

開發環境專為開發者設計，支援程式碼熱重載，方便快速迭代。

*   **特點**：
    *   `web-app` 和 `ai-worker` 的原始碼會掛載到容器中，修改程式碼後無需重新建置映像檔即可生效 (部分服務可能需要重啟容器)。
    *   直接暴露 `web-app` (5000)、`llm-service` (8001)、`stt-service` (8002)、`tts-service` (8003) 的埠，方便直接測試。
    *   資料庫和快取服務的資料會持久化到本地的 Docker Volume 中，但方便清理。

*   **啟動所有服務**：

    ```bash
docker-compose -f docker-compose.dev.yml up --build -d
    ```
    *   `--build`: 確保在啟動前重新建置所有服務的 Docker 映像檔。
    *   `-d`: 在背景模式下運行容器。

*   **常用指令**：
    *   **查看服務狀態**：
        ```bash
docker-compose -f docker-compose.dev.yml ps
        ```
    *   **查看服務日誌**：
        ```bash
docker-compose -f docker-compose.dev.yml logs -f <service_name>
        # 範例：docker-compose -f docker-compose.dev.yml logs -f web-app
        ```
    *   **停止所有服務**：
        ```bash
docker-compose -f docker-compose.dev.yml down
        ```
    *   **停止並移除所有容器、網路和 Volume (會清除資料)**：
        ```bash
docker-compose -f docker-compose.dev.yml down -v
        ```
    *   **進入容器內部**：
        ```bash
docker-compose -f docker-compose.dev.yml exec <service_name> bash
        # 範例：docker-compose -f docker-compose.dev.yml exec web-app bash
        ```

*   **存取服務**：
    *   **Web App (API)**: `http://localhost:5000`
    *   **Swagger UI**: `http://localhost:5000/apidocs/`
    *   **PostgreSQL**: `localhost:15432` (使用者/密碼/DB 名稱請參考 `.env`)
    *   **Redis**: `localhost:6379`
    *   **RabbitMQ Management UI**: `http://localhost:15672` (預設使用者/密碼: guest/guest)
    *   **MinIO Console**: `http://localhost:9001` (預設使用者/密碼: minioadmin/minioadmin)
    *   **LLM Service**: `http://localhost:8001`
    *   **STT Service**: `http://localhost:8002`
    *   **TTS Service**: `http://localhost:8003`

### 2. 生產環境 (Production Environment)

生產環境配置旨在提供穩定、高效和安全的運行環境。

*   **特點**：
    *   所有服務的程式碼都已內建於 Docker 映像檔中，不進行原始碼掛載。
    *   透過 Nginx 作為反向代理和負載平衡器，統一處理所有外部請求 (預設監聽 80 埠)。
    *   資料庫和儲存服務的資料會持久化到具名的 Docker Volume 中，確保資料安全。
    *   RabbitMQ 和 MinIO 的管理介面埠僅在內部網路可達，或透過 Nginx 代理。

*   **啟動所有服務**：

    ```bash
docker-compose -f docker-compose.prod.yml up --build -d
    ```
    *   **重要**：首次部署或更新程式碼後，務必執行 `--build` 以確保使用最新的映像檔。

*   **常用指令**：
    *   **查看服務狀態**：
        ```bash
docker-compose -f docker-compose.prod.yml ps
        ```
    *   **查看服務日誌**：
        ```bash
docker-compose -f docker-compose.prod.yml logs -f <service_name>
        # 範例：docker-compose -f docker-compose.prod.yml logs -f web-app
        ```
    *   **停止所有服務**：
        ```bash
docker-compose -f docker-compose.prod.yml down
        ```
    *   **停止並移除所有容器、網路 (不會清除資料 Volume)**：
        ```bash
docker-compose -f docker-compose.prod.yml down
        ```
    *   **停止並移除所有容器、網路和 Volume (會清除所有資料，請謹慎使用！)**：
        ```bash
docker-compose -f docker-compose.prod.yml down -v
        ```

*   **存取服務**：
    *   **Web App (透過 Nginx)**: `http://localhost` (或您的伺服器 IP/域名)
    *   **Swagger UI**: `http://localhost/apidocs/`
    *   **PostgreSQL**: `localhost:15432` (通常僅供內部服務或管理工具存取)
    *   **RabbitMQ Management UI**: `http://localhost:15672` (如果您的 `docker-compose.prod.yml` 暴露了此埠)
    *   **MinIO Console**: `http://localhost:9001` (如果您的 `docker-compose.prod.yml` 暴露了此埠)

## 文件更新原則

*   **架構文件 (`document/架構文件.md`)**: 任何系統架構上的重大變更 (如新增/移除服務、改變服務間通訊方式) 都應在此文件更新。
*   **資料庫文件 (`document/資料庫.md`)**: 資料庫結構 (表、欄位、關聯) 的變更應在此文件更新。
*   **API 文件 (`document/flask_API.md`)**: 任何 API 端點的變更 (路徑、方法、參數、回應格式) 都應在此文件更新，並確保與程式碼中的 Swagger Docstring 同步。
*   **檔案結構 (`document/檔案結構.md`)**: 專案目錄結構的重大調整應在此文件更新。
*   **README.md**: 部署流程、環境設定、常用指令等變更應在此文件更新。

## 常見問題與故障排除

### 1. 容器無法啟動或健康檢查失敗

*   **檢查日誌**：使用 `docker-compose -f <env_file>.yml logs <service_name>` 查看特定服務的日誌，通常錯誤訊息會明確指出問題所在。
*   **埠衝突**：確保主機上沒有其他程式佔用 Docker Compose 配置中暴露的埠 (例如 5000, 80, 15432 等)。
*   **環境變數**：檢查 `.env` 檔案中的環境變數是否正確配置，特別是資料庫連線資訊。
*   **資源不足**：如果您的機器資源 (CPU/記憶體) 較少，部分服務 (尤其是 `llm-service`) 可能會因為資源不足而啟動失敗。嘗試增加 Docker 的資源限制。

### 2. `web-app` 無法連接到資料庫或 Redis

*   **服務名稱**：在 Docker Compose 網路中，服務之間應使用服務名稱 (例如 `postgres`, `redis`) 進行通訊，而不是 `localhost` 或 `127.0.0.1`。
*   **健康檢查**：確認 `postgres` 和 `redis` 服務的健康檢查狀態是否為 `healthy`。如果不是，`web-app` 可能會因為依賴服務未就緒而啟動失敗。

### 3. `ai-worker` 無法連接到 AI 微服務

*   **服務名稱**：確保 `ai-worker` 的環境變數中，AI 微服務的 URL 使用了正確的服務名稱 (例如 `http://llm-service:8000`)。
*   **服務啟動**：確認所有 AI 微服務 (`llm-service`, `stt-service`, `tts-service`) 都已成功啟動並運行。

### 4. `web-app` 熱重載未生效 (開發環境)

*   **Volume 掛載**：確認 `docker-compose.dev.yml` 中 `web-app` 服務的 `volumes` 配置是否正確，確保本地程式碼目錄已正確掛載到容器內部。
    ```yaml
    volumes:
      - ./services/web-app/app:/app/app
    ```
*   **FLASK_ENV**：確認 `FLASK_ENV` 環境變數是否設定為 `development`。

### 5. 清理 Docker 資源

如果您遇到不明問題，或需要徹底清理環境重新開始，可以使用以下命令：

```bash
docker-compose -f docker-compose.dev.yml down -v # 清理開發環境所有資源
docker-compose -f docker-compose.prod.yml down -v # 清理生產環境所有資源 (謹慎！會刪除資料)

docker system prune -a # 清理所有停止的容器、未使用的網路、懸掛的映像檔和建置快取 (會刪除所有 Docker 相關資料，請謹慎使用！)
```

## 貢獻指南

歡迎對本專案做出貢獻！請遵循以下步驟：

1.  Fork 本專案。
2.  建立新的功能分支 (`git checkout -b feature/your-feature-name`)。
3.  提交您的變更 (`git commit -am 'feat: Add new feature'`)。
4.  推送到遠端分支 (`git push origin feature/your-feature-name`)。
5.  建立 Pull Request。

在提交 Pull Request 之前，請確保您的程式碼符合專案的風格指南，並且所有測試都已通過。
