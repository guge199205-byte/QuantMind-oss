"""
Notification metrics shared by API / stream / publisher.
"""

from __future__ import annotations

try:
    from prometheus_client import Counter, Histogram

    notification_publish_total = Counter(
        "quantmind_notification_publish_total",
        "Notification publish attempts by result",
        ["result"],
    )
    notification_event_push_total = Counter(
        "quantmind_notification_event_push_total",
        "Notification event push attempts by result",
        ["result"],
    )
    notification_unread_query_duration_seconds = Histogram(
        "quantmind_notification_unread_query_duration_seconds",
        "Notification unread query duration in seconds",
    )
    notification_ws_deliver_total = Counter(
        "quantmind_notification_ws_deliver_total",
        "Notification websocket deliveries by result",
        ["result"],
    )
except Exception:  # pragma: no cover
    notification_publish_total = None
    notification_event_push_total = None
    notification_unread_query_duration_seconds = None
    notification_ws_deliver_total = None


def inc_counter(counter, result: str) -> None:
    if counter is None:
        return
    counter.labels(result=result).inc()


class _NoopTimer:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def timer(histogram):
    if histogram is None:
        return _NoopTimer()
    return histogram.time()
