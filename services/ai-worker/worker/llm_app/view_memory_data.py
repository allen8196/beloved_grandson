#!/usr/bin/env python3
"""
記憶資料管理工具 - 詳細視覺化版
持續運行，僅支援 Ctrl+C 退出
支援完整內容查看，解決截斷問題
"""

import json
import os
import time

import redis
from pymilvus import Collection, connections

# 載入環境變數
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# 連接設定
MEM_COLLECTION = "user_memory"


def get_redis_client():
    """簡單的 Redis 連接，嘗試不同的連接方式"""
    redis_configs = [
        {"host": "localhost", "port": 6379},
        {"host": "redis", "port": 6379},
        {"host": "127.0.0.1", "port": 6379},
    ]

    for config in redis_configs:
        try:
            print(f"🔗 嘗試連接 Redis: {config['host']}:{config['port']}")
            client = redis.Redis(
                host=config["host"], port=config["port"], decode_responses=True
            )
            client.ping()
            print(f"✅ Redis 連接成功: {config['host']}:{config['port']}")
            return client
        except Exception as e:
            print(f"❌ 連接失敗: {e}")
            continue

    raise Exception("無法連接到 Redis，請檢查 Redis 服務是否啟動")


def connect_milvus():
    """簡單的 Milvus 連接，嘗試不同的連接方式"""
    milvus_configs = [
        {"host": "localhost", "port": 19530},
        {"host": "milvus", "port": 19530},
        {"host": "127.0.0.1", "port": 19530},
    ]

    for config in milvus_configs:
        try:
            print(f"🔗 嘗試連接 Milvus: {config['host']}:{config['port']}")
            connections.connect(
                alias="default", host=config["host"], port=config["port"]
            )
            print(f"✅ Milvus 連接成功: {config['host']}:{config['port']}")
            return
        except Exception as e:
            print(f"❌ 連接失敗: {e}")
            continue

    raise Exception("無法連接到 Milvus，請檢查 Milvus 服務是否啟動")


def show_help():
    """顯示幫助訊息"""
    print("\n" + "=" * 80)
    print("🎯 指令列表:")
    print("  📊 Milvus 資料:")
    print("    'm' / 'milvus'     - 查看簡要列表")
    print("    'md' / 'detail'    - 查看詳細內容（完整文本）")
    print("    'mu {user_id}'     - 查看特定用戶記憶")
    print("  💾 Redis 資料:")
    print("    'r' / 'redis'      - 查看簡要列表")
    print("    'rd' / 'rdetail'   - 查看詳細內容（完整值）")
    print("    'ru {user_id}'     - 查看特定用戶 Redis 資料")
    print("  👥 用戶管理:")
    print("    'u' / 'users'      - 查看用戶列表")
    print("    'd {user_id}'      - 刪除用戶資料")
    print("  🖥️  系統:")
    print("    's' / 'status'     - 系統概覽")
    print("    'c' / 'clear'      - 清空畫面")
    print("    'h' / 'help'       - 顯示幫助")
    print("=" * 80)


def view_milvus_simple(collection):
    """查看 Milvus 簡要資料"""
    print("\n🧠 Milvus user_memory 資料（簡要模式）:")
    print("=" * 80)

    results = collection.query(
        expr="user_id != ''",
        output_fields=["user_id", "updated_at", "text"],
        limit=50,
    )

    if not results:
        print("📝 沒有資料")
        return

    print(f"📊 總計: {len(results)} 條記錄")
    print("-" * 80)

    for i, record in enumerate(results, 1):
        user_id = record.get("user_id", "N/A")
        timestamp = record.get("updated_at", 0)
        text = record.get("text", "N/A")

        if timestamp:
            time_str = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(timestamp / 1000)
            )
        else:
            time_str = "N/A"

        if len(text) > 80:
            text = text[:80] + "..."

        print(f"{i:2d}. 👤 {user_id:<15} ⏰ {time_str}")
        print(f"    💭 {text}")
        print("-" * 40)


def view_milvus_detail(collection):
    """查看 Milvus 詳細資料"""
    print("\n🧠 Milvus user_memory 資料（詳細模式）:")
    print("=" * 100)

    results = collection.query(
        expr="user_id != ''",
        output_fields=["id", "user_id", "updated_at", "text"],
        limit=20,
    )

    if not results:
        print("📝 沒有資料")
        return

    print(f"📊 顯示: {len(results)} 條記錄（詳細內容）")
    print("=" * 100)

    for i, record in enumerate(results, 1):
        record_id = record.get("id", "N/A")
        user_id = record.get("user_id", "N/A")
        timestamp = record.get("updated_at", 0)
        text = record.get("text", "N/A")

        if timestamp:
            time_str = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(timestamp / 1000)
            )
        else:
            time_str = "N/A"

        print(f"📝 記錄 #{i} (ID: {record_id})")
        print(f"👤 用戶: {user_id}")
        print(f"⏰ 時間: {time_str}")
        print(f"💭 完整內容:")
        print("─" * 60)

        if text and text != "N/A":
            lines = [text[j : j + 60] for j in range(0, len(text), 60)]
            for line in lines:
                print(f"   {line}")
        else:
            print("   (空內容)")

        print("─" * 60)
        print()


