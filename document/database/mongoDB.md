# MongoDB 資料庫設計 - Beloved Grandson

## 1. 總覽與設計理念

本文件旨在為「Beloved Grandson」專案的 MongoDB 資料庫提供一個清晰、結構化的設計方案。根據系統架構，MongoDB 的核心職責是**儲存對話歷史紀錄**。

我們選擇 MongoDB 是因為其文件導向的特性非常適合儲存半結構化或非結構化的對話資料。其彈性的 Schema 讓我們能夠輕鬆應對未來可能變化的訊息格式。

核心設計理念是採用**內嵌模型 (Embedding)**，將一場完整對話中的所有訊息 (`messages`) 內嵌到單一的 `conversation` 文件中。這種設計有以下優點：
-   **讀取高效**: 只需要一次資料庫查詢，就能取得一場對話的完整上下文，極大地優化了讀取效能。
-   **資料原子性**: 對單一對話的更新（例如新增訊息）可以在一個原子操作中完成。
-   **架構簡潔**: 資料模型直觀，易於理解與維護。

## 2. 集合定義 (Collection Definitions)

本資料庫僅包含一個核心集合：`conversations`。

### 2.1. `conversations` 集合

此集合的每一個文件代表一場完整的使用者與 AI 的對話。

#### 2.1.1. 頂層欄位 (Top-Level Fields)

| 欄位名稱 (Field Name) | 資料型態 (Data Type) | 說明 (Description) |
| :--- | :--- | :--- |
| `_id` | `ObjectId` | MongoDB 自動生成的主鍵，唯一識別每一場對話。 |
| `user_id` | `UUID` | 關聯至 PostgreSQL `users` 表的 `id`。用於識別此對話屬於哪個使用者。**此欄位必須建立索引**。 |
| `title` | `String` | 對話的標題，可由第一則訊息自動生成或由使用者自訂。 |
| `created_at` | `Date` | 對話的建立時間。 |
| `updated_at` | `Date` | 對話的最後更新時間（例如，當有新訊息加入時）。**此欄位建議建立索引**以利排序。 |
| `messages` | `Array<Object>` | 一個包含所有訊息的陣列。詳細結構見下一節。 |

#### 2.1.2. `messages` 內嵌文件結構

`messages` 陣列中的每一個物件代表對話中的一則訊息。

| 欄位名稱 (Field Name) | 資料型態 (Data Type) | 說明 (Description) |
| :--- | :--- | :--- |
| `message_id` | `ObjectId` | 訊息的唯一識別碼，方便對單一訊息進行定位與操作。 |
| `sender_type` | `String` | 訊息發送者。枚舉值: `"user"`, `"ai"`。 |
| `content_type` | `String` | 訊息內容的類型。枚舉值: `"text"`, `"audio"`。 |
| `text_content` | `String` | 當 `content_type` 為 `"text"` 時，儲存文字內容。 |
| `audio_object_key`| `String` | 當 `content_type` 為 `"audio"` 時，儲存音檔在 MinIO 中的物件金鑰 (Object Key)。 |
| `created_at` | `Date` | 訊息的建立時間。 |

#### 2.1.3. 文件範例 (Example Document)

```json
{
  "_id": ObjectId("64c3b1d2e1a2b3c4d5e6f7a8"),
  "user_id": UUID("a1b2c3d4-e5f6-7890-1234-567890abcdef"),
  "title": "今天天氣如何？",
  "created_at": ISODate("2023-07-28T10:00:00Z"),
  "updated_at": ISODate("2023-07-28T10:01:15Z"),
  "messages": [
    {
      "message_id": ObjectId("64c3b1d2e1a2b3c4d5e6f7a9"),
      "sender_type": "user",
      "content_type": "text",
      "text_content": "你好，請問今天台北的天氣如何？",
      "audio_object_key": null,
      "created_at": ISODate("2023-07-28T10:00:00Z")
    },
    {
      "message_id": ObjectId("64c3b1e7e1a2b3c4d5e6f7b0"),
      "sender_type": "ai",
      "content_type": "audio",
      "text_content": null,
      "audio_object_key": "tts-outputs/a1b2c3d4-e5f6-7890-1234-567890abcdef/response.mp3",
      "created_at": ISODate("2023-07-28T10:01:15Z")
    }
  ]
}
```

## 3. 索引策略 (Indexing Strategy)

為了確保高效的查詢效能，建議在 `conversations` 集合上建立以下索引：

-   **使用者查詢索引**:
    -   **欄位**: `user_id`
    -   **用途**: 快速查詢特定使用者發起的所有對話。這是最核心的查詢場景。
    -   **指令**: `db.conversations.createIndex({ "user_id": 1 });`

-   **最近對話排序索引**:
    -   **欄位**: `user_id`, `updated_at`
    -   **用途**: 組合索引，用於高效地查詢某個使用者的對話列表，並按最新活動排序。
    -   **指令**: `db.conversations.createIndex({ "user_id": 1, "updated_at": -1 });`

## 4. 關聯性 (Relationships)

本設計中的關聯性主要體現在 `conversations` 集合與外部 PostgreSQL 資料庫的 `users` 表之間。

-   **類型**: 引用 (Reference)
-   **實現方式**: `conversations` 文件中的 `user_id` 欄位儲存了對應 `users` 表的主鍵 `id`。應用程式層需要負責在需要時，透過此 ID 查詢 PostgreSQL 以獲取完整的使用者資訊。

## 5. 設計決策與考量

-   **內嵌模型的限制**: 雖然內嵌模型效能極佳，但需注意 MongoDB 的**單一文件 16MB 大小限制**。本設計基於一個假設：單場對話的歷史紀錄不會超過此限制。對於絕大多數對話應用而言，這是一個合理的假設。如果未來出現極端長的對話，可能需要考慮將 `messages` 拆分到獨立的集合中（即引用模型）。

-   **資料一致性**: 由於使用者資料和對話資料分屬兩個不同的資料庫系統 (PostgreSQL 和 MongoDB)，應用程式層需要自行處理跨資料庫的資料一致性問題。例如，刪除使用者時，需要同時刪除其在 MongoDB 中的所有對話紀錄。
