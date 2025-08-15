#!/usr/bin/env python3
"""
Milvus (user_memory_v2) + Redis 資料查看與刪除工具
整合自 view_memory_data.py，欄位已切換為 pk
"""

import json
import os
import time

import redis
from pymilvus import Collection, connections

# ==== 環境設定 ====
MEM_COLLECTION = os.getenv("MEMORY_COLLECTION", "user_memory_v2")
MILVUS_HOSTS = [("localhost", 19530), ("milvus", 19530), ("127.0.0.1", 19530)]
REDIS_HOSTS = [("localhost", 6379), ("redis", 6379), ("127.0.0.1", 6379)]


# ==== 連線方法 ====
def get_redis_client():
    for host, port in REDIS_HOSTS:
        try:
            client = redis.Redis(host=host, port=port, decode_responses=True)
            client.ping()
            print(f"✅ Redis 已連線: {host}:{port}")
            return client
        except Exception as e:
            print(f"❌ Redis 連線失敗: {host}:{port} {e}")
    raise RuntimeError("無法連線 Redis")


def connect_milvus():
    for host, port in MILVUS_HOSTS:
        try:
            connections.connect(alias="default", host=host, port=port)
            print(f"✅ Milvus 已連線: {host}:{port}")
            return
        except Exception as e:
            print(f"❌ Milvus 連線失敗: {host}:{port} {e}")
    raise RuntimeError("無法連線 Milvus")


# ==== Milvus 查看 ====
def view_milvus_user(collection, user_id):
    results = collection.query(
        expr=f'user_id == "{user_id}"',
        output_fields=[
            "pk",
            "user_id",
            "type",
            "norm_key",
            "status",
            "updated_at",
            "text",
        ],
        limit=200,
    )
    if not results:
        print(f"📝 無 {user_id} 資料")
        return
    for rec in results:
        ts = rec.get("updated_at", 0)
        tstr = (
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts / 1000))
            if ts
            else "N/A"
        )
        print(
            f"\n📝 pk={rec['pk']} user={rec['user_id']} type={rec['type']} norm_key={rec['norm_key']} status={rec['status']} time={tstr}"
        )
        print(f"💭 {rec['text']}")


def delete_milvus_user(collection, user_id):
    results = collection.query(
        expr=f'user_id == "{user_id}"', output_fields=["pk"], limit=10000
    )
    if not results:
        print("📝 無資料可刪")
        return
    pks = [r["pk"] for r in results]
    collection.delete(expr=f"pk in {pks}")
    collection.flush()
    print(f"✅ 已刪除 {len(pks)} 筆 Milvus 記錄")


# ==== Redis 查看 ====
def view_redis_user(r, user_id):
    patterns = [f"session:{user_id}:*", f"audio:{user_id}:*", f"processed:{user_id}:*"]
    keys = set()
    for pat in patterns:
        keys.update(r.keys(pat))
    if not keys:
        print(f"📝 無 {user_id} Redis 資料")
        return
    for k in sorted(keys):
        dtype = r.type(k)
        print(f"\n🔑 {k} ({dtype})")
        if dtype == "string":
            print(r.get(k))
        elif dtype == "list":
            print(r.lrange(k, 0, -1))
        elif dtype == "stream":
            print(r.xrange(k))
        else:
            print("(未處理類型)")


def delete_redis_user(r, user_id):
    patterns = [f"session:{user_id}:*", f"audio:{user_id}:*", f"processed:{user_id}:*"]
    total = 0
    for pat in patterns:
        ks = r.keys(pat)
        if ks:
            total += r.delete(*ks)
    print(f"✅ 已刪除 {total} 個 Redis 項")


# ==== 主互動 ====
def main():
    connect_milvus()
    coll = Collection(MEM_COLLECTION)
    coll.load()
    r = get_redis_client()
    print(
        "輸入: m <uid> 查看 Milvus | mr <uid> 查看 Redis | d <uid> 刪除兩邊 | exit 離開"
    )
    while True:
        cmd = input("db> ").strip()
        if not cmd:
            continue
        if cmd == "exit":
            break
        parts = cmd.split()
        if parts[0] == "m" and len(parts) > 1:
            view_milvus_user(coll, parts[1])
        elif parts[0] == "mr" and len(parts) > 1:
            view_redis_user(r, parts[1])
        elif parts[0] == "d" and len(parts) > 1:
            delete_milvus_user(coll, parts[1])
            delete_redis_user(r, parts[1])
        else:
            print("未知指令")


if __name__ == "__main__":
    main()