def view_milvus_user(collection, user_id):
    """查看特定用戶的 Milvus 資料"""
    print(f"\n🧠 用戶 '{user_id}' 的 Milvus 記憶:")
    print("=" * 80)

    results = collection.query(
        expr=f'user_id == "{user_id}"',
        output_fields=["id", "updated_at", "text"],
        limit=100,
    )

    if not results:
        print(f"📝 用戶 '{user_id}' 沒有記憶資料")
        return

    print(f"📊 找到 {len(results)} 條記憶")
    print("-" * 80)

    for i, record in enumerate(results, 1):
        record_id = record.get("id", "N/A")
        timestamp = record.get("updated_at", 0)
        text = record.get("text", "N/A")

        if timestamp:
            time_str = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(timestamp / 1000)
            )
        else:
            time_str = "N/A"

        print(f"📝 記憶 #{i} (ID: {record_id})")
        print(f"⏰ 時間: {time_str}")
        print(f"💭 內容:")

        if text and text != "N/A":
            lines = [text[j : j + 70] for j in range(0, len(text), 70)]
            for line in lines:
                print(f"   {line}")
        else:
            print("   (空內容)")

        print("-" * 40)


def view_redis_simple(redis_client):
    """查看 Redis 簡要資料"""
    print("\n💾 Redis 資料（簡要模式）:")
    print("=" * 80)

    patterns = ["session:*", "audio:*", "processed:*", "lock:*", "alerts:stream"]
    all_keys = set()

    for pattern in patterns:
        keys = redis_client.keys(pattern)
        all_keys.update(keys)

    if not all_keys:
        print("📝 沒有資料")
        return

    key_groups = {
        "📋 會話資料": [],
        "🎵 音頻資料": [],
        "✅ 已處理": [],
        "🔒 鎖定": [],
        "⚠️ 警報": [],
        "🔧 其他": [],
    }

    for key in sorted(all_keys):
        if key.startswith("session:"):
            key_groups["📋 會話資料"].append(key)
        elif key.startswith("audio:"):
            key_groups["🎵 音頻資料"].append(key)
        elif key.startswith("processed:"):
            key_groups["✅ 已處理"].append(key)
        elif key.startswith("lock:"):
            key_groups["🔒 鎖定"].append(key)
        elif "alerts" in key:
            key_groups["⚠️ 警報"].append(key)
        else:
            key_groups["🔧 其他"].append(key)

    for group_name, keys in key_groups.items():
        if not keys:
            continue

        print(f"\n{group_name} ({len(keys)} 項):")
        print("-" * 60)

        for i, key in enumerate(keys[:10], 1):
            try:
                data_type = redis_client.type(key)
                if data_type == "string":
                    value = redis_client.get(key)
                    if len(value) > 40:
                        value = value[:40] + "..."
                    print(f"  {i:2d}. {key:<35} | {value}")
                elif data_type == "list":
                    length = redis_client.llen(key)
                    print(f"  {i:2d}. {key:<35} | (清單: {length} 項)")
                elif data_type == "stream":
                    try:
                        info = redis_client.xinfo_stream(key)
                        length = info.get("length", 0)
                        print(f"  {i:2d}. {key:<35} | (串流: {length} 條)")
                    except:
                        print(f"  {i:2d}. {key:<35} | (串流)")
                else:
                    print(f"  {i:2d}. {key:<35} | ({data_type})")
            except Exception as e:
                print(f"  {i:2d}. {key:<35} | 錯誤: {e}")

        if len(keys) > 10:
            print(f"  ... 還有 {len(keys) - 10} 個項目")


