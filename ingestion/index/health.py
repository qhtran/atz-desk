"""`python -m ingestion.index.health`: exit 0 khi heartbeat idx:health còn mới."""
from __future__ import annotations

import json
import sys
import time

import redis

from ingestion.index.common import load


def main() -> int:
    s = load()
    try:
        raw = redis.Redis.from_url(s.redis_url, decode_responses=True, socket_timeout=3).get(s.health_key)
    except redis.exceptions.RedisError as err:
        print(f"redis down: {err}")
        return 1
    if not raw:
        print("heartbeat missing")
        return 1
    beat = json.loads(raw)
    age = time.time() - float(beat.get("epoch", 0))
    print(json.dumps({"age_s": round(age, 1), **beat}, ensure_ascii=False))
    return 0 if age <= s.health_max_age else 1


if __name__ == "__main__":
    sys.exit(main())
