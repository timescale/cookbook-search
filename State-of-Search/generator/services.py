"""
Service catalog and routine (non-incident) log templates for the synthetic
"Tigerlily" e-commerce platform.

Every service has a GitHub repo, a team that owns it, a rough traffic share
(used to weight how many routine events it emits), and a kind that decides
which template pool its routine logs come from.
"""

# kind: http_api | worker | datastore | infra
SERVICES = {
    "checkout-api":     {"repo": "tigerlily/checkout-api",     "team": "payments-platform", "share": 9,  "kind": "http_api",  "lang": "Go"},
    "payments":         {"repo": "tigerlily/payments",         "team": "payments-platform", "share": 7,  "kind": "http_api",  "lang": "Go"},
    "billing":          {"repo": "tigerlily/billing",          "team": "payments-platform", "share": 3,  "kind": "worker",    "lang": "Java"},
    "cart-service":     {"repo": "tigerlily/cart-service",     "team": "storefront",        "share": 8,  "kind": "http_api",  "lang": "Node.js"},
    "catalog-api":      {"repo": "tigerlily/catalog-api",      "team": "storefront",        "share": 9,  "kind": "http_api",  "lang": "Java"},
    "search-api":       {"repo": "tigerlily/search-api",       "team": "discovery",         "share": 7,  "kind": "http_api",  "lang": "Python"},
    "recommendations":  {"repo": "tigerlily/recommendations",  "team": "discovery",         "share": 4,  "kind": "http_api",  "lang": "Python"},
    "embedding-worker": {"repo": "tigerlily/recommendations",  "team": "discovery",         "share": 3,  "kind": "worker",    "lang": "Python"},
    "inventory":        {"repo": "tigerlily/inventory",        "team": "fulfillment",       "share": 5,  "kind": "http_api",  "lang": "Go"},
    "order-service":    {"repo": "tigerlily/order-service",    "team": "fulfillment",       "share": 6,  "kind": "worker",    "lang": "Java"},
    "notifications":    {"repo": "tigerlily/notifications",    "team": "growth",            "share": 4,  "kind": "worker",    "lang": "Node.js"},
    "auth-service":     {"repo": "tigerlily/auth-service",     "team": "identity",          "share": 6,  "kind": "http_api",  "lang": "Go"},
    "user-profile":     {"repo": "tigerlily/user-profile",     "team": "identity",          "share": 4,  "kind": "http_api",  "lang": "Node.js"},
    "image-resizer":    {"repo": "tigerlily/image-resizer",    "team": "storefront",        "share": 3,  "kind": "worker",    "lang": "Rust"},
    "scheduler":        {"repo": "tigerlily/scheduler",        "team": "platform-infra",    "share": 2,  "kind": "worker",    "lang": "Go"},
    "api-gateway":      {"repo": "tigerlily/api-gateway",      "team": "platform-infra",    "share": 8,  "kind": "infra",     "lang": "Go"},
    "edge-proxy":       {"repo": "tigerlily/edge-proxy",       "team": "platform-infra",    "share": 6,  "kind": "infra",     "lang": "config"},
    "postgres":         {"repo": "tigerlily/db-ops",           "team": "data-infra",        "share": 5,  "kind": "datastore", "lang": "SQL"},
    "redis-cache":      {"repo": "tigerlily/db-ops",           "team": "data-infra",        "share": 3,  "kind": "datastore", "lang": "config"},
    "kafka":            {"repo": "tigerlily/db-ops",           "team": "data-infra",        "share": 3,  "kind": "datastore", "lang": "config"},
}

ENVIRONMENTS = [("production", 80), ("staging", 15), ("dev", 5)]
REGIONS = [("us-east-1", 45), ("us-west-2", 25), ("eu-central-1", 20), ("ap-southeast-1", 10)]

# Routine severity mix. Incidents add their own errors on top of this.
ROUTINE_SEVERITY = [("info", 780), ("warning", 170), ("error", 45), ("critical", 5)]