def view_redis_detail(redis_client):
    """查看 Redis 詳細資料"""
    print("\n💾 Redis 資料（詳細模式）:")
    print("=" * 100)

    patterns = ["session:*", "audio:*", "processed:*", "alerts:stream"]
    all_keys = set()

    for pattern in patterns:
        keys = redis_client.keys(pattern)
        all_keys.update(keys)

    if not all_keys:
        print("📝 沒有資料")
        return

    print(f"📊 顯示前 15 個鍵值的詳細內容:")
    print("=" * 100)

    for i, key in enumerate(sorted(all_keys)[:15], 1):
        try:
            data_type = redis_client.type(key)
            print(f"\n🔑 鍵值 #{i}: {key}")
            print(f"📝 類型: {data_type}")

            if data_type == "string":
                value = redis_client.get(key)
                print(f"💭 內容:")
                print("─" * 80)
                if value:
                    try:
                        parsed = json.loads(value)
                        print(json.dumps(parsed, ensure_ascii=False, indent=2))
                    except:
                        lines = [value[j : j + 70] for j in range(0, len(value), 70)]
                        for line in lines:
                            print(f"   {line}")
                else:
                    print("   (空值)")

            elif data_type == "list":
                length = redis_client.llen(key)
                print(f"📝 清單長度: {length}")
                if length > 0:
                    items = redis_client.lrange(key, 0, 4)
                    print(f"💭 內容（前 5 項）:")
                    print("─" * 80)
                    for idx, item in enumerate(items):
                        print(f"   [{idx}] {item}")
                    if length > 5:
                        print(f"   ... 還有 {length - 5} 項")

            elif data_type == "stream":
                try:
                    info = redis_client.xinfo_stream(key)
                    length = info.get("length", 0)
                    print(f"📝 串流長度: {length}")
                    if length > 0:
                        entries = redis_client.xrevrange(key, count=3)
                        print(f"💭 最新 3 條記錄:")
                        print("─" * 80)
                        for entry_id, fields in entries:
                            print(f"   ID: {entry_id}")
                            for field, value in fields.items():
                                print(f"     {field}: {value}")
                            print("   " + "-" * 40)
                except Exception as e:
                    print(f"   無法讀取串流: {e}")

            print("─" * 80)

        except Exception as e:
            print(f"❌ 讀取錯誤: {e}")
            print("─" * 80)


def view_redis_user(redis_client, user_id):
    """查看特定用戶的 Redis 資料"""
    print(f"\n💾 用戶 '{user_id}' 的 Redis 資料:")
    print("=" * 80)

    patterns = [f"session:{user_id}:*", f"audio:{user_id}:*", f"processed:{user_id}:*"]

    user_keys = set()
    for pattern in patterns:
        keys = redis_client.keys(pattern)
        user_keys.update(keys)

    if not user_keys:
        print(f"📝 用戶 '{user_id}' 沒有 Redis 資料")
        return

    print(f"📊 找到 {len(user_keys)} 個鍵值")
    print("-" * 80)

    for i, key in enumerate(sorted(user_keys), 1):
        try:
            data_type = redis_client.type(key)
            print(f"\n🔑 {i}. {key}")
            print(f"📝 類型: {data_type}")

            if data_type == "string":
                value = redis_client.get(key)
                print(f"💭 內容:")
                if value:
                    try:
                        parsed = json.loads(value)
                        print(json.dumps(parsed, ensure_ascii=False, indent=2))
                    except:
                        lines = [value[j : j + 60] for j in range(0, len(value), 60)]
                        for line in lines:
                            print(f"   {line}")
                else:
                    print("   (空值)")

            elif data_type == "list":
                length = redis_client.llen(key)
                print(f"💭 清單 ({length} 項):")
                if length > 0:
                    items = redis_client.lrange(key, 0, 2)
                    for idx, item in enumerate(items):
                        print(f"   [{idx}] {item}")
                    if length > 3:
                        print(f"   ... 還有 {length - 3} 項")

            print("-" * 40)

        except Exception as e:
            print(f"❌ 讀取錯誤: {e}")
            print("-" * 40)


def view_users(collection, redis_client):
    """查看用戶列表"""
    print("\n👥 用戶列表:")
    print("-" * 50)

    # 從 Milvus 獲取用戶
    milvus_users = set()
    try:
        results = collection.query(
            expr="user_id != ''", output_fields=["user_id"], limit=1000
        )
        milvus_users = set(r["user_id"] for r in results)
    except:
        pass

    # 從 Redis 獲取用戶
    redis_users = set()
    try:
        for pattern in ["session:*", "audio:*"]:
            keys = redis_client.keys(pattern)
            for key in keys:
                parts = key.split(":")
                if len(parts) >= 2:
                    redis_users.add(parts[1])
    except:
        pass

    all_users = milvus_users | redis_users

    if not all_users:
        print("📝 沒有用戶")
        return

    for i, user in enumerate(sorted(all_users), 1):
        sources = []
        if user in milvus_users:
            sources.append("Milvus")
        if user in redis_users:
            sources.append("Redis")
        print(f"{i:2d}. {user:<20} ({', '.join(sources)})")


