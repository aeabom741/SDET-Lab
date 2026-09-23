"""
SDET System Design Lab — Profile Update API
=============================================
這是一個模擬「更新用戶 Profile」的 API，
用來練習分散式系統的故障場景與測試策略。

架構：
  Actor → Flask API → PostgreSQL (DB) → Redis (Cache)

你可以透過 X-Fail-At header 來注入故障，
模擬系統在不同步驟掛掉的情況。
"""

import json
import os
import time

import psycopg2
import redis
from flask import Flask, jsonify, request

app = Flask(__name__)

# ---------- 連線設定 ----------

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://sdet:sdet_pass@localhost:5432/sdet_lab"
)
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# Cache TTL（秒）作為安全網。用環境變數控制，讓測試能把過期時間縮短，
# 以驗證「TTL 到期後自癒」的行為，而不需要在測試裡真的等 60 秒。
CACHE_TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", "60"))

redis_client = redis.from_url(REDIS_URL, decode_responses=True)


def get_db_connection():
    return psycopg2.connect(DATABASE_URL)


# ---------- 初始化資料庫 ----------

def init_db():
    """建立 users 表（如果不存在）"""
    retries = 5
    for i in range(retries):
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id VARCHAR(50) PRIMARY KEY,
                    nickname VARCHAR(100),
                    bio TEXT,
                    avatar_url TEXT,
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            # 插入一筆測試用的種子資料
            cur.execute("""
                INSERT INTO users (user_id, nickname, bio, avatar_url)
                VALUES ('user_001', 'Leo', '原始的 Bio', 'https://old-avatar.jpg')
                ON CONFLICT (user_id) DO NOTHING
            """)
            conn.commit()
            cur.close()
            conn.close()
            print("✅ Database initialized successfully")
            return
        except psycopg2.OperationalError:
            print(f"⏳ Waiting for DB... ({i + 1}/{retries})")
            time.sleep(2)
    print("❌ Failed to connect to database")


# ---------- API 路由 ----------

@app.route("/profile/<user_id>", methods=["GET"])
def get_profile(user_id):
    """
    讀取 Profile（Cache-Aside Pattern）
    1. 先查 Redis Cache
    2. Cache Miss → 查 DB → 寫回 Cache
    """
    # Step 1: 嘗試從 Redis 讀取
    cached = redis_client.get(f"profile:{user_id}")
    if cached:
        data = json.loads(cached)
        data["_source"] = "cache"  # 標記資料來源，方便測試驗證
        return jsonify(data)

    # Step 2: Cache Miss，從 DB 讀取
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id, nickname, bio, avatar_url FROM users WHERE user_id = %s",
        (user_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return jsonify({"error": "User not found"}), 404

    data = {
        "user_id": row[0],
        "nickname": row[1],
        "bio": row[2],
        "avatar_url": row[3],
    }

    # 寫回 Cache（TTL 作為安全網，秒數由 CACHE_TTL_SECONDS 控制）
    redis_client.setex(f"profile:{user_id}", CACHE_TTL_SECONDS, json.dumps(data))
    data["_source"] = "database"
    return jsonify(data)


@app.route("/profile/<user_id>", methods=["PUT"])
def update_profile(user_id):
    """
    更新 Profile（同步流程）

    正常流程：
      1. 收到 PUT 請求
      2. 寫入 DB（更新 bio, avatar_url）
      3. 更新 Redis Cache
      4. 回傳 200 OK

    故障注入：
      透過 Header 'X-Fail-At' 控制在哪個步驟掛掉
      - "after_db"    → DB 寫入成功後、更新 Cache 前掛掉（幽靈數據！）
      - "after_cache" → Cache 更新成功後、回傳前掛掉
    """
    payload = request.get_json()
    if not payload:
        return jsonify({"error": "Request body is required"}), 400

    new_bio = payload.get("bio")
    new_avatar = payload.get("avatar_url")
    fail_at = request.headers.get("X-Fail-At", "").lower()

    # ===== Step 1: 寫入 DB =====
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE users
            SET bio = COALESCE(%s, bio),
                avatar_url = COALESCE(%s, avatar_url),
                updated_at = NOW()
            WHERE user_id = %s
            RETURNING user_id, nickname, bio, avatar_url
            """,
            (new_bio, new_avatar, user_id),
        )
        row = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        return jsonify({"error": f"DB write failed: {str(e)}"}), 500

    if not row:
        return jsonify({"error": "User not found"}), 404

    updated_data = {
        "user_id": row[0],
        "nickname": row[1],
        "bio": row[2],
        "avatar_url": row[3],
    }

    # ===== 故障注入點 1: DB 寫完、Cache 還沒更新 =====
    if fail_at == "after_db":
        # 模擬 Server 在這個瞬間崩潰
        # DB 已經是新資料，但 Redis 還是舊資料 → 幽靈數據！
        return jsonify({"error": "💥 Server crashed after DB write!"}), 500

    # ===== Step 2: 更新 Redis Cache =====
    try:
        redis_client.setex(
            f"profile:{user_id}", CACHE_TTL_SECONDS, json.dumps(updated_data)
        )
    except Exception as e:
        # Redis 掛了但 DB 已經寫了 — 資料不一致！
        return jsonify({
            "warning": "DB updated but cache update failed",
            "data": updated_data,
        }), 207  # 207 Multi-Status: 部分成功

    # ===== 故障注入點 2: Cache 更新完、回傳前 =====
    if fail_at == "after_cache":
        return jsonify({"error": "💥 Server crashed after cache update!"}), 500

    # ===== Step 3: 成功回傳 =====
    return jsonify({
        "message": "Profile updated successfully",
        "data": updated_data,
    })


@app.route("/debug/state/<user_id>", methods=["GET"])
def debug_state(user_id):
    """
    偵錯用 API：同時顯示 DB 和 Redis 的資料
    SDET 用這個來驗證資料一致性
    """
    # 讀 DB
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id, nickname, bio, avatar_url FROM users WHERE user_id = %s",
        (user_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    db_data = None
    if row:
        db_data = {
            "user_id": row[0],
            "nickname": row[1],
            "bio": row[2],
            "avatar_url": row[3],
        }

    # 讀 Redis
    cached = redis_client.get(f"profile:{user_id}")
    cache_data = json.loads(cached) if cached else None

    # 比對一致性
    is_consistent = True
    inconsistencies = []

    if db_data and cache_data:
        for key in ["bio", "avatar_url"]:
            if db_data.get(key) != cache_data.get(key):
                is_consistent = False
                inconsistencies.append({
                    "field": key,
                    "db_value": db_data.get(key),
                    "cache_value": cache_data.get(key),
                })

    return jsonify({
        "database": db_data,
        "cache": cache_data,
        "is_consistent": is_consistent,
        "inconsistencies": inconsistencies,
    })


@app.route("/debug/reset/<user_id>", methods=["POST"])
def reset_user(user_id):
    """重置用戶資料到初始狀態（方便反覆測試）"""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE users
        SET bio = '原始的 Bio',
            avatar_url = 'https://old-avatar.jpg',
            updated_at = NOW()
        WHERE user_id = %s
        """,
        (user_id,),
    )
    conn.commit()
    cur.close()
    conn.close()

    # 清除 Cache
    redis_client.delete(f"profile:{user_id}")

    return jsonify({"message": f"User {user_id} reset to initial state"})


# ---------- 啟動 ----------

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