HTTP_PATHS = {
    "checkout-api":  ["/v1/checkout", "/v1/checkout/{id}/confirm", "/v1/checkout/{id}/shipping", "/v1/checkout/{id}/tax", "/healthz"],
    "payments":      ["/v1/payments/authorize", "/v1/payments/capture", "/v1/payments/{id}", "/v1/payments/{id}/refund", "/healthz"],
    "cart-service":  ["/v1/cart/{id}", "/v1/cart/{id}/items", "/v1/cart/{id}/merge", "/v1/cart/{id}/coupon", "/healthz"],
    "catalog-api":   ["/v2/products/{id}", "/v2/products", "/v2/categories/{id}", "/v2/products/{id}/variants", "/healthz"],
    "search-api":    ["/v1/search", "/v1/search/suggest", "/v1/search/facets", "/healthz"],
    "recommendations": ["/v1/recommendations/{id}", "/v1/recommendations/similar/{id}", "/v1/recommendations/trending", "/healthz"],
    "inventory":     ["/v1/inventory/{id}", "/v1/inventory/reserve", "/v1/inventory/release", "/v1/inventory/bulk", "/healthz"],
    "auth-service":  ["/oauth/token", "/oauth/introspect", "/v1/sessions", "/v1/sessions/{id}", "/.well-known/jwks.json"],
    "user-profile":  ["/v1/users/{id}", "/v1/users/{id}/addresses", "/v1/users/{id}/preferences", "/healthz"],
}

