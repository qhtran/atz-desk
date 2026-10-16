"""Nhập vị thế tạm thời (chưa có UI - Module 5 sẽ làm).

docker exec atz-position python -m position_monitor.cli add --user akadmin --symbol FPT --qty 100 --entry 58600 --sl 55000 --tp 65000
  --unit k : nhập giá theo nghìn đồng như tab Danh mục (58.6 -> 58600 VND)
docker exec atz-position python -m position_monitor.cli list [--user akadmin]
docker exec atz-position python -m position_monitor.cli close ID
docker exec atz-position python -m position_monitor.cli set ID [--sl X] [--tp Y] [--unit k]   (đổi mức -> bật lại cảnh báo mức đó)
docker exec atz-position python -m position_monitor.cli rearm ID
docker exec atz-position python -m position_monitor.cli live --user akadmin      (P&L realtime từ Redis)
"""
from __future__ import annotations

import argparse
import json
import sys

import redis

from position_monitor import config, store


def _user_id(conn, user: str) -> int:
    if user.isdigit():
        return int(user)
    row = conn.execute("SELECT id FROM users WHERE username = ?", (user,)).fetchone()
    if row is None:
        raise SystemExit(f"không có user '{user}'")
    return int(row["id"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="position_monitor.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add"); a.add_argument("--user", required=True); a.add_argument("--symbol", required=True)
    a.add_argument("--qty", type=float, required=True); a.add_argument("--entry", type=float, required=True)
    a.add_argument("--sl", type=float); a.add_argument("--tp", type=float); a.add_argument("--note")
    a.add_argument("--unit", choices=["vnd", "k"], default="vnd")
    l = sub.add_parser("list"); l.add_argument("--user")
    for name in ("close", "rearm"):
        sub.add_parser(name).add_argument("id", type=int)
    s = sub.add_parser("set"); s.add_argument("id", type=int); s.add_argument("--sl", type=float); s.add_argument("--tp", type=float)
    s.add_argument("--unit", choices=["vnd", "k"], default="vnd")
    v = sub.add_parser("live"); v.add_argument("--user", required=True)
    args = ap.parse_args(argv)
    cfg = config.load()
    conn = store.open_db(cfg["sqlite"]["path"])
    k = 1000.0 if getattr(args, "unit", "vnd") == "k" else 1.0
    scale = lambda x: None if x is None else x * k  # noqa: E731
    if args.cmd == "add":
        pid = store.add(conn, _user_id(conn, args.user), args.symbol, args.qty, args.entry * k, scale(args.sl), scale(args.tp), args.note)
        print(f"added position id={pid}")
    elif args.cmd == "list":
        rows = store.list_all(conn, _user_id(conn, args.user) if args.user else None)
        for r in rows:
            print(json.dumps(r, ensure_ascii=False))
    elif args.cmd == "close":
        print("closed" if store.close(conn, args.id) else "not open")
    elif args.cmd == "rearm":
        store.rearm(conn, args.id); print("rearmed")
    elif args.cmd == "set":
        store.update_levels(conn, args.id, scale(args.sl), scale(args.tp)); print("updated")
    elif args.cmd == "live":
        r = redis.Redis.from_url(cfg["redis"]["url"], decode_responses=True, socket_timeout=5)
        uid = _user_id(conn, args.user)
        for pid, val in sorted(r.hgetall(cfg["position_monitor"]["live"]["key"].format(user_id=uid)).items()):
            print(val)
    return 0


if __name__ == "__main__":
    sys.exit(main())
