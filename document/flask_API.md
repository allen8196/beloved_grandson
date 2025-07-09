# Flask API 文件

## 1. 總覽

本文件詳細描述了 Flask Web 應用程式的 API 端點。此 API 負責使用者管理、處理對話任務及檢索任務結果，是客戶端應用程式的主要介面。

身份驗證透過 JWT (JSON Web Tokens) 處理。客戶端在請求受保護的端點時，必須在標頭中包含 `Authorization: Bearer <token>`。

## 2. 使用者管理 (`/api/users`)

用於使用者註冊、登入和個人資料管理的端點。

### 註冊新使用者

- **端點:** `POST /api/users/register`
- **方法:** `POST`
- **描述:** 建立一個新的使用者帳號。
- **請求主體:**

| 參數 | 類型 | 描述 |
| :--- | :--- | :--- |
| `email` | `string` | 使用者的電子郵件地址，必須是唯一的。 |
| `password` | `string` | 使用者的密碼（將會被雜湊）。 |
| `full_name`| `string` | 使用者的全名。 |

- **請求範例:**
```json
{
  "email": "user@example.com",
  "password": "securepassword123",
  "full_name": "Alex Doe"
}
```

- **回應範例 (成功 `201`):**
```json
{
  "id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "email": "user@example.com",
  "full_name": "Alex Doe",
  "created_at": "2023-10-27T10:00:00Z"
}
```

### 使用者登入

- **端點:** `POST /api/users/login`
- **方法:** `POST`
- **描述:** 驗證使用者身份並返回一個 JWT 存取權杖。
- **請求主體:**

| 參數 | 類型 | 描述 |
| :--- | :--- | :--- |
| `email` | `string` | 使用者的電子郵件地址。 |
| `password` | `string` | 使用者的密碼。 |

- **請求範例:**
```json
{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

- **回應範例 (成功 `200`):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

### 獲取目前使用者資料

- **端點:** `GET /api/users/me`
- **方法:** `GET`
- **描述:** 檢索當前已驗證使用者的個人資料。
- **身份驗證:** 需要 (`Bearer Token`)。
- **回應範例 (成功 `200`):**
```json
{
  "id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "email": "user@example.com",
  "full_name": "Alex Doe",
  "created_at": "2023-10-27T10:00:00Z"
}
```

## 3. 對話與任務管理

管理非同步對話任務的提交與查詢。

### 提交對話訊息任務

- **端點:** `POST /api/conversations`
- **方法:** `POST`
- **描述:** 提交一個包含音訊檔案的對話訊息任務。在此流程中，Web App 會先將上傳的 `audio_file` 存入 MinIO 物件儲存，然後將包含 MinIO 內部路徑的任務發布至訊息佇列供 AI Worker 處理，並立即返回一個唯一的任務 ID。如果未提供 `conversation_id`，系統將在任務處理完成後建立一個全新的對話。
- **身份驗證:** 需要 (`Bearer Token`)。
- **請求主體:** `multipart/form-data`

| 參數 | 類型 | 描述 |
| :--- | :--- | :--- |
| `audio_file` | `file` | 使用者輸入的音訊檔案（例如 `.wav`, `.mp3`）。 |
| `conversation_id` | `string` | （可選）現有對話的 ID，用於在該對話中新增訊息。 |

- **回應範例 (成功 `202 Accepted`):**
```json
{
  "task_id": "f1g2h3i4-j5k6-7890-1234-567890lmnpqr"
}
```

### 獲取任務狀態與結果 (備用機制)

- **端點:** `GET /api/tasks/{task_id}`
- **方法:** `GET`
- **描述:** 使用 `task_id` 查詢非同步任務的最終結果。此端點主要作為 WebSocket 連線失敗或中斷時的**備用查詢機制**，不建議用於高頻率輪詢。
- **身份驗證:** 需要 (`Bearer Token`)。
- **URL 參數:**

| 參數 | 類型 | 描述 |
| :--- | :--- | :--- |
| `task_id` | `string` | 任務的 UUID。 |

- **回應範例 (處理中 `200 OK`):**
```json
{
  "status": "PROCESSING",
  "result": null
}
```

- **回應範例 (成功 `200 OK`):**
  當任務成功完成後，`result` 物件會包含處理結果。如果這是一個新建立的對話，`conversation_id` 將會被回傳。
```json
{
  "status": "SUCCESS",
  "result": {
    "conversation_id": "c1d2e3f4-g5h6-7890-1234-567890ijklmn",
    "text_response": "這是對您問題的回答。",
    "audio_output_url": "/media/audio-outputs/xyz.mp3"
  }
}
```

- **回應範例 (失敗 `200 OK`):**
```json
{
  "status": "FAILURE",
  "result": {
    "error_message": "無法處理音訊檔案。"
  }
}
```

### 即時結果通知 (WebSocket)

為了提供即時的任務結果更新，系統採用 WebSocket 協定。客戶端在提交任務後，應使用獲取的 `task_id` 建立一個 WebSocket 連線，以非同步接收最終結果，從而避免了傳統 HTTP 輪詢的延遲與資源浪費。

- **端點:** `ws://<your-server-address>/ws/tasks/{task_id}`
- **描述:** 建立一個與特定任務 (`task_id`) 綁定的 WebSocket 連線。當該任務完成時，伺服器會透過此連線主動推送一次最終結果，然後關閉連線。
- **URL 參數:**