# {placeholders} are filled by the generator: id, ms, path, status, pod, node,
# n, pct, mb, version, region, topic, partition, lag, job, table, query_ms
ROUTINE_TEMPLATES = {
    "http_api": {
        "info": [
            "GET {path} 200 {ms}ms trace={trace}",
            "POST {path} 201 {ms}ms trace={trace}",
            "GET {path} 200 {ms}ms cache=hit trace={trace}",
            "GET {path} 304 {ms}ms trace={trace}",
            "PUT {path} 200 {ms}ms trace={trace}",
            "DELETE {path} 204 {ms}ms trace={trace}",
            "readiness probe succeeded on {pod}",
            "request completed method=GET path={path} status=200 duration_ms={ms} upstream_ms={ums}",
            "circuit breaker for downstream {dep} is closed, {n} successes in window",
            "connection pool stats: active={active} idle={idle} waiting=0 max={max}",
            "served {n} requests in last 60s, p50={ms}ms p99={p99}ms error_rate=0.{pct}%",
            "graceful shutdown complete on {pod}, drained {n} in-flight requests",
            "started {pod} version={version} commit={sha} listening on :8080",
            "feature flag snapshot refreshed, {n} flags loaded from config service",
            "JWKS cache refreshed, {n} signing keys, next refresh in 3600s",
            "trace sampler: sampled {n} of {total} spans (rate 0.{pct})",
        ],
        "warning": [
            "GET {path} 200 {slow_ms}ms exceeds slow-request threshold (1000ms) trace={trace}",
            "POST {path} 429 client rate limited api_key=ak_...{sha4} trace={trace}",
            "GET {path} 404 unknown resource id={id} trace={trace}",
            "retrying call to {dep} attempt 2/3 after timeout {ms}ms trace={trace}",
            "connection pool utilization {pct}% (active={active} max={max})",
            "upstream {dep} responded 503, serving stale cache entry age={n}s",
            "request body {mb}MB exceeds recommended size for {path}",
            "GC pause {ms}ms on {pod} exceeds 200ms budget",
            "deprecated header X-Legacy-Session received from client ua=tigerlily-ios/4.{n}",
            "TLS handshake to {dep} took {slow_ms}ms",
        ],
        "error": [
            "POST {path} 400 invalid request body: field 'quantity' must be positive trace={trace}",
            "GET {path} 500 unhandled error: context deadline exceeded calling {dep} trace={trace}",
            "POST {path} 409 optimistic lock conflict on {table} id={id} trace={trace}",
            "client disconnected before response written path={path} trace={trace}",
            "PUT {path} 502 upstream {dep} connection reset by peer trace={trace}",
            "panic recovered in handler {path}: nil pointer dereference (recovered, request failed) trace={trace}",
        ],
        "critical": [
            "liveness probe failed 3 times on {pod}, container will be restarted",
            "all {n} replicas of {dep} unreachable from {pod}, failing open",
        ],
    },
    "worker": {
        "info": [
            "job {job} completed: processed {n} records in {sec}s",
            "consumed {n} messages from {topic} partition {partition} offset={offset} lag={lag}",
            "scheduled job {job} started run_id={id}",
            "batch flushed {n} rows to {table} in {ms}ms",
            "worker {pod} heartbeat ok, queue_depth={n}",
            "consumer group {group} rebalance complete, assigned partitions [{partition}]",
            "retry queue drained, {n} messages reprocessed successfully",
            "started {pod} version={version} commit={sha} concurrency={n}",
            "checkpoint committed for {topic} at offset {offset}",
            "outbound webhook to merchant {id} delivered 200 in {ms}ms",
        ],
        "warning": [
            "consumer lag on {topic} partition {partition} is {lag} messages (threshold 1000)",
            "job {job} took {sec}s, exceeding expected duration of 120s",
            "message on {topic} offset={offset} failed schema validation, sent to DLQ",
            "worker {pod} memory {mb}MB approaching limit {limit}MB",
            "retrying webhook to merchant {id} attempt 3/5 after 502",
            "job {job} skipped: previous run still holding lock {id}",
            "processing rate dropped to {n}/s from baseline {baseline}/s",
        ],
        "error": [
            "job {job} failed: {table} row id={id} violates foreign key constraint",
            "failed to publish to {topic}: broker not available (retrying)",
            "webhook to merchant {id} permanently failed after 5 attempts, marking undeliverable",
            "unhandled exception in {job}: KeyError 'sku' in payload offset={offset}",
        ],
        "critical": [
            "worker {pod} exited with code 137 (SIGKILL) during {job}",
        ],
    },
    "datastore": {
        "info": [
            "checkpoint complete: wrote {n} buffers ({pct}%), {sec}s total",
            "automatic vacuum of table \"{table}\": removed {n} dead row versions",
            "automatic analyze of table \"{table}\" complete",
            "connection received: host={host} port={port}",
            "connection authorized: user=app_{svc} database=tigerlily ssl=on",
            "disconnection: session time: 0:{min}:{sec2}.{ms} user=app_{svc}",
            "replication slot replica_{region} confirmed flush lsn {lsn}",
            "redis: {n} keys, {mb}MB used, hit_rate={pct}.{n2}%, evicted_keys=0",
            "redis: RDB snapshot saved to disk in {sec}s",
            "kafka: partition {topic}-{partition} leader elected broker-{n2}",
            "kafka: ISR for {topic}-{partition} expanded to [1,2,3]",
            "kafka: log segment rolled for {topic}-{partition}",
            "wal archiving: archived segment {lsn}",
            "cache hit ratio for shared buffers: {pct}.{n2}%",
        ],
        "warning": [
            "duration: {slow_ms}.{ms} ms  statement: SELECT ... FROM {table} WHERE ... (slow query, >1000ms)",
            "temporary file: path \"base/pgsql_tmp/pgsql_tmp{id}\", size {mb}MB",
            "checkpoints are occurring too frequently ({n} seconds apart)",
            "redis: {n} slow commands logged in last 60s (slowlog threshold 10ms)",
            "kafka: under-replicated partitions: {n2} for topic {topic}",
            "active connections at {pct}% of max_connections",
            "lock wait on relation {table}: waited {slow_ms}ms for ShareLock",
            "autovacuum: table \"{table}\" has {n} dead tuples pending",
        ],
        "error": [
            "could not serialize access due to concurrent update on {table}",
            "deadlock detected: process {id} waits for ShareLock on transaction {n}; blocked by process {id2}",
            "redis: client connection reset by peer client_id={id}",
            "kafka: failed to append records to {topic}-{partition}: NotLeaderForPartition (transient)",
        ],
        "critical": [
            "terminating connection due to administrator command",
        ],
    },
    "infra": {
        "info": [
            "route match host=api.tigerlily.example path={path} upstream={dep} status=200 {ms}ms",
            "TLS 1.3 handshake complete cipher=TLS_AES_256_GCM_SHA384 sni=api.tigerlily.example",
            "upstream health check passed for {dep} ({n}/{n} healthy)",
            "rate limiter: {n} requests allowed, 0 rejected for key bucket=anon-{region}",
            "config reload complete, {n} routes, {n2} upstreams",
            "HPA {dep}: current replicas {n}, desired {n}, cpu utilization {pct}%",
            "autoscaler scaled {dep} from {n} to {n_plus} replicas (cpu {pct}%)",
            "cert-manager: certificate api-tigerlily-tls is valid for {days} more days",
            "WAF: {n} requests inspected, 0 blocked",
            "access log: {ip} - GET {path} 200 {bytes} \"tigerlily-web/2.{n2}\" {ms}ms",
        ],
        "warning": [
            "upstream {dep} health check failed 1/3 (timeout after 2s), still in rotation",
            "route {path} 499 client closed request before upstream responded",
            "rate limiter: {n} requests rejected for key bucket=api-{sha4} in last 60s",
            "HPA {dep} at max replicas ({n}), cannot scale further",
            "WAF: blocked {n} requests matching rule SQLi-942100 from {ip}",
            "upstream {dep} response time p99 {slow_ms}ms exceeds SLO 800ms",
            "TLS: client offered deprecated protocol TLS 1.0 from {ip}, rejected",
        ],
        "error": [
            "upstream {dep} returned 502 for {path}, retried on next replica",
            "route {path} 504 upstream {dep} timed out after 30s trace={trace}",
            "DNS resolution for {dep}.svc.cluster.local took {slow_ms}ms",
        ],
        "critical": [
            "no healthy upstreams for {dep}, returning 503 to all clients",
        ],
    },
}

