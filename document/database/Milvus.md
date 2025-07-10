# Milvus 向量資料庫 - 技術文件

## 1. 設計宗旨與核心功能

### 1.1. 系統定位

在「Beloved Grandson」專案的微服務架構中，Milvus 扮演著 **AI 的長期記憶與知識庫** 的核心角色。它是一個專為高效能相似度搜尋而設計的向量資料庫，主要服務於 `llm-service`。

### 1.2. 核心功能

-   **支援 RAG (Retrieval-Augmented Generation)**: Milvus 的主要目的是儲存大量外部知識文件（如：常見問答、專業領域資料、故事集等）的向量化表示。當 `llm-service` 需要回答特定問題時，它會先在 Milvus 中進行語意檢索，找出最相關的知識片段，再將這些片段作為上下文提供給大型語言模型（TAIDE），從而生成更準確、更具深度的回答。
-   **語意搜尋**: 允許系統超越關鍵字匹配，進行基於語意相似度的搜尋。例如，使用者詢問「如何保持健康？」，系統可以從 Milvus 中找到與「健康生活方式」、「均衡飲食」、「規律運動」相關的知識。
-   **解耦知識與模型**: 將外部知識儲存在 Milvus 中，使得知識庫的更新與 LLM 模型的迭代可以獨立進行。我們可以在不重新訓練核心語言模型的情況下，隨時擴充、更新或刪除知識庫內容。

---

## 2. 資料模型與結構

為了有效地組織 RAG 的知識，我們在 Milvus 中設計了以下的資料結構。

### 2.1. Collection: `knowledge_base`

我們定義一個名為 `knowledge_base` 的 Collection 來儲存所有用於 RAG 的向量化知識。

### 2.2. 欄位 (Fields) 定義

`knowledge_base` Collection 包含以下欄位：

| 欄位名稱      | 資料類型      | 維度 (Dimension) | 描述                                                                 | 索引/主鍵 |
| :------------ | :------------ | :--------------- | :------------------------------------------------------------------- | :-------- |
| `chunk_id`    | `Int64`       | -                | 資料片段的唯一識別碼。                                               | 主鍵 (PK) |
| `source`      | `VarChar`     | -                | 知識來源的識別符，例如檔名 (`faq.pdf`) 或類別 (`medical_info`)。     |           |
| `original_text` | `VarChar`     | -                | 向量化前的原始文字片段，用於除錯或直接顯示給使用者。                 |           |
| `embedding`   | `FloatVector` | 768              | 文字片段的向量表示。維度需與 `llm-service` 使用的嵌入模型保持一致。 | 向量索引  |

**設計說明**:
- `chunk_id` 作為主鍵，確保每個文字片段的唯一性。
- `source` 欄位至關重要，它允許我們在查詢時進行元資料過濾 (Metadata Filtering)，例如只在特定的文件中搜尋，大幅提升查詢效率與精準度。
- `embedding` 是核心的向量欄位，其 768 維度是目前主流嵌入模型的常見選擇，未來可根據模型更換進行調整。

---

## 3. 索引策略與選擇考量

為了在查詢效能與資源消耗之間取得平衡，我們為 `embedding` 欄位選擇了合適的索引策略。

### 3.1. 推薦索引類型: `HNSW` (Hierarchical Navigable Small World)

-   **選擇原因**:
    -   **高效能與高召回率**: HNSW 是一種基於圖的索引，能夠在極大規模的資料集上提供非常快速且準確的近鄰搜尋，非常適合需要即時回應的對話系統。
    -   **成熟穩定**: HNSW 是目前業界最主流且經過驗證的向量索引之一，社群支援廣泛。
-   **索引參數 (`index_params`)**:
    -   `M`: 32 (控制圖的複雜度，較高的值能提升準確度，但會增加記憶體消耗與索引建構時間)。
    -   `efConstruction`: 256 (索引建構時的搜尋廣度，較高的值會建構出更優質的索引，但耗時更長)。
-   **搜尋參數 (`search_params`)**:
    -   `ef`: 128 (查詢時的搜尋廣度，較高的值能提升召回率，但會增加查詢延遲)。

### 3.2. 備選索引類型: `IVF_FLAT`

