# -*- coding: utf-8 -*-
# file: toolkits/memory_store.py
import hashlib
import math
import os
import time
from typing import Any, Dict, List

try:
    from pymilvus import (
        Collection,
        CollectionSchema,
        DataType,
        FieldSchema,
        connections,
        utility,
    )
except Exception as e:
    raise RuntimeError(
        "需要 pymilvus，請先安裝並連上 Milvus：pip install pymilvus"
    ) from e

EMBED_DIM = int(os.getenv("EMBED_DIM", 1536))  # text-embedding-3-small = 1536
MILVUS_URI = os.getenv("MILVUS_URI", "http://localhost:19530")
COLL = os.getenv("MEMORY_COLLECTION", "user_memory_v2")

# P1-5: 緩存 collection 以避免重複 load
_cached_collection = None
_collection_loaded = False


def _connect():
    try:
        connections.get_connection("default")
    except Exception:
        connections.connect(alias="default", uri=MILVUS_URI)


def ensure_memory_collection():
    # P1-5: 緩存 collection 以避免重複 load
    global _cached_collection, _collection_loaded
    if _cached_collection and _collection_loaded:
        return _cached_collection

    _connect()
    if utility.has_collection(COLL):
        c = Collection(COLL)
        # P1-7: 若 collection 已存在，回讀 dim，矯正 EMBED_DIM
        try:
            schema = c.schema
            for field in schema.fields:
                if (
                    field.name == "embedding"
                    and hasattr(field, "params")
                    and "dim" in field.params
                ):
                    global EMBED_DIM
                    actual_dim = field.params["dim"]
                    if actual_dim != EMBED_DIM:
                        print(f"⚠️ 矯正 EMBED_DIM: {EMBED_DIM} → {actual_dim}")
                        EMBED_DIM = actual_dim
        except Exception as e:
            print(f"[dim correction error] {e}")

        # 只在需要時才 load
        if not _collection_loaded:
            try:
                c.load()
                _collection_loaded = True
            except Exception:
                pass
        _cached_collection = c
        return c

    # 創建新 collection
    fields = [
        FieldSchema(name="pk", dtype=DataType.INT64, is_primary=True, auto_id=False),
        FieldSchema(name="user_id", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="type", dtype=DataType.VARCHAR, max_length=32),
        FieldSchema(name="norm_key", dtype=DataType.VARCHAR, max_length=128),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=2048),
        FieldSchema(name="importance", dtype=DataType.INT64),
        FieldSchema(name="confidence", dtype=DataType.FLOAT),
        FieldSchema(name="times_seen", dtype=DataType.INT64),
        FieldSchema(
            name="status", dtype=DataType.VARCHAR, max_length=16
        ),  # active/superseded/archived
        FieldSchema(name="source_session_id", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="created_at", dtype=DataType.INT64),
        FieldSchema(name="updated_at", dtype=DataType.INT64),
        FieldSchema(name="last_used_at", dtype=DataType.INT64),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=EMBED_DIM),
    ]
    schema = CollectionSchema(fields, description="Personal long-term memory v2")
    c = Collection(COLL, schema=schema)
    c.create_index(
        field_name="embedding",
        index_params={
            "index_type": "HNSW",
            "metric_type": "COSINE",
            "params": {"M": 16, "efConstruction": 200},
        },
    )
    c.load()
    _cached_collection = c
    _collection_loaded = True
    return c


def _now_ms() -> int:
    return int(time.time() * 1000)


def _pk(user_id: str, type_: str, norm_key: str) -> int:
    h = hashlib.sha1(f"{user_id}|{type_}|{norm_key}".encode()).digest()
    return int.from_bytes(h[:8], "big", signed=False) & ((1 << 63) - 1)


def _recency_weight(updated_at_ms: int, tau_days: int = 45) -> float:
    if not updated_at_ms:
        return 0.0
    delta_days = max(0.0, (time.time() * 1000 - updated_at_ms) / 86400000.0)
    return math.exp(-delta_days / float(tau_days))


def upsert_memory_atoms(user_id: str, atoms: List[Dict[str, Any]]):
    """
    Upsert 記憶原子（同 user_id+type+norm_key 覆寫更新）。
    atoms 需包含：type, norm_key, text, importance, confidence, times_seen, status, source_session_id, embedding
    """
    if not atoms:
        return 0
    c = ensure_memory_collection()
    now = _now_ms()
    rows = {
        "pk": [],
        "user_id": [],
        "type": [],
        "norm_key": [],
        "text": [],
        "importance": [],
        "confidence": [],
        "times_seen": [],
        "status": [],
        "source_session_id": [],
        "created_at": [],
        "updated_at": [],
        "last_used_at": [],
        "embedding": [],
    }
    for a in atoms:
        t = (a.get("type") or "other")[:32]
        nk = (a.get("norm_key") or "").strip()[:128]
        if not nk:
            nk = (
                "auto:"
                + hashlib.sha1((a.get("text", "")[:64]).encode()).hexdigest()[:24]
            )
        pk = _pk(user_id, t, nk)
        rows["pk"].append(pk)
        rows["user_id"].append(user_id)
        rows["type"].append(t)
        rows["norm_key"].append(nk)
        rows["text"].append((a.get("text", "")[:2000]))
        rows["importance"].append(int(a.get("importance", 3)))
        rows["confidence"].append(float(a.get("confidence", 0.7)))
        rows["times_seen"].append(int(a.get("times_seen", 1)))
        rows["status"].append(a.get("status", "active"))
        rows["source_session_id"].append(a.get("source_session_id", ""))
        rows["created_at"].append(int(a.get("created_at", now)))
        rows["updated_at"].append(int(a.get("updated_at", now)))
        rows["last_used_at"].append(int(a.get("last_used_at", now)))
        emb = a.get("embedding") or []
        if not isinstance(emb, list) or len(emb) != EMBED_DIM:
            raise ValueError(f"embedding 維度錯誤，需 {EMBED_DIM}")
        rows["embedding"].append(emb)
    c.upsert(
        [
            rows["pk"],
            rows["user_id"],
            rows["type"],
            rows["norm_key"],
            rows["text"],
            rows["importance"],
            rows["confidence"],
            rows["times_seen"],
            rows["status"],
            rows["source_session_id"],
            rows["created_at"],
            rows["updated_at"],
            rows["last_used_at"],
            rows["embedding"],
        ]
    )
    return len(rows["pk"])