DOWNSTREAMS = {
    "checkout-api": ["payments", "cart-service", "inventory", "postgres", "auth-service"],
    "payments": ["postgres", "payment-processor", "billing", "kafka"],
    "billing": ["postgres", "payment-processor", "kafka"],
    "cart-service": ["redis-cache", "catalog-api", "postgres"],
    "catalog-api": ["postgres", "redis-cache", "image-resizer"],
    "search-api": ["postgres", "catalog-api", "redis-cache"],
    "recommendations": ["embedding-worker", "postgres", "redis-cache"],
    "embedding-worker": ["postgres", "kafka", "object-store"],
    "inventory": ["postgres", "kafka"],
    "order-service": ["postgres", "kafka", "inventory", "notifications"],
    "notifications": ["kafka", "email-provider", "sms-provider"],
    "auth-service": ["postgres", "redis-cache", "user-profile"],
    "user-profile": ["postgres", "redis-cache"],
    "image-resizer": ["object-store", "cdn"],
    "scheduler": ["postgres", "kafka"],
    "api-gateway": ["checkout-api", "catalog-api", "search-api", "auth-service", "cart-service"],
    "edge-proxy": ["api-gateway", "image-resizer"],
    "postgres": [],
    "redis-cache": [],
    "kafka": [],
}

TABLES = ["orders", "order_items", "carts", "cart_items", "products", "product_variants",
          "inventory_levels", "payments", "payment_attempts", "users", "sessions",
          "addresses", "notifications_outbox", "audit_log", "price_history"]

TOPICS = ["orders.created", "orders.updated", "payments.captured", "inventory.reserved",
          "cart.abandoned", "notifications.email", "catalog.product-updated", "search.reindex"]

