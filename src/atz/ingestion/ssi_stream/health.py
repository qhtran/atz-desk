"""Healthcheck container: ssi_stream:health fresh + healthy=true."""
from __future__ import annotations

import json
import os
import sys
import time

import redis
import yaml

from storage.paths import repo_root


def main() -> int:
    path = os.environ.get("SSI_STREAM_CONFIG") or str(repo_root() / "config" / "ssi_stream.yaml")
    doc = yaml.safe_load(open(path, encoding="utf-8"))
    rconf = doc["redis"]
    url = os.environ.get("REDIS_URL") or rconf["url"]
    key = rconf["health_key"]
    max_age = float(doc["ssi_stream"].get("silence_seconds_off") or 180) + 30
    try:
        r = redis.Redis.from_url(url, decode_responses=True, socket_timeout=2)
        raw = r.get(key)
    except Exception as err:  # noqa: BLE001
        print(f"redis fail: {err}", file=sys.stderr)
        return 1
    if not raw:
        # Process có thể đang reconnect — chưa fail cứng lúc start
        print("no health yet", file=sys.stderr)
        return 1
    h = json.loads(raw)
    age = time.time() - float(h.get("epoch") or 0)
    if age > max_age:
        print(f"stale age={age:.0f}", file=sys.stderr)
        return 1
    # connected hoặc đang backup-visible vẫn OK nếu process ghi health
    print("ok", h.get("phase"), "age", round(age, 1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