| 參數 | 類型 | 描述 |
| :--- | :--- | :--- |
| `task_id` | `string` | 任務的 UUID，用於識別要監聽的任務。 |

- **流程說明:**
    1.  客戶端 `POST /api/conversations` 並獲得 `task_id`。
    2.  客戶端立即使用此 `task_id` 初始化 WebSocket 連線。
    3.  連線建立後，客戶端進入等待狀態。
    4.  當後端 `AI Worker` 完成任務並將結果傳回 `Web App` 後，`Web App` 會將結果整理成 JSON 格式。
    5.  `Web App` 透過對應的 WebSocket 通道，將 JSON 結果推送給客戶端。
    6.  推送完成後，伺服器會主動關閉該 WebSocket 連線。

- **伺服器推送訊息範例 (成功):**
  伺服器推送的訊息格式與 `GET /api/tasks/{task_id}` 的成功回應格式完全相同。
```json
{
  "status": "SUCCESS",
  "result": {
    "conversation_id": "c1d2e3f4-g5h6-7890-1234-567890ijklmn",
    "text_response": "這是對您問題的回答。",
    "audio_output_url": "/media/audio-outputs/xyz.mp3"
  }
}
```

- **伺服器推送訊息範例 (失敗):**
```json
{
  "status": "FAILURE",
  "result": {
    "error_message": "無法處理音訊檔案。"
  }
}
```

## 4. 對話歷史紀錄

用於檢索已完成並儲存於資料庫中的對話歷史。

### 列出使用者所有對話

- **端點:** `GET /api/conversations`
- **方法:** `GET`
- **描述:** 檢索已驗證使用者的所有對話列表。此端點僅返回對話的摘要資訊。
- **身份驗證:** 需要 (`Bearer Token`)。
- **回應範例 (成功 `200 OK`):**
```json
[
  {
    "id": "c1d2e3f4-g5h6-7890-1234-567890ijklmn",
    "user_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
    "title": "關於天氣的對話",
    "created_at": "2023-10-27T10:05:00Z",
    "updated_at": "2023-10-27T10:15:00Z"
  }
]
```

### 獲取特定對話的完整內容

- **端點:** `GET /api/conversations/{conversation_id}`
- **方法:** `GET`
- **描述:** 檢索單一對話的完整歷史，包含其所有訊息。
- **身份驗證:** 需要 (`Bearer Token`)。
- **URL 參數:**

| 參數 | 類型 | 描述 |
| :--- | :--- | :--- |
| `conversation_id` | `string` | 對話的 UUID。 |