JOBS = {
    "billing": ["invoice-generation", "settlement-reconcile", "refund-sweep"],
    "embedding-worker": ["embed-product-batch", "embed-query-log", "refresh-similar-items"],
    "order-service": ["order-fulfillment", "order-status-sync", "backorder-release"],
    "notifications": ["email-dispatch", "sms-dispatch", "digest-builder"],
    "image-resizer": ["resize-product-images", "purge-orphan-renditions"],
    "scheduler": ["inventory-reconcile", "abandoned-cart-sweep", "price-history-rollup", "session-cleanup"],
}

# Plausible change summaries for routine deployments, by service kind.
DEPLOY_SUMMARIES = {
    "http_api": [
        "Bump {lang} base image and rebuild",
        "Add structured logging fields for trace and span ids",
        "Tighten request validation on {path}",
        "Increase default page size for list endpoints to 50",
        "Cache {dep} responses for 30s to reduce load",
        "Add p99 latency histogram buckets to metrics",
        "Refactor handler middleware chain, no behavior change",
        "Return 422 instead of 400 for semantic validation errors",
        "Upgrade OpenTelemetry SDK to latest minor",
        "Remove deprecated v0 endpoints",
        "Add readiness gate on {dep} connectivity",
        "Fix off-by-one in pagination cursor encoding",
        "Reduce connection pool idle timeout to 5m",
        "Add rate limit headers to responses",
        "Localize error messages for de-DE and fr-FR",
    ],
    "worker": [
        "Increase consumer concurrency from 4 to 8",
        "Add dead-letter queue handling for {topic}",
        "Batch writes to {table} in groups of 500",
        "Add idempotency key check before processing",
        "Upgrade Kafka client library",
        "Emit lag metric per partition",
        "Retry transient DB errors with jittered backoff",
        "Fix memory growth in {job} by clearing per-batch cache",
        "Add graceful shutdown drain with 30s timeout",
        "Move {job} schedule from hourly to every 15 minutes",
    ],
    "datastore": [
        "Apply weekly minor version patch",
        "Tune autovacuum settings for {table}",
        "Add index on {table}(created_at)",
        "Rotate replication credentials",
        "Increase shared_buffers to 25% of memory",
        "Enable pg_stat_statements",
        "Adjust redis maxmemory-policy to allkeys-lru",
        "Increase kafka retention for {topic} to 7d",
    ],
    "infra": [
        "Update routing rules for /v2 catalog endpoints",
        "Rotate edge TLS certificate",
        "Increase upstream timeout for search-api to 5s",
        "Add WAF rule for known scanner user agents",
        "Tune HPA target CPU from 70% to 60%",
        "Enable HTTP/3 on edge listeners",
        "Add canary weight support to route config",
        "Upgrade envoy to latest stable",
        "Add per-tenant rate limit buckets",
    ],
}

PEOPLE = [
    "amara.okafor", "diego.fernandez", "priya.raman", "jonas.lindqvist", "mei.tanaka",
    "samuel.adeyemi", "lucia.moretti", "kwame.mensah", "hannah.weiss", "rafael.souza",
    "yuki.nakamura", "fatima.alrashid", "tomasz.kowalski", "nia.johnson", "arjun.patel",
    "sofia.andersson", "omar.haddad", "chloe.dubois", "daniel.kim", "ingrid.olsen",
]

TEAM_ONCALL = {
    "payments-platform": ["amara.okafor", "diego.fernandez", "kwame.mensah"],
    "storefront": ["priya.raman", "lucia.moretti", "chloe.dubois"],
    "discovery": ["jonas.lindqvist", "arjun.patel", "sofia.andersson"],
    "fulfillment": ["mei.tanaka", "rafael.souza", "daniel.kim"],
    "growth": ["samuel.adeyemi", "nia.johnson"],
    "identity": ["hannah.weiss", "omar.haddad"],
    "platform-infra": ["yuki.nakamura", "tomasz.kowalski", "ingrid.olsen"],
    "data-infra": ["fatima.alrashid", "daniel.kim", "tomasz.kowalski"],
}
