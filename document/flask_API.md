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

## 3. 對話管理 (`/api/conversations`)

用於建立和管理對話的端點。

### 建立新的對話任務

- **端點:** `POST /api/conversations`
- **方法:** `POST`
- **描述:** 透過提交一個音訊檔案來發起新的對話。這會為 AI Worker 建立一個非同步任務進行處理。
- **身份驗證:** 需要 (`Bearer Token`)。
- **請求主體:** `multipart/form-data`

| 參數 | 類型 | 描述 |
| :--- | :--- | :--- |
| `audio_file` | `file` | 使用者輸入的音訊檔案（例如 `.wav`, `.mp3`）。 |
| `conversation_id` | `string` | （可選）現有對話的 ID，用於繼續對話。如果省略，將會建立一個新的對話。 |

- **回應範例 (成功 `202`):**
```json
{
  "task_id": "f1g2h3i4-j5k6-7890-1234-567890lmnpqr"
}
```

### 列出使用者對話

- **端點:** `GET /api/conversations`
- **方法:** `GET`
- **描述:** 檢索已驗證使用者的所有對話列表。
- **身份驗證:** 需要 (`Bearer Token`)。
- **回應範例 (成功 `200`):**
```json
[
  {
    "id": "c1d2e3f4-g5h6-7890-1234-567890ijklmn",
    "user_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
    "title": "My First Conversation",
    "created_at": "2023-10-27T10:05:00Z",
    "updated_at": "2023-10-27T10:15:00Z"
  }
]
```

### 獲取特定對話

- **端點:** `GET /api/conversations/{conversation_id}`
- **方法:** `GET`
- **描述:** 檢索單一對話，包含其所有訊息。
- **身份驗證:** 需要 (`Bearer Token`)。
- **URL 參數:**

| 參數 | 類型 | 描述 |
| :--- | :--- | :--- |
| `conversation_id` | `string` | 對話的 UUID。 |

- **回應範例 (成功 `200`):**
```json
{
  "id": "c1d2e3f4-g5h6-7890-1234-567890ijklmn",
  "title": "My First Conversation",
  "created_at": "2023-10-27T10:05:00Z",
  "messages": [
    {
      "id": "m1n2o3p4-q5r6-7890-1234-567890stuvwx",
      "sender_type": "USER",
      "text_content": "Hello, what is the weather like today?",
      "audio_input_url": "https://storage.googleapis.com/your-bucket/audio_input/abc.wav",
      "created_at": "2023-10-27T10:05:10Z"
    },
    {
      "id": "x1y2z3a4-b5c6-7890-1234-567890defghi",
      "sender_type": "AI",
      "text_content": "The weather is sunny with a high of 25 degrees Celsius.",
      "audio_output_url": "https://storage.googleapis.com/your-bucket/tts_output/xyz.mp3",
      "created_at": "2023-10-27T10:05:15Z"
    }
  ]
}
```

## 4. 任務狀態 (`/api/tasks`)

用於檢查非同步任務狀態的端點。

### 獲取任務狀態與結果

- **端點:** `GET /api/tasks/{task_id}`
- **方法:** `GET`
- **描述:** 使用從建立對話時獲取的 `task_id`，輪詢非同步 AI 任務的狀態和結果。
- **身份驗證:** 需要 (`Bearer Token`)。
- **URL 參數:**

| 參數 | 類型 | 描述 |
| :--- | :--- | :--- |
| `task_id` | `string` | 任務的 UUID。 |

- **回應範例 (處理中 `200`):**
```json
{
  "status": "PROCESSING",
  "result_type": null,
  "data": null,
  "error_message": null
}
```

- **回應範例 (成功 `200`):**
```json
{
  "status": "SUCCESS",
  "result_type": "tts_audio",
  "data": {
    "text_response": "This is the answer to your question.",
    "audio_output_url": "https://storage.googleapis.com/your-bucket/tts_output/xyz.mp3"
  },
  "error_message": null
}
```

- **回應範例 (失敗 `200`):**
```json
{
  "status": "FAILURE",
  "result_type": null,
  "data": null,
  "error_message": "Failed to process audio file."
}
```
