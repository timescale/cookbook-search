#!/usr/bin/env python3
"""Generate deterministic synthetic incident events for the cookbook.

The dataset is a compact adaptation of the in-progress Incident-search
cookbook. It represents the fictional ``tigerlily`` e-commerce platform and
contains no real people, customers, or vendors. The same seed and row count
always produce the same records.

Usage:
    python generate_data.py --rows 1200 --output sample_data/events.csv

The module can also be imported by load.py, which avoids creating a local CSV.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path


INCIDENTS = (
    (
        "db_pool_exhaustion",
        "checkout-api",
        (
            "Checkout requests time out while acquiring a database connection.",
            "Postgres reports too many clients already with SQLSTATE 53300.",
            "Connection count reached max_connections after the payments deploy.",
            "Rollback started; terminating idle-in-transaction sessions older than 60 seconds.",
            "Database connections returned below 60 percent and checkout p99 recovered.",
        ),
    ),
    (
        "tls_cert_expiry",
        "edge-proxy",
        (
            "Synthetic probes report that the edge certificate has expired.",
            "TLS handshakes fail before requests reach otherwise healthy backend services.",
            "cert-manager renewal failed because the ACME challenge path was blocked.",
            "The edge team restored the challenge route and forced certificate renewal.",
            "Traffic recovered after the renewed certificate was loaded by the proxy.",
        ),
    ),
    (
        "embedding_worker_oom",
        "embedding-worker",
        (
            "Embedding worker memory rose sharply after the model rollout.",
            "Kubernetes reports OOMKilled and CrashLoopBackOff for worker pods.",
            "Batch size and model cache together exceeded the container memory limit.",
            "The rollout was reverted and batch size was reduced.",
            "Worker memory stabilized and the queue began draining normally.",
        ),
    ),
    (
        "kafka_consumer_lag",
        "order-service",
        (
            "Order events are arriving faster than the consumer group can process them.",
            "Kafka consumer lag crossed the critical threshold on orders.created.",
            "A poison message caused repeated retries in one partition.",
            "The message was moved to the dead-letter queue and consumers were restarted.",
            "Consumer lag returned to normal across every partition.",
        ),
    ),
    (
        "redis_eviction_storm",
        "redis-cache",
        (
            "Cache hit rate fell while Redis memory remained at its configured maximum.",
            "Redis began evicting hot session keys under allkeys-lru pressure.",
            "Checkout latency increased because requests fell through to Postgres.",
            "Cache capacity was increased and oversized recommendation entries were removed.",
            "Evictions stopped and cache hit rate recovered.",
        ),
    ),
    (
        "dns_resolution_failure",
        "api-gateway",
        (
            "API gateway requests fail while resolving an internal service hostname.",
            "Pods report temporary failure in name resolution and upstream lookup errors.",
            "CoreDNS saturation caused intermittent SERVFAIL responses.",
            "DNS replicas were scaled out and the noisy search domain was removed.",
            "Name resolution latency and gateway success rate returned to normal.",
        ),
    ),
    (
        "disk_full_wal",
        "postgres",
        (
            "Postgres primary disk usage crossed 95 percent as WAL accumulated.",
            "Replication slot retention prevented old WAL segments from being removed.",
            "Writes slowed and the database reported no space left on device.",
            "The abandoned replication slot was dropped and storage was expanded.",
            "WAL usage declined and write latency recovered.",
        ),
    ),
    (
        "mtls_cert_mismatch",
        "auth-service",
        (
            "Authentication calls fail during the mutual TLS handshake.",
            "The client certificate issuer does not match the newly rotated trust bundle.",
            "Auth-service reports unknown ca while other endpoints remain healthy.",
            "The compatible trust bundle was restored across the client fleet.",
            "Mutual TLS handshakes and login success rate recovered.",
        ),
    ),
    (
        "migration_lock",
        "inventory",
        (
            "Inventory writes are waiting behind a schema migration lock.",
            "An ALTER TABLE statement holds an access exclusive lock during peak traffic.",
            "Request latency rises as blocked database sessions accumulate.",
            "The migration was cancelled and rescheduled with a safer rollout plan.",
            "Blocked sessions cleared and inventory writes recovered.",
        ),
    ),
    (
        "feature_flag_misconfig",
        "checkout-api",
        (
            "Checkout errors began immediately after a production feature flag change.",
            "The new payment path was enabled for all users instead of one percent.",
            "Requests reach an incomplete handler and return HTTP 500.",
            "The feature flag was disabled and configuration caches were refreshed.",
            "Checkout error rate returned to baseline.",
        ),
    ),
)

ROUTINE_MESSAGES = (
    "Health check completed successfully in {latency} ms.",
    "Processed {count} requests during the last reporting interval.",
    "Background cache refresh completed with {count} entries updated.",
    "Deployment readiness probe passed for version {version}.",
    "Scheduled metrics export completed in {latency} ms.",
    "Connection pool utilization is {percent} percent.",
)

SERVICES = tuple(sorted({item[1] for item in INCIDENTS} | {"payments", "catalog-api", "notifications"}))
BASE_TIME = datetime(2026, 9, 1, tzinfo=timezone.utc)


def generate_events(row_count: int = 1200, seed: int = 2026) -> list[dict[str, object]]:
    """Return a deterministic mix of routine and incident-related events."""
    incident_rows = sum(len(messages) for _, _, messages in INCIDENTS)
    if row_count < max(500, incident_rows):
        raise ValueError("row_count must be at least 500 so PRISM has useful training data")

    rng = random.Random(seed)
    events: list[dict[str, object]] = []

    for number, (family, service, messages) in enumerate(INCIDENTS, start=1):
        incident_id = f"INC-2026-{number:04d}"
        start = BASE_TIME + timedelta(days=number * 2, hours=number)
        for phase, message in enumerate(messages):
            events.append(
                {
                    "occurred_at": start + timedelta(minutes=phase * 7),
                    "service": service,
                    "severity": "critical" if phase in (1, 2) else "warning",
                    "incident_id": incident_id,
                    "incident_family": family,
                    "content": message,
                    "metadata": json.dumps({"phase": phase, "environment": "production"}),
                }
            )

    while len(events) < row_count:
        service = rng.choice(SERVICES)
        template = rng.choice(ROUTINE_MESSAGES)
        events.append(
            {
                "occurred_at": BASE_TIME + timedelta(seconds=rng.randrange(45 * 24 * 3600)),
                "service": service,
                "severity": rng.choices(("info", "warning"), weights=(19, 1), k=1)[0],
                "incident_id": None,
                "incident_family": None,
                "content": template.format(
                    latency=rng.randrange(8, 240),
                    count=rng.randrange(10, 5000),
                    version=f"{rng.randrange(1, 6)}.{rng.randrange(0, 20)}.{rng.randrange(0, 10)}",
                    percent=rng.randrange(10, 80),
                ),
                "metadata": json.dumps({"environment": "production"}),
            }
        )

    events.sort(key=lambda row: (row["occurred_at"], row["service"], row["content"]))
    return events


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=1200)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--output", type=Path, default=Path("sample_data/events.csv"))
    args = parser.parse_args()

    rows = generate_events(args.rows, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    columns = tuple(rows[0])
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows):,} deterministic events to {args.output}")


if __name__ == "__main__":
    main()
