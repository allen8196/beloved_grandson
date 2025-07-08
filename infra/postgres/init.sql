-- 啟用 pgcrypto 擴充套件以使用 gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =================================================================
--  Table: users
--  Description: 儲存應用程式的使用者基本資料。
-- =================================================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 為 email 欄位建立索引以加速查詢
CREATE INDEX idx_users_email ON users(email);

COMMENT ON TABLE users IS '儲存應用程式的使用者基本資料。';
COMMENT ON COLUMN users.id IS 'PK (主鍵), default gen_random_uuid()';
COMMENT ON COLUMN users.email IS '用於登入和識別，值需唯一。';
COMMENT ON COLUMN users.hashed_password IS '儲存雜湊後的密碼。';
COMMENT ON COLUMN users.full_name IS '使用者全名。';
COMMENT ON COLUMN users.created_at IS '資料建立時間戳。';
COMMENT ON COLUMN users.updated_at IS '資料最後更新時間戳。';


-- =================================================================
--  Table: conversations
--  Description: 組織多次的對話，代表一個完整的對話主題或會話。
-- =================================================================
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 為 user_id 欄位建立索引以加速查詢
CREATE INDEX idx_conversations_user_id ON conversations(user_id);

COMMENT ON TABLE conversations IS '代表一個完整的對話主題或會話 (Session)。';
COMMENT ON COLUMN conversations.id IS 'PK (主鍵), default gen_random_uuid()';
COMMENT ON COLUMN conversations.user_id IS 'FK -> users(id), 標示此對話屬於哪個使用者。';
COMMENT ON COLUMN conversations.title IS '對話標題，可由第一個問題或 LLM 生成的摘要產生。';
COMMENT ON COLUMN conversations.created_at IS '資料建立時間戳。';
COMMENT ON COLUMN conversations.updated_at IS '資料最後更新時間戳。';


-- =================================================================
--  Table: messages
--  Description: 儲存每一則使用者與 AI 之間的問答訊息。
-- =================================================================
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    sender_type VARCHAR(10) NOT NULL CHECK (sender_type IN ('USER', 'AI')),
    text_content TEXT,
    audio_input_url TEXT,
    audio_output_url TEXT,
    task_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 為 conversation_id 欄位建立索引以加速查詢
CREATE INDEX idx_messages_conversation_id ON messages(conversation_id);

COMMENT ON TABLE messages IS '儲存每一則使用者與 AI 之間的問答訊息。';
COMMENT ON COLUMN messages.id IS 'PK (主鍵), default gen_random_uuid()';
COMMENT ON COLUMN messages.conversation_id IS 'FK -> conversations(id), 標示此訊息屬於哪個對話。';
COMMENT ON COLUMN messages.sender_type IS '標示發送者，例如 ''USER'' 或 ''AI''。';
COMMENT ON COLUMN messages.text_content IS '訊息的文字內容 (STT 轉譯結果或 LLM 回應)。';
COMMENT ON COLUMN messages.audio_input_url IS '(可選) 使用者上傳的原始語音檔案儲存位置 (例如 S3 URL)。';
COMMENT ON COLUMN messages.audio_output_url IS '(可選) TTS 生成的語音檔案儲存位置 (例如 S3 URL)。';
COMMENT ON COLUMN messages.task_id IS '(可選) 關聯到觸發此訊息生成的非同步任務 ID。';
COMMENT ON COLUMN messages.created_at IS '資料建立時間戳。';

-- =================================================================
--  Function: _update_updated_at
--  Description: 自動更新 updated_at 時間戳的觸發器函式。
-- =================================================================
CREATE OR REPLACE FUNCTION _update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 為 users 表格建立觸發器
CREATE TRIGGER update_users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION _update_updated_at();

-- 為 conversations 表格建立觸發器
CREATE TRIGGER update_conversations_updated_at
BEFORE UPDATE ON conversations
FOR EACH ROW
EXECUTE FUNCTION _update_updated_at();
