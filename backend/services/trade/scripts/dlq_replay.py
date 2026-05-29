#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

# 允许从项目根目录直接执行该脚本
ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.trade.redis_client import get_redis


def _load_event(fields: Dict[str, Any]) -> Dict[str, Any]:
    raw_event_json = fields.get("raw_event_json")
    if raw_event_json:
        try:
            obj = json.loads(str(raw_event_json))
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass

    # fallback: 从 DLQ 字段恢复最小事件
    event: Dict[str, Any] = {}
    for key in [
        "event_type",
        "tenant_id",
        "user_id",
        "client_order_id",
        "broker_order_id",
        "exec_id",
        "symbol",
        "side",
        "quantity",
        "price",
    ]:
        if fields.get(key) is not None:
            event[key] = fields.get(key)
    return event


def _iter_filtered_entries(
    entries: Iterable[Tuple[str, Dict[str, Any]]],
    *,
    reason_contains: str | None,
    event_type: str | None,
) -> List[Tuple[str, Dict[str, Any]]]:
    result: List[Tuple[str, Dict[str, Any]]] = []
    for message_id, fields in entries:
        if reason_contains:
            reason = str(fields.get("reason") or "")
            if reason_contains not in reason:
                continue
        if event_type:
            current_type = str(fields.get("event_type") or "")
            if current_type != event_type:
                continue
        result.append((message_id, fields))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay execution DLQ events back to stream")
    parser.add_argument("--tenant", default="default", help="tenant id")
    parser.add_argument("--dlq-prefix", default="qm:exec:dlq", help="DLQ stream prefix")
    parser.add_argument("--exec-prefix", default="qm:exec:stream", help="default target stream prefix")
    parser.add_argument("--dlq-stream", default=None, help="explicit DLQ stream name")
    parser.add_argument("--target-stream", default=None, help="explicit target stream name")
    parser.add_argument("--start-id", default="-", help="xrange start id")
    parser.add_argument("--end-id", default="+", help="xrange end id")
    parser.add_argument("--max-count", type=int, default=100, help="max records to scan and replay")
    parser.add_argument("--reason-contains", default=None, help="filter by reason keyword")
    parser.add_argument("--event-type", default=None, help="filter by event_type")
    parser.add_argument("--dry-run", action="store_true", help="only print replay candidates")
    parser.add_argument(
        "--delete-after-replay",
        action="store_true",
        help="delete message from dlq after successful replay",
    )
    args = parser.parse_args()

    redis_wrap = get_redis()
    if redis_wrap.client is None:
        redis_wrap.connect()
    client = redis_wrap.client
    if client is None:
        raise RuntimeError("redis client unavailable")

    dlq_stream = args.dlq_stream or f"{args.dlq_prefix}:{args.tenant}"
    default_target = f"{args.exec_prefix}:{args.tenant}"

    entries = client.xrange(
        dlq_stream,
        min=args.start_id,
        max=args.end_id,
        count=max(1, args.max_count),
    )
    filtered = _iter_filtered_entries(
        entries,
        reason_contains=args.reason_contains,
        event_type=args.event_type,
    )

    print(f"DLQ stream={dlq_stream} total={len(entries)} filtered={len(filtered)}")

    replayed = 0
    deleted = 0
    for message_id, fields in filtered:
        target_stream = str(fields.get("source_stream") or args.target_stream or default_target)
        event = _load_event(fields)
        event["replay_from_dlq"] = "true"
        event["replay_source_message_id"] = str(message_id)

        if args.dry_run:
            print(
                f"[DRY-RUN] id={message_id} -> {target_stream} "
                f"event_type={event.get('event_type')} client_order_id={event.get('client_order_id')}"
            )
            replayed += 1
            continue

        payload = {k: str(v) for k, v in event.items() if v is not None}
        client.xadd(target_stream, payload, maxlen=200000, approximate=True)
        replayed += 1
        print(
            f"[REPLAY] id={message_id} -> {target_stream} "
            f"event_type={event.get('event_type')} client_order_id={event.get('client_order_id')}"
        )

        if args.delete_after_replay:
            deleted += int(client.xdel(dlq_stream, message_id) or 0)

    print(f"Replay completed: replayed={replayed}, deleted={deleted}, dry_run={args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
