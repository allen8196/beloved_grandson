# -*- coding: utf-8 -*-
import hashlib
import json
import os
import time
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

import redis
from .profile_store import touch_last_contact_ts
from ..repositories.profile_repository import ProfileRepository

REDIS_TTL_SECONDS = int(os.getenv("REDIS_TTL_SECONDS", 86400))
ALERT_STREAM_KEY = os.getenv("ALERT_STREAM_KEY", "alerts:stream")
ALERT_STREAM_GROUP = os.getenv("ALERT_STREAM_GROUP", "case_mgr")


@lru_cache(maxsize=1)
def get_redis() -> redis.Redis:
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    return redis.Redis.from_url(url, decode_responses=True)


def _touch_ttl(keys: List[str]) -> None:
    if not keys:
        return
    r = get_redis()
    p = r.pipeline()
    for k in keys:
        p.pexpire(k, REDIS_TTL_SECONDS * 1000)
    p.execute()


def ensure_active_state(user_id: str) -> None:
    r = get_redis()
    key = f"session:{user_id}:state"
    r.set(key, "ACTIVE", nx=True)
    _touch_ttl([key])


def try_register_request(user_id: str, request_id: str) -> bool:
    r = get_redis()
    key = f"processed:{user_id}:{request_id}"
    return bool(r.set(key, "1", nx=True, ex=REDIS_TTL_SECONDS))


def make_request_id(user_id: str, text: str, now_ms: Optional[int] = None) -> str:
    if now_ms is None:
        now_ms = int(time.time() * 1000)
    bucket = now_ms // 3000
    return hashlib.sha1(f"{user_id}|{text}|{bucket}".encode()).hexdigest()


def append_round(user_id: str, round_obj: Dict) -> None:
    r = get_redis()
    key = f"session:{user_id}:history"
    r.rpush(key, json.dumps(round_obj, ensure_ascii=False))
    ensure_active_state(user_id)
    _touch_ttl([
        key,
        f"session:{user_id}:summary:text",
        f"session:{user_id}:summary:rounds",
        f"session:{user_id}:alerts",
        f"session:{user_id}:state",
    ])
    ProfileRepository().touch_last_contact_ts(user_id)

# 【新增】主動關懷專用函式
def append_proactive_round(user_id: str, round_obj: Dict) -> None:
    """專門用於寫入主動關懷訊息，但不重置閒置計時器。"""
    r = get_redis()
    key = f"session:{user_id}:history"
    r.rpush(key, json.dumps(round_obj, ensure_ascii=False))


def history_len(user_id: str) -> int:
    return get_redis().llen(f"session:{user_id}:history")


def fetch_unsummarized_tail(user_id: str, k: int = 6) -> List[Dict]:
    r = get_redis()
    cursor = int(r.get(f"session:{user_id}:summary:rounds") or 0)
    items = r.lrange(f"session:{user_id}:history", cursor, -1)
    return [json.loads(x) for x in items[-k:]]


def fetch_all_history(user_id: str) -> List[Dict]:
    r = get_redis()
    items = r.lrange(f"session:{user_id}:history", 0, -1)
    return [json.loads(x) for x in items]


def get_summary(user_id: str) -> Tuple[str, int]:
    r = get_redis()
    text = r.get(f"session:{user_id}:summary:text") or ""
    rounds = int(r.get(f"session:{user_id}:summary:rounds") or 0)
    return text, rounds


def peek_next_n(user_id: str, n: int) -> Tuple[Optional[int], List[Dict]]:
    r = get_redis()
    cursor = int(r.get(f"session:{user_id}:summary:rounds") or 0)
    total = r.llen(f"session:{user_id}:history")
    if (total - cursor) < n:
        return None, []
    items = r.lrange(f"session:{user_id}:history", cursor, cursor + n - 1)
    return cursor, [json.loads(x) for x in items]


def peek_remaining(user_id: str) -> Tuple[int, List[Dict]]:
    r = get_redis()
    cursor = int(r.get(f"session:{user_id}:summary:rounds") or 0)
    total = r.llen(f"session:{user_id}:history")
    if total <= cursor:
        return cursor, []
    items = r.lrange(f"session:{user_id}:history", cursor, total - 1)
    return cursor, [json.loads(x) for x in items]