- **回應範例 (成功 `200 OK`):**
```json
{
  "id": "c1d2e3f4-g5h6-7890-1234-567890ijklmn",
  "title": "關於天氣的對話",
  "created_at": "2023-10-27T10:05:00Z",
  "messages": [
    {
      "id": "m1n2o3p4-q5r6-7890-1234-567890stuvwx",
      "sender_type": "USER",
      "text_content": "今天天氣如何？",
      "audio_input_url": "/media/audio-inputs/abc.wav",
      "created_at": "2023-10-27T10:05:10Z"
    },
    {
      "id": "x1y2z3a4-b5c6-7890-1234-567890defghi",
      "sender_type": "AI",
      "text_content": "天氣晴朗，氣溫攝氏25度。",
      "audio_output_url": "/media/audio-outputs/xyz.mp3",
      "created_at": "2023-10-27T10:05:15Z"
    }
  ]
}
```

## 5. Swagger / OpenAPI 支援

為了提升 API 的可用性、可測試性與文件品質，本專案已整合 `flasgger`，提供完整的 Swagger UI 支援。開發人員與前端團隊可透過互動式介面探索、測試所有 API 端點。

- **Swagger UI 存取路徑**: `http://<your-server-address>/apidocs/`
- **OpenAPI 規格檔**: `http://<your-server-address>/apispec_1.json`

### 整合步驟

1.  **安裝依賴**:
    在 `services/web-app/requirements.txt` 中新增 `flasgger`。

    ```
    pip install flasgger
    ```

2.  **初始化 Flasgger**:
    在 `services/web-app/app/__init__.py` 或 `app.py` 中初始化 Flasgger 擴充。

    ```python
    from flask import Flask
    from flasgger import Swagger

    def create_app():
        app = Flask(__name__)
        # ... 其他設定 ...

        # 初始化 Swagger
        Swagger(app)

        # ... 註冊藍圖 ...
        return app
    ```

### 對 API 設計的影響

- **文件即程式碼 (Documentation as Code)**: API 文件（OpenAPI 規格）直接寫在對應端點的 Python docstring 中。這確保了文件與實作永遠同步。
- **契約驅動開發 (Contract-Driven Development)**: 開發者在實作功能前，需先思考並定義 API 的契約（路徑、參數、請求/回應格式、狀態碼）。這有助於前後端並行開發。
- **模型標準化**: 透過 OpenAPI 的 `definitions` (或 `components/schemas`)，我們可以定義標準化的資料模型（DTOs），並在多個端點中重複使用，確保 API 回應的一致性。

### 實用範例

以下範例展示如何在 `users.py` 中為 `GET /api/users/me` 端點撰寫 Swagger 文件。

```python
# services/web-app/app/api/users.py

from flask import Blueprint, jsonify
from flasgger import swag_from

users_bp = Blueprint('users', __name__)

@users_bp.route('/me', methods=['GET'])
def get_current_user():
    """
    獲取目前使用者資料
    這是一個示範端點，用於檢索已驗證使用者的個人資料。
    ---
    tags:
      - User Management
    security:
      - BearerAuth: []
    responses:
      200:
        description: 成功獲取使用者資料。
        schema:
          $ref: '#/definitions/User'
      401:
        description: 未經授權或 Token 無效。
    definitions:
      User:
        type: object
        properties:
          id:
            type: string
            format: uuid
            description: 使用者的唯一識別碼。
            example: "a1b2c3d4-e5f6-7890-1234-567890abcdef"
          email:
            type: string
            format: email
            description: 使用者的電子郵件地址。
            example: "user@example.com"
          full_name:
            type: string
            description: 使用者的全名。
            example: "Alex Doe"
          created_at:
            type: string
            format: date-time
            description: 帳號建立時間。
    """
    # 這裡應有實際的邏輯來獲取使用者
    user_data = {
        "id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
        "email": "user@example.com",
        "full_name": "Alex Doe",
        "created_at": "2023-10-27T10:00:00Z"
    }
    return jsonify(user_data)

```