def delete_user_data(collection, redis_client, user_id):
    """刪除用戶資料"""
    print(f"\n🗑️  刪除用戶 '{user_id}' 的資料...")

    # 刪除 Milvus 資料
    try:
        results = collection.query(
            expr=f'user_id == "{user_id}"',
            output_fields=["id"],
            limit=10000,
        )

        if results:
            ids_to_delete = [r["id"] for r in results]
            collection.delete(expr=f"id in {ids_to_delete}")
            collection.flush()
            print(f"✅ 已刪除 {len(ids_to_delete)} 條 Milvus 記錄")
        else:
            print("📝 Milvus 中沒有該用戶資料")
    except Exception as e:
        print(f"❌ 刪除 Milvus 資料失敗: {e}")

    # 刪除 Redis 資料
    try:
        patterns = [
            f"session:{user_id}:*",
            f"audio:{user_id}:*",
            f"processed:{user_id}:*",
        ]
        deleted_count = 0

        for pattern in patterns:
            keys = redis_client.keys(pattern)
            if keys:
                deleted_count += redis_client.delete(*keys)

        if deleted_count > 0:
            print(f"✅ 已刪除 {deleted_count} 個 Redis 項目")
        else:
            print("📝 Redis 中沒有該用戶資料")
    except Exception as e:
        print(f"❌ 刪除 Redis 資料失敗: {e}")


def view_status(collection, redis_client):
    """查看系統概覽"""
    print("\n🖥️  系統概覽:")
    print("-" * 50)

    # Milvus 統計
    try:
        total_entities = collection.num_entities
        print(f"🧠 Milvus 總記錄數: {total_entities}")

        results = collection.query(
            expr="user_id != ''", output_fields=["user_id"], limit=1000
        )
        unique_users = set(r["user_id"] for r in results)
        print(f"👥 Milvus 用戶數: {len(unique_users)}")
    except Exception as e:
        print(f"❌ Milvus 統計失敗: {e}")

    # Redis 統計
    try:
        session_count = len(redis_client.keys("session:*"))
        audio_count = len(redis_client.keys("audio:*"))
        print(f"💾 Redis 會話數: {session_count}")
        print(f"🎵 Redis 音頻數: {audio_count}")
    except Exception as e:
        print(f"❌ Redis 統計失敗: {e}")


def main():
    """主程式 - 保持連線直到 Ctrl+C"""
    print("🔍 記憶資料管理工具 - 詳細視覺化版")
    print("=" * 60)
    print("💡 使用 Ctrl+C 退出")
    print("=" * 60)

    # 連接 Milvus
    connect_milvus()
    collection = Collection(MEM_COLLECTION)
    collection.load()
    print(f"✅ Milvus {MEM_COLLECTION} collection 已載入")

    # 連接 Redis
    redis_client = get_redis_client()

    # 顯示幫助
    show_help()

    while True:
        try:
            cmd = input("\n👉 請輸入指令: ").strip().lower()

            if not cmd:
                continue

            # Milvus 查看指令
            if cmd in ["m", "milvus"]:
                view_milvus_simple(collection)
            elif cmd in ["md", "detail"]:
                view_milvus_detail(collection)
            elif cmd.startswith("mu "):
                user_id = cmd[3:].strip()
                if user_id:
                    view_milvus_user(collection, user_id)
                else:
                    print("❌ 請指定用戶ID: mu {user_id}")

            # Redis 查看指令
            elif cmd in ["r", "redis"]:
                view_redis_simple(redis_client)
            elif cmd in ["rd", "rdetail"]:
                view_redis_detail(redis_client)
            elif cmd.startswith("ru "):
                user_id = cmd[3:].strip()
                if user_id:
                    view_redis_user(redis_client, user_id)
                else:
                    print("❌ 請指定用戶ID: ru {user_id}")

            # 用戶管理指令
            elif cmd in ["u", "users"]:
                view_users(collection, redis_client)
            elif cmd.startswith("d "):
                user_id = cmd[2:].strip()
                if user_id:
                    delete_user_data(collection, redis_client, user_id)
                else:
                    print("❌ 請指定用戶ID: d {user_id}")

            # 系統指令
            elif cmd in ["s", "status"]:
                view_status(collection, redis_client)
            elif cmd in ["c", "clear"]:
                os.system("cls" if os.name == "nt" else "clear")
                print("🔍 記憶資料管理工具 - 詳細視覺化版")
                print("💡 使用 Ctrl+C 退出")
                show_help()
            elif cmd in ["h", "help"]:
                show_help()

            else:
                print("❓ 未知指令，可用指令:")
                print("📊 Milvus: m(簡要) | md(詳細) | mu {user_id}(用戶)")
                print("💾 Redis: r(簡要) | rd(詳細) | ru {user_id}(用戶)")
                print("👥 用戶: u(列表) | d {user_id}(刪除)")
                print("🖥️  系統: s(概覽) | c(清空) | h(幫助)")
                print("💡 提示：使用 'md' 或 'rd' 查看完整內容！")

        except KeyboardInterrupt:
            print("\n\n👋 收到 Ctrl+C，程式結束！")
            break
        except Exception as e:
            print(f"❌ 發生錯誤: {e}")
            print("程式繼續運行...")


if __name__ == "__main__":
    main()