def commit_summary_chunk(user_id: str, expected_cursor: int, advance: int, add_text: str) -> bool:
    r = get_redis()
    ckey = f"session:{user_id}:summary:rounds"
    tkey = f"session:{user_id}:summary:text"
    with r.pipeline() as p:
        while True:
            try:
                p.watch(ckey, tkey)
                cur = int(p.get(ckey) or 0)
                if cur != expected_cursor:
                    p.unwatch()
                    return False
                old = p.get(tkey) or ""
                new = (old + ("\n\n" if old else "") + (add_text or "").strip()) if add_text else old
                p.multi()
                p.set(tkey, new)
                p.set(ckey, cur + int(advance))
                p.execute()
                _touch_ttl([ckey, tkey])
                return True
            except redis.WatchError:
                return False


def ensure_alert_group() -> None:
    r = get_redis()
    try:
        r.xgroup_create(name=ALERT_STREAM_KEY, groupname=ALERT_STREAM_GROUP, id='$', mkstream=True)
    except redis.ResponseError as e:
        if 'BUSYGROUP' not in str(e):
            raise


def xadd_alert(user_id: str, reason: str, severity: str = "info", extra: Optional[Dict] = None) -> str:
    ensure_alert_group()
    r = get_redis()
    fields = {"user_id": user_id, "reason": reason, "severity": severity, "ts": str(int(time.time() * 1000))}
    if extra:
        fields["extra"] = json.dumps(extra, ensure_ascii=False)
    xid = r.xadd(ALERT_STREAM_KEY, fields)
    r.rpush(f"session:{user_id}:alerts", json.dumps(fields, ensure_ascii=False))
    _touch_ttl([f"session:{user_id}:alerts"])
    return xid


def pop_all_alerts(user_id: str) -> List[Dict]:
    r = get_redis()
    key = f"session:{user_id}:alerts"
    with r.pipeline() as p:
        p.lrange(key, 0, -1)
        p.delete(key)
        items, _ = p.execute()
    return [json.loads(x) for x in items]


def purge_user_session(user_id: str) -> int:
    r = get_redis()
    keys = [
        f"session:{user_id}:history",
        f"session:{user_id}:summary:text",
        f"session:{user_id}:summary:rounds",
        f"session:{user_id}:alerts",
        f"session:{user_id}:state",
    ]
    p = r.pipeline()
    for k in keys:
        p.delete(k)
    res = p.execute()
    return sum(res)


def set_state_if(user_id: str, expect: str, to: str) -> bool:
    r = get_redis()
    key = f"session:{user_id}:state"
    try:
        with r.pipeline() as pipe:
            while True:
                try:
                    pipe.watch(key)
                    cur = pipe.get(key)
                    if expect is None or expect == "":
                        if cur not in (None, ""):
                            pipe.unwatch()
                            return False
                    else:
                        if cur != expect:
                            pipe.unwatch()
                            return False
                    pipe.multi()
                    pipe.set(key, to)
                    pipe.execute()
                    try:
                        _touch_ttl([key])
                    except Exception:
                        pass
                    return True
                except redis.WatchError:
                    return False
    except Exception:
        return False


def append_audio_segment(user_id: str, audio_id: str, seg: str, ttl_sec: int = 3600) -> None:
    r = get_redis()
    key = f"audio:{user_id}:{audio_id}:buf"
    r.rpush(key, seg)
    r.expire(key, ttl_sec)


def read_and_clear_audio_segments(user_id: str, audio_id: str) -> str:
    r = get_redis()
    key = f"audio:{user_id}:{audio_id}:buf"
    with r.pipeline() as p:
        p.lrange(key, 0, -1)
        p.delete(key)
        parts, _ = p.execute()
    try:
        parts = [x if isinstance(x, str) else x.decode("utf-8", "ignore") for x in parts]
    except Exception:
        parts = []
    return " ".join([p.strip() for p in parts if p])


def get_audio_result(user_id: str, audio_id: str) -> Optional[str]:
    return get_redis().get(f"audio:{user_id}:{audio_id}:result")


def set_audio_result(user_id: str, audio_id: str, reply: str, ttl_sec: int = 86400) -> None:
    get_redis().set(f"audio:{user_id}:{audio_id}:result", reply, ex=ttl_sec)


# ---- Lightweight audio locks (separate from session state) ----
def acquire_audio_lock(lock_id: str, ttl_sec: int = 60) -> bool:
    """Try acquire a short-lived lock; return True on success.

    Use a dedicated key independent from session state to avoid interference.
    """
    r = get_redis()
    key = f"lock:audio:{lock_id}"
    try:
        # SET NX with expiration
        return bool(r.set(key, "1", nx=True, ex=ttl_sec))
    except Exception:
        return False


def release_audio_lock(lock_id: str) -> None:
    r = get_redis()
    key = f"lock:audio:{lock_id}"
    try:
        r.delete(key)
    except Exception:
        pass