-   **適用場景**: 如果未來系統面臨極大的記憶體限制，或索引建構速度成為瓶頸時，可以考慮使用 `IVF_FLAT`。
-   **優缺點**:
    -   **優點**: 索引建構速度快，記憶體佔用相對較小。
    -   **缺點**: 查詢效能與準確度通常略遜於 HNSW，且需要仔細調整 `nprobe` 參數才能達到理想效果。

---

## 4. 查詢優化指南

為了確保 `llm-service` 能夠從 Milvus 快速獲取所需資訊，建議遵循以下最佳實踐：

1.  **優先使用元資料過濾**: 在進行向量搜尋前，盡可能利用 `source` 欄位進行過濾。這可以將搜尋範圍縮小到一個或幾個特定的文件，極大地減少計算量。
    ```python
    # 範例：僅在 'faq.pdf' 中搜尋
    expr = "source == 'faq.pdf'"
    results = collection.search(
        data=[query_vector],
        anns_field="embedding",
        param=search_params,
        limit=5,
        expr=expr
    )
    ```

2.  **調整 `limit` 與 `ef` 參數**:
    -   `limit` (回傳結果數量): 只請求必要數量的結果 (Top-K)。通常 RAG 應用中 K 值設為 3 到 5 即可取得良好效果。
    -   `ef` (HNSW 搜尋廣度): 在可接受的延遲範圍內，適度���高 `ef` 值可以提升搜尋的召回率。建議從 64 或 128 開始測試。

3.  **負載均衡與連線管理**:
    -   `llm-service` 應使用連線池 (Connection Pooling) 來管理與 Milvus 的連線，避免頻繁建立和銷毀連線所帶來的開銷。
    -   如果未來查詢量巨大，可以考慮部署多個 Milvus 查詢節點 (Query Node) 並在 `llm-service` 前端進行負載均衡。

4.  **資料分割 (Partitioning)**: 如果單一 Collection 的資料量變得極其龐大（例如超過一億個向量），可以考慮使用 Milvus 的 Partition 功能。將 `knowledge_base` 按照 `source` 或其他高基數的元資料進行分割，可以將查詢限定在特定分割區內，進一步提升效能。

---

## 5. 與現有架構的整合點

Milvus 與系統其他元件的協同運作方式如下：

### 5.1. 資料寫入 (Ingestion) - `離線 RAG 資料載入`

-   **觸發點**: 由開發者在本地環境手動執行 `IngestionScript`。
-   **流程**:
    1.  腳本讀取指定的外部文件（如 PDF, TXT, Markdown）。
    2.  將文件內容進行切塊 (Chunking)。
    3.  呼叫嵌入模型（可能封裝在 `llm-service` 或一個獨立服務中）將每個文字塊轉換為向量。
    4.  腳本將 `chunk_id`, `source`, `original_text`, `embedding` 組裝成一條記錄。
    5.  透過 Milvus Python SDK 將記錄插入到 `knowledge_base` Collection 中。

### 5.2. 資料讀取 (Retrieval) - `llm-service`

-   **觸發點**: `ai-worker` 呼叫 `llm-service` 進行對話生成。
-   **流程**:
    1.  `llm-service` 接收到來自 `ai-worker` 的使用者查詢文字。
    2.  `llm-service` 使用相同的嵌入模型，將該查詢文字轉換為一個查詢向量 (`query_vector`)。
    3.  `llm-service` 向 Milvus 的 `knowledge_base` Collection 發起一個 `search` 請求，使用 `query_vector` 尋找最相似的 Top-K 個 `embedding`。
    4.  Milvus 回傳最相似的 K 個結果，包含 `chunk_id` 和 `original_text`。
    5.  `llm-service` 將這 K 個 `original_text` 片段組合成一個豐富的上下文 (Context)。
    6.  最後，將此上下文與原始查詢一起傳遞給 TAIDE 語言模型，生成最終的回覆。

### 5.3. 底層儲存依賴 - `MinIO`

-   根據架構圖，Milvus 本身的持久化儲存依賴於 `MinIO`。所有寫入 Milvus 的向量、索引和元資料變更日誌，最終都會由 Milvus 在背景儲存到 `MinIO` 的 `milvus-data` bucket 中，確保資料的持久性和可恢復性。
