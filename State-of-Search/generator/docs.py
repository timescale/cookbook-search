"""
Non-incident documents: on-call handbook and per-service architecture notes.
These give the documents table realistic "background" passages so semantic
search has plausible near-misses to rank against runbooks and postmortems.
"""

HANDBOOK = [
    ("On-call handbook", "Severity levels",
     "SEV1: customer-facing outage or data loss affecting most users, for example checkout unavailable or the public API down. Page the on-call and an incident commander immediately, open a status page entry within 15 minutes. SEV2: significant degradation for a subset of users or a tier-1 service running with reduced capacity. Page the owning team. SEV3: minor impact, delayed processing, or elevated error rates within SLO. Handle during business hours. Severity can be raised at any time and should be lowered only by the incident commander."),
    ("On-call handbook", "Declaring an incident",
     "Anyone can declare an incident. Run /incident declare in Slack with a one-line summary; the bot creates the channel, assigns the on-call as interim commander, and starts the timeline. Post what you see, not what you think caused it. Link the firing alerts. If a deploy happened in the last hour to any involved service, say so in the first message."),
    ("On-call handbook", "Roles",
     "Incident commander owns decisions and communication and does not debug. Operations lead runs the technical investigation and mitigation. Communications lead updates the status page and stakeholder channel every 30 minutes for SEV1 and every hour for SEV2. Scribe keeps the timeline in the incident channel. In small incidents one person may hold several roles, but the commander should always be named."),
    ("On-call handbook", "Rollback first",
     "If a deploy to any involved service happened within the last hour, roll it back before investigating further. Rollbacks are cheap and reversible; debugging under pressure is neither. The deploy tool supports tigerlily-deploy rollback <service> --to <version> and completes in two to three minutes for most services. Schema migrations are the exception: check the migration notes before rolling back a service whose deploy included one."),
    ("On-call handbook", "Communication cadence",
     "Post an update in the incident channel at least every 15 minutes during active mitigation, even if the update is 'no change, still investigating X'. Status page updates use the templates in the comms folder. Never promise a resolution time. When mitigated, say mitigated, not resolved; resolved means the root cause is fixed."),
    ("On-call handbook", "Escalation paths",
     "Each team has a primary and secondary on-call in the pager tool. If the primary does not acknowledge within 5 minutes, the page escalates to the secondary, then to the team lead. For cross-cutting infrastructure (Kubernetes, networking, DNS, mesh) page platform-infra. For databases, Redis, and Kafka page data-infra. For vendor issues, the commander opens the vendor case; do not wait for the vendor before mitigating on our side."),
    ("On-call handbook", "Postmortem timing",
     "Every SEV1 and SEV2 gets a blameless postmortem within five business days. The postmortem owner is the operations lead unless reassigned. Use the template in the postmortems folder: summary, timeline, root cause, contributing factors, impact, what went well, action items with owners and due dates. Action items are tracked as GitHub issues labeled postmortem-action-item and reviewed weekly."),
    ("On-call handbook", "Handover checklist",
     "Before ending your on-call shift: review open incidents and their status, note any alerts you silenced and when the silence expires, list deploys scheduled during the next shift, and post the handover summary in the team channel. If an incident is still active, do a verbal handover with the incoming on-call rather than a written one."),
    ("On-call handbook", "Alert hygiene",
     "An alert that fires and needs no action is a bug in the alert. If you acknowledge an alert and take no action, open an issue to tune or delete it before your shift ends. Warning-level alerts route to Slack; critical alerts page. If a warning should have paged, change its severity rather than adding a second alert."),
    ("On-call handbook", "Change freeze",
     "Production deploys are frozen during the two highest-traffic weeks of the year and during any active SEV1. Emergency fixes during a freeze need approval from the incident commander or the on-call platform lead. Flag changes count as deploys for the purpose of the freeze."),
    ("On-call handbook", "Useful queries",
     "Connections by app: SELECT application_name, state, count(*) FROM pg_stat_activity GROUP BY 1,2 ORDER BY 3 DESC. Blockers: SELECT pid, pg_blocking_pids(pid), left(query,60) FROM pg_stat_activity WHERE cardinality(pg_blocking_pids(pid)) > 0. Replica lag: SELECT now() - pg_last_xact_replay_timestamp(). Kafka lag: kafka-consumer-groups --describe --group <group>. Evictions: kubectl get events -A --field-selector reason=Evicted."),
    ("On-call handbook", "Kubernetes quick reference",
     "Crash loops: kubectl logs --previous <pod>. Evictions and pressure: kubectl describe node <node> and look at Conditions and Allocated resources. Stuck rollouts: kubectl rollout status deploy/<name> and kubectl rollout undo. Resource hogs: kubectl top pod -A --sort-by=memory. DNS: run a debug pod and dig <service>.<namespace>.svc.cluster.local."),
]

# (title, section, template) per service. {service} and {team} are filled.
ARCH_SECTIONS = [
    ("Overview", "{service} is owned by {team} and written in {lang}. It runs in the {namespace} namespace with {replicas} replicas in production behind the API gateway. Its primary dependencies are {deps}. Traffic peaks at roughly {rps} requests per second during US evening hours."),
    ("Data storage", "{service} stores its durable state in the shared Postgres primary (schema {schema}) and uses Redis for short-lived caching with TTLs between 30 seconds and 2 hours. It does not own any tables outside its schema. Cross-service reads go through APIs, never through shared tables."),
    ("Scaling and limits", "Production runs {replicas} replicas with an HPA targeting 60% CPU, minimum {min_replicas}, maximum {max_replicas}. Each replica requests {cpu}m CPU and {mem}Mi memory with a limit of {mem_limit}Mi. Connection pool to Postgres is capped at {pool} per replica. Scale-down stabilization is 300 seconds."),
    ("Failure modes", "Known failure modes for {service}: loss of the Postgres primary (fails all writes), Redis unavailability (falls back to direct reads with higher latency), and slow downstream {dep} (circuit breaker opens after 20% failures over 30 seconds). Deploys use canary promotion with a 1% error-rate threshold over 15 minutes."),
    ("Observability", "{service} emits structured JSON logs with trace_id, span_id, and request path. Metrics follow the RED pattern (rate, errors, duration) per endpoint. Alerts: {alert_prefix}ErrorRateHigh at 2% over 5 minutes (page), {alert_prefix}LatencyP99 at 800ms (page), and pool utilization at 80% (warning). Dashboards live under the {team} folder."),
]
