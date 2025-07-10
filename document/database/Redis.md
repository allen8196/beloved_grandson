# Redis 資料庫技術文件

本文檔旨在詳細闡述「Beloved Grandson」專案中 Redis 資料庫的設計理念、核心用途、資料模型及操作策略。

## 1. 設計總覽與原則

### 1.1. Redis 在系統中的角色

在「Beloved Grandson」架構中，Redis 作為一個高效能的 **記憶體內資料庫 (In-memory Database)**，扮演著以下幾個關鍵角色：

1.  **即時對話上下文快取 (Real-time Context Cache)**: 為了讓 LLM 能夠理解對話的來龍去脈，系統需要快速存取最近的幾輪對話。將這些即時性強、存取頻繁的對話上下文儲存在 Redis 中，可以極大地降低對後端 MongoDB 的讀取壓力，並提供毫秒級的響應速度。

2.  **使用者會話管理 (Session Management)**: `web-app` 使用 Redis 來儲存使用者的會話 (Session) 資訊。相較於傳統的檔案或資料庫 Session 儲存，Redis 提供了更快的讀寫效能與更簡易的水平擴展能力。

3.  **通用資料快取 (General-purpose Caching)**: 對於系統中其他頻繁讀取但不常變動的資料（例如使用者設定、不常變更的 API 回應等），Redis 可作為一層快取層，減少對主要資料庫 (PostgreSQL) 的請求，提升整體系統效能。

### 1.2. 設計決策

選擇 Redis 的主要理由如下：

-   **極致效能**: 基於記憶體的儲存方式，確保了資料讀寫的低延遲，這對於即時對話等場景至關重要。
-   **豐富的資料結構**: Redis 提供多樣的資料結構（如 Strings, Hashes, Lists），能夠以更高效、更貼近業務邏輯的方式儲存資料。
-   **內建的過期策略**: Redis 原生支援鍵 (Key) 的過期時間 (TTL, Time-To-Live)，完美適用於快取和 Session 管理，無需應用層手動管理過期邏輯。
-   **原子性操作**: Redis 的大部分操作都是原子性的，這簡化了並行場景下的開發複雜度。

## 2. 核心資料模型與應用

為了確保系統的可維護性與擴展性，我們定義了一套清晰的鍵命名規範 (Key Naming Convention)。

**規範**: `[scope]:[object]:[id]`

-   `scope`: 用途範疇，如 `session`, `context`, `cache`。
-   `object`: 儲存的物件類型，如 `user`, `conversation`。
-   `id`: 唯一識別碼。

### 2.1. 即時對話上下文 (Real-time Context)

-   **用途**: 儲存最近 N 筆對話紀錄，供 LLM 快速取用。
-   **資料結構**: `List`
-   **鍵範例**: `context:conversation:CONV_ID_123`
-   **值範例**:
    -   每則訊息被序列化為 JSON 字串後存入 List。
    -   `'{"role": "user", "content": "你好嗎？"}'`
    -   `'{"role": "assistant", "content": "我很好，有什麼可以幫您的嗎？"}'`
-   **操作策略**:
    -   **寫入**: 使用 `LPUSH` 將最新的訊息添加到列表的頭部。
    -   **修剪**: 使用 `LTRIM` 保留固定長度的對話歷史（例如，只保留最近 10 則訊息），防止記憶體無限增長。
    -   **讀取**: 使用 `LRANGE` 一次性讀取所有上下文。

    ```bash
    # 新增一則使用者訊息
    LPUSH context:conversation:CONV_ID_123 '{"role": "user", "content": "今天天氣如何？"}'

    # 維持列表長度為 10
    LTRIM context:conversation:CONV_ID_123 0 9

    # 讀取所有上下文
    LRANGE context:conversation:CONV_ID_123 0 -1
    ```

### 2.2. 使用者會話 (Session)

-   **用途**: 儲存 `web-app` 的使用者登入狀態。
-   **資料結構**: `String` 或 `Hash`
-   **鍵範例**: `session:USER_ID_ABC`
-   **值範例**: 序列化後的 Session 物件。
-   **操作策略**:
    -   使用 `SET` 進行儲存，並透過 `EXPIRE` 或 `SETEX` 設定合理的過期時間（例如 24 小時）。
    -   每次使用者活動時，可透過 `EXPIRE` 重新設定過期時間，實現滑動過期。

    ```bash
    # 設置一個 24 小時後過期的 Session
    SETEX session:USER_ID_ABC 86400 '{"user_id": "USER_ID_ABC", "permissions": ["read", "write"]}'
    ```

### 2.3. API 回應快取 (API Response Cache)

-   **用途**: 快取不常變動的 API GET 請求的回應。
-   **資料結構**: `String`
-   **鍵範例**: `cache:api:/api/users/USER_ID_ABC/profile`
-   **值範例**: API 回應的 JSON 字串。
-   **操作策略**:
    -   使用 `SETEX` 儲存 API 回應，並設定一個較短的過期時間（例如 5 分鐘），以在效能和資料一致性之間取得平衡。

    ```bash
    # 快取使用者個人資料 API 的回應，有效期 300 秒
    SETEX cache:api:/api/users/USER_ID_ABC/profile 300 '{"username": "grandson_lover", "email": "..."}'
    ```

## 3. 關鍵操作策略與效能優化

### 3.1. 快取策略：讀取穿透 (Cache-Aside)

本系統主要採用 **讀取穿透 (Cache-Aside)** 模式來操作快取：

1.  **讀取**:
    -   應用程式先嘗試從 Redis 讀取資料。
    -   如果 Redis 中存在資料（快取命中, Cache Hit），則直接返回。
    -   如果 Redis 中不存在資料（快取未命中, Cache Miss），則從主要資料庫（PostgreSQL/MongoDB）讀取。
    -   讀取成功後，將資料寫入 Redis 快取，並設定過期時間，然後返回給客戶端。

2.  **寫入/更新**:
    -   直接更新主要資料庫。
    -   **然後，從 Redis 中刪除對應的快取鍵**。這種策略稱為「Write-through with cache invalidation」，可以確保資料的一致性，並將快取的回填延遲到下一次讀取時。

### 3.2. 避免 Big Keys

應避免在單一鍵中儲存過大的資料（例如，超過 1MB 的 List 或 Hash），因為這會導致網路延遲增加、阻塞 Redis 單執行緒，甚至引發記憶體分配問題。對於對話歷史，應使用 `LTRIM` 嚴格控制其長度。

## 4. 架構整合

### 4.1. 與 Web-App 的協作

`web-app` 是 Redis 的主要使用者之一。它透過 Redis 進行 Session 管理和 API 回應快取，以提升前端反應速度和使用者體驗。

### 4.2. 與 AI-Worker 的協作

`ai-worker` 在處理對話任務時，會直接從 Redis 的 `context:conversation:*` 鍵中讀取對話上下文，以供 `llm-service` 參考。這避免了對 `mongodb` 的高頻查詢，是保障 AI 即時回應的關鍵。

### 4.3. 監控與維護

開發與維運人員可使用 `redis-cli` 工具進行即時監控與手動操作。

-   **即時監控**:
    ```bash
    redis-cli MONITOR
    ```
-   **查看記憶體使用情況**:
    ```bash
    redis-cli INFO memory
    ```
