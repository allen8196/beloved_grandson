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
- **描述:** 提交一個包含音訊檔案的對話訊息任務。此端點會立即將任務發布至訊息佇列供 AI Worker 處理，並返回一個唯一的任務 ID。如果未提供 `conversation_id`，AI Worker 將會建立一個全新的對話。
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

### 獲取任務狀態與結果

- **端點:** `GET /api/tasks/{task_id}`
- **方法:** `GET`
- **描述:** 使用 `task_id` 輪詢非同步任務的狀態和結果。客戶端應持續查詢此端點，直到 `status` 變為 `SUCCESS` 或 `FAILURE`。
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
    "audio_output_url": "https://storage.googleapis.com/your-bucket/tts_output/xyz.mp3"
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
      "audio_input_url": "https://storage.googleapis.com/your-bucket/audio_input/abc.wav",
      "created_at": "2023-10-27T10:05:10Z"
    },
    {
      "id": "x1y2z3a4-b5c6-7890-1234-567890defghi",
      "sender_type": "AI",
      "text_content": "天氣晴朗，氣溫攝氏25度。",
      "audio_output_url": "https://storage.googleapis.com/your-bucket/tts_output/xyz.mp3",
      "created_at": "2023-10-27T10:05:15Z"
    }
  ]
}
```