def _score(hit, sim_weight=0.64, tau_days=45):
    sim = float(getattr(hit, "distance", 0.0))  # COSINE：越大越相似
    e = hit.entity
    # P0-2: 使用 last_used_at 而非 updated_at 計算新鮮度
    last_used = int(e.get("last_used_at") or e.get("updated_at") or 0)
    rec = _recency_weight(last_used, tau_days)
    imp = (int(e.get("importance") or 3)) / 5.0
    freq = min(1.0, (int(e.get("times_seen") or 1)) / 5.0)
    return sim_weight * sim + 0.18 * rec + 0.12 * imp + 0.06 * freq


def retrieve_memory_pack(
    user_id: str,
    query_vec: List[float],
    topk: int = 5,
    sim_thr: float = 0.78,
    tau_days: int = 45,
) -> str:
    """
    回傳可直接塞進 prompt 的 Top‑K 記憶包字串。命中不足則回空字串。
    P0-2: 命中後更新 times_seen 與 last_used_at
    """
    c = ensure_memory_collection()
    # P1-5: 移除重複 load，已在 ensure_memory_collection() 中處理
    expr = f'user_id == "{user_id}" and status == "active"'
    res = c.search(
        data=[query_vec],
        anns_field="embedding",
        param={"metric_type": "COSINE", "params": {"ef": 128}},
        limit=min(20, max(5, topk * 4)),
        expr=expr,
        output_fields=["pk"],  # 只取 pk
    )
    hits = [h for h in res[0] if float(getattr(h, "distance", 0.0)) >= sim_thr]
    print(f"🔍 記憶檢索結果: 共找到 {len(res[0])} 筆候選，{len(hits)} 筆超過門檻 {sim_thr}")
    if res[0]:
        similarities = [f'{float(getattr(h, "distance", 0.0)):.3f}' for h in res[0][:3]]
        print(f"📊 相似度分佈: {similarities}")
    if not hits:
        return ""

    # 取全欄位（pk 去重）
    pk_list = list({h.entity.get("pk") for h in hits if h.entity.get("pk") is not None})
    if not pk_list:
        return ""
    # Milvus query 支援 in 語法
    pk_expr = f"pk in [{','.join(str(pk) for pk in pk_list)}]"
    full_rows = c.query(expr=pk_expr, output_fields=None)  # None 取全部欄位
    pk2row = {row["pk"]: row for row in full_rows}

    # 同 norm_key 去重：保留分數最高
    best_by_key = {}
    for h in hits:
        pk = h.entity.get("pk")
        e = pk2row.get(pk)
        if not e:
            continue
        key = f'{e.get("type")}#{e.get("norm_key")}'
        s = _score(h, tau_days=tau_days)
        if (key not in best_by_key) or (s > best_by_key[key]["score"]):
            best_by_key[key] = {"hit": h, "score": s, "row": e}

    picked = sorted(best_by_key.values(), key=lambda x: x["score"], reverse=True)[:topk]

    # P0-2: 更新命中記憶的使用統計
    if picked:
        try:
            now = _now_ms()
            for item in picked:
                e = item["row"]
                pk = e.get("pk")
                if pk:
                    new_times_seen = int(e.get("times_seen", 1)) + 1
                    original_embedding = e.get("embedding")
                    if original_embedding is None:
                        print(
                            f"[warning] missing embedding for pk={pk}, skipping update"
                        )
                        continue
                    c.upsert(
                        [
                            [pk],
                            [e.get("user_id")],
                            [e.get("type")],
                            [e.get("norm_key")],
                            [e.get("text")],
                            [e.get("importance")],
                            [e.get("confidence")],
                            [new_times_seen],
                            [e.get("status")],
                            [e.get("source_session_id")],
                            [e.get("created_at")],
                            [e.get("updated_at")],
                            [now],
                            [original_embedding],
                        ]
                    )
        except Exception as ex:
            print(f"[memory usage update error] {ex}")

    lines = [f'- {x["row"].get("text")} ' for x in picked]
    return "⭐ 個人長期記憶：\n" + "\n".join(lines) if lines else ""
