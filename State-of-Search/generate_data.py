#!/usr/bin/env python3
"""
generate_data.py -- regenerate the Incident-search sample dataset.

Produces six CSV files that model an SRE "incident memory" for a fictional
e-commerce platform (tigerlily): routine logs, Kubernetes events and alerts,
incident storylines that unfold in phases, deployments (some of which cause
incidents), runbooks, postmortems, architecture notes, GitHub issues with
comments, and a set of labeled search questions for measuring recall.

    data/events.csv             ~250k timestamped events with JSON metadata
    data/deployments.csv        ~5k deployment records
    data/documents.csv          runbooks, postmortems, handbook, architecture, ops reviews
    data/github_issues.csv      postmortem action items plus routine engineering issues
    data/issue_comments.csv     comments on those issues
    data/labeled_questions.csv  100 questions with expected incident families and IDs

Everything is driven by the seed/ folder, which holds the incident families
(twenty failure modes such as connection-pool exhaustion, expired TLS
certificates, Kafka consumer lag), their event templates by phase, runbook and
postmortem text, issue templates, and the vocabulary for background traffic.
Edit the seed to add or change a failure mode; run this script to get a fresh,
internally consistent dataset.

Usage:
    uv run python generate_data.py                       # defaults reproduce the shipped shape
    uv run python generate_data.py --events 50000 --deployments 1000 --incidents 20
    uv run python generate_data.py --start 2027-01-04 --days 60 --seed 7 --out data

The output is deterministic for a given seed and set of options. It needs only
the Python standard library.
"""
import argparse
import bisect
import collections
import csv
import json
import math
import random
import re
import string
from datetime import datetime, timedelta
from pathlib import Path

PHASES = ["precursor", "onset", "peak", "mitigation", "recovery"]
HEX = "0123456789abcdef"
ALNUM = string.ascii_lowercase + string.digits


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def fmt_ms(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S.") + "%03d+00" % (dt.microsecond // 1000)


def fmt_s(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S.000+00")


def pg_array(items):
    return "{" + ",".join('"%s"' % i for i in items) + "}"


def weighted(rng, mapping):
    """Pick a key from {key: weight}."""
    keys = list(mapping)
    return rng.choices(keys, weights=[mapping[k] for k in keys], k=1)[0]


def spread(rng, lo, hi):
    return rng.randint(lo, hi) if lo <= hi else lo


class Filler:
    """Fill <<placeholders>> in a template string."""

    def __init__(self, rng, regions, vocab):
        self.rng = rng
        self.regions = regions
        self.vocab = vocab

    def hexs(self, n):
        return "".join(self.rng.choice(HEX) for _ in range(n))

    def pod(self, service):
        return "%s-%s-%s" % (service, self.hexs(9), "".join(self.rng.choice(ALNUM) for _ in range(5)))

    def node(self, region):
        r = self.rng
        return "ip-10-%d-%d-%d.%s.compute.internal" % (r.randint(0, 3), r.randint(0, 255), r.randint(1, 254), region)

    def ip(self):
        r = self.rng
        return "%d.%d.%d.%d" % (r.randint(1, 223), r.randint(0, 255), r.randint(0, 255), r.randint(1, 254))

    def jitter(self, value, before="", after=""):
        """Vary a sampled measurement a little. Leave identifiers alone:
        codes (SQLSTATE, HTTP status, percentile labels), ports, API version
        segments, round thresholds and anything preceded by a letter or slash."""
        r = self.rng
        if before and (before[-1].isalpha() or before[-1] in "/:._-#"):
            return value
        if "." in value:
            try:
                f = float(value)
            except ValueError:
                return value
            dec = len(value.split(".")[1])
            return ("%%.%df" % dec) % max(0.0, f * r.uniform(0.9, 1.1))
        try:
            n = int(value)
        except ValueError:
            return value
        if n < 20 or n % 10 == 0 or 100 <= n <= 599 or value.startswith("0"):
            return value
        return str(max(1, int(round(n * r.uniform(0.9, 1.1)))))

    def fill(self, template, ctx, samples=None):
        """ctx: dict with optional keys region, oregion, inc, dep, person,
        ver, ver_new, ver_old, when (datetime), service."""
        r = self.rng
        t = template
        if "<<" not in t:
            return t
        when = ctx.get("when")
        region = ctx.get("region") or r.choice(self.regions)
        rep = {
            "<<trace>>": lambda: ctx.get("trace") or self.hexs(32),
            "<<sha>>": lambda: self.hexs(7),
            "<<hexkey>>": lambda: "api-" + self.hexs(4),
            "<<ip>>": self.ip,
            "<<node>>": lambda: ctx.get("node") or "ip-10-%d-%d-%d" % (r.randint(0, 3), r.randint(0, 255), r.randint(1, 254)),
            "<<region>>": lambda: region,
            "<<oregion>>": lambda: r.choice([x for x in self.regions if x != region]),
            "<<inc>>": lambda: ctx.get("inc", "INC-0000-0000"),
            "<<dep>>": lambda: ctx.get("dep", "dep-000000"),
            "<<person>>": lambda: ctx.get("person", "on-call"),
            "<<ver_new>>": lambda: ctx.get("ver_new") or ctx.get("ver", "1.0.0"),
            "<<ver_old>>": lambda: ctx.get("ver_old") or ctx.get("ver", "1.0.0"),
            "<<ver>>": lambda: ctx.get("ver", "1.0.0"),
            "<<iso>>": lambda: (when or datetime(2026, 1, 1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "<<date>>": lambda: (when or datetime(2026, 1, 1)).strftime("%Y-%m-%d"),
            "<<time>>": lambda: (when or datetime(2026, 1, 1)).strftime("%H:%M"),
            "<<lsn>>": lambda: "%X/%08X" % (r.randint(1, 40), r.randint(0, 0xFFFFFFFF)),
            "<<walseg>>": lambda: "%08X%08X%08X" % (1, r.randint(1, 4000), r.randint(0, 255)),
            "<<table>>": lambda: r.choice(self.vocab.get("table") or ["orders"]),
            "<<topic>>": lambda: r.choice(self.vocab.get("topic") or ["orders.created"]),
            "<<job>>": lambda: r.choice(self.vocab.get("job") or ["nightly-rollup"]),
        }
        for key, fn in rep.items():
            while key in t:
                t = t.replace(key, fn(), 1)
        # pods carry their service name
        while "<<pod:" in t:
            i = t.index("<<pod:")
            j = t.index(">>", i)
            service = t[i + 6:j]
            pod = ctx.get("pod") if service == ctx.get("service") else None
            t = t[:i] + (pod or self.pod(service)) + t[j + 2:]
        # numbers: take one observed tuple and jitter it
        if "<<n>>" in t:
            parts = t.split("<<n>>")
            need = len(parts) - 1
            vals = list(r.choice(samples)) if samples else []
            if len(vals) < need:
                vals += [str(r.randint(1, 999)) for _ in range(need - len(vals))]
            out = parts[0]
            for k in range(need):
                out += self.jitter(vals[k], out[-2:], parts[k + 1][:1]) + parts[k + 1]
            t = out
        return t


# --------------------------------------------------------------------------
class Generator:
    def __init__(self, args):
        self.args = args
        self.rng = random.Random(args.seed)
        seed = Path(args.seed_dir)
        self.families = json.load(open(seed / "families.json"))
        self.routine = json.load(open(seed / "routine_templates.json"))
        sv = json.load(open(seed / "services.json"))
        self.services = sv["services"]
        self.people = sv["people"]              # name -> team
        self.regions = sv["regions"]
        self.vocab = sv.get("vocab", {})
        self.deploy_seed = json.load(open(seed / "deployments.json"))
        self.events_seed = json.load(open(seed / "events.json"))
        self.docs_seed = json.load(open(seed / "documents.json"))
        self.issues_seed = json.load(open(seed / "issues.json"))
        self.questions_seed = json.load(open(seed / "questions.json"))
        self.fill = Filler(self.rng, self.regions, self.vocab)

        self.start = datetime.strptime(args.start, "%Y-%m-%d")
        self.end = self.start + timedelta(days=args.days)
        self.year = self.start.year
        self.team_people = collections.defaultdict(list)
        for p, t in self.people.items():
            self.team_people[t].append(p)
        # Persistent infrastructure makes correlations useful: many events
        # come from the same pods and nodes, as they would in a real cluster.
        self.node_pools = {
            region: [self.fill.node(region) for _ in range(12)]
            for region in self.regions
        }
        self.pod_pools = {}
        self.incident_traces = {}

    def event_identity(self, service, environment, region, version):
        """Return a reusable pod/node pair for a deployed service version."""
        key = (service, environment, region, version)
        if key not in self.pod_pools:
            replicas = max(2, min(8, round(self.services[service]["event_weight"] / 4000)))
            self.pod_pools[key] = [
                (self.fill.pod(service), self.rng.choice(self.node_pools[region]))
                for _ in range(replicas)
            ]
        return self.rng.choice(self.pod_pools[key])

    def incident_trace(self, incident_id, when):
        """Reuse a trace across nearby cross-service incident signals."""
        bucket = int(when.timestamp()) // 30
        return self.incident_traces.setdefault((incident_id, bucket), self.fill.hexs(32))

    @staticmethod
    def allocate_counts(total, weights):
        """Allocate an exact total with largest remainders."""
        weight_total = sum(weights)
        raw = [total * weight / weight_total for weight in weights]
        counts = [int(value) for value in raw]
        remainder = total - sum(counts)
        order = sorted(
            range(len(raw)), key=lambda n: raw[n] - counts[n], reverse=True
        )
        for i in order[:remainder]:
            counts[i] += 1
        return counts

    # ---------------------------------------------------------------- time
    def random_time(self, lo, hi, hour_weights, weekday_weights):
        """A random moment in [lo, hi) following hour-of-day and weekday weights."""
        r = self.rng
        days = max(1, (hi - lo).days)
        for _ in range(200):
            d = lo + timedelta(days=r.randrange(days))
            if r.random() * max(weekday_weights) <= weekday_weights[d.weekday()]:
                break
        hour = r.choices(range(24), weights=hour_weights, k=1)[0]
        return d.replace(hour=hour, minute=r.randrange(60), second=r.randrange(60), microsecond=r.randrange(1000) * 1000)

    # ----------------------------------------------------------- incidents
    def plan_incidents(self):
        r = self.rng
        fams = list(self.families)
        total_ref = sum(self.families[f]["incident_count"] for f in fams)
        target = self.args.incidents
        # largest-remainder allocation, at least one incident per family
        raw = {f: self.families[f]["incident_count"] * target / total_ref for f in fams}
        counts = {f: max(1, int(raw[f])) for f in fams}
        while sum(counts.values()) < target:
            f = max(fams, key=lambda x: raw[x] - counts[x])
            counts[f] += 1
        while sum(counts.values()) > target:
            f = max((x for x in fams if counts[x] > 1), key=lambda x: counts[x] - raw[x], default=None)
            if f is None:
                break
            counts[f] -= 1

        incidents = []
        n = 0
        hour_w = self.events_seed["hour_weights"]
        wd_w = [1] * 7
        lo = self.start + timedelta(days=1)
        hi = self.end - timedelta(days=1)
        for f in fams:
            fam = self.families[f]
            for _ in range(counts[f]):
                n += 1
                start = self.random_time(lo, hi, hour_w, wd_w)
                dur = timedelta(minutes=spread(r, *fam["duration_minutes"]))
                cmd = r.choices([c[0] for c in fam["commanders"]], weights=[c[2] for c in fam["commanders"]], k=1)[0]
                team = dict((c[0], c[1]) for c in fam["commanders"])[cmd]
                incidents.append({
                    "id": "INC-%d-%04d" % (self.year, n),
                    "family": f,
                    "start": start,
                    "end": start + dur,
                    "duration_min": int(dur.total_seconds() // 60),
                    "region": weighted(r, fam["regions"]),
                    "commander": cmd,
                    "team": team,
                    "severity": fam["severity"],
                    "rows": spread(r, *fam["rows_per_incident"]),
                    "trigger": None,
                    "fix": None,
                })
        # keep two incidents of the same family at least two days apart
        by_fam = collections.defaultdict(list)
        for inc in incidents:
            by_fam[inc["family"]].append(inc)
        for lst in by_fam.values():
            lst.sort(key=lambda x: x["start"])
            for a, b in zip(lst, lst[1:]):
                if b["start"] - a["start"] < timedelta(days=2):
                    shift = timedelta(days=2) - (b["start"] - a["start"])
                    b["start"] = min(b["start"] + shift, hi)
                    b["end"] = b["start"] + timedelta(minutes=b["duration_min"])
        scale = self.args.events / 250000.0
        for inc in incidents:
            inc["rows"] = max(40, int(inc["rows"] * scale))
        self.incidents = incidents
        return incidents

    # --------------------------------------------------------- deployments
    def build_deployments(self):
        r = self.rng
        ds = self.deploy_seed
        dep_lo = self.start - timedelta(days=3)
        slots = []
        svc_w = {s: v["deploy_weight"] for s, v in self.services.items()}
        for _ in range(self.args.deployments):
            slots.append({
                "service": weighted(r, svc_w),
                "environment": weighted(r, ds["environments"]),
                "at": self.random_time(dep_lo, self.end, ds["hour_weights"], ds["weekday_weights"]).replace(microsecond=0),
                "kind": "normal",
            })
        # incident-linked deploys
        for inc in self.incidents:
            fam = self.families[inc["family"]]
            trig = fam.get("trigger_deploy")
            if not trig:
                continue
            before = timedelta(minutes=spread(r, *trig["minutes_before"]))
            slot = {
                "service": trig["service"], "environment": "production",
                "at": (inc["start"] - before).replace(microsecond=0), "kind": "trigger", "incident": inc,
                "status": trig["status"], "strategy": trig["strategy"], "summary": trig["change_summary"],
            }
            slots.append(slot)
            inc["trigger"] = slot
            fix = fam.get("fix_deploy")
            if fix:
                if fix["when"] == "mitigation":
                    at = inc["start"] + (inc["end"] - inc["start"]) * 0.72
                else:
                    at = inc["end"] + timedelta(minutes=spread(r, *fix["minutes_after_end"]))
                # rollback re-releases the previous version, a redeploy ships the same
                # version again once config is fixed, anything else is a new build
                if fix["rollback"]:
                    kind = "rollback"
                elif "<<ver_new>>" in fix["change_summary"]:
                    kind = "redeploy"
                else:
                    kind = "fix"
                fslot = {
                    "service": trig["service"], "environment": "production", "at": at.replace(microsecond=0),
                    "kind": kind,
                    "incident": inc, "status": "succeeded", "strategy": trig["strategy"], "summary": fix["change_summary"],
                }
                slots.append(fslot)
                inc["fix"] = fslot

        slots.sort(key=lambda s: s["at"])
        # version streams per service
        cur = {}
        for s, v in self.services.items():
            cur[s] = [v["major"], r.randint(0, 24), r.randint(0, 9)]
        summaries = ds["change_summaries"]
        summ_text = [s[0] for s in summaries]
        summ_w = [s[1] for s in summaries]
        rows = []
        for i, s in enumerate(slots, 1):
            svc = s["service"]
            v = cur[svc]
            kind = s["kind"]
            if kind == "rollback":
                inc = s["incident"]
                version, prev = inc["ver_old"], inc["ver_new"]
            elif kind == "redeploy":
                inc = s["incident"]
                version, prev = inc["ver_new"], inc["ver_old"]
            else:
                prev = "%d.%d.%d" % tuple(v)
                if r.random() < 0.15:
                    v[1] += 1
                    v[2] = 0
                else:
                    v[2] += 1
                version = "%d.%d.%d" % tuple(v)
            if kind == "trigger":
                s["incident"]["ver_new"] = version
                s["incident"]["ver_old"] = prev
            team = self.services[svc]["team"]
            people = self.team_people.get(team) or list(self.people)
            deployer = r.choice(people) if r.random() < 0.85 else r.choice(list(self.people))
            if kind == "normal":
                status = weighted(r, ds["statuses"])
                strategy = weighted(r, ds["strategies"])
                summary = r.choices(summ_text, weights=summ_w, k=1)[0]
                while "<<n>>" in summary:
                    summary = summary.replace("<<n>>", str(r.randint(10000, 999999)), 1)
            else:
                status, strategy = s["status"], s["strategy"]
                inc = s["incident"]
                summary = (s["summary"].replace("<<inc>>", inc["id"]).replace("<<ver_old>>", inc["ver_old"])
                           .replace("<<ver_new>>", inc["ver_new"]).replace("<<ver_next>>", version))
            dep_id = "dep-%06d" % i
            s["deploy_id"] = dep_id
            s["version"] = version
            s["status"] = status
            rows.append({
                "deploy_id": dep_id, "deployed_at": fmt_s(s["at"]), "service": svc, "environment": s["environment"],
                "version": version, "previous_version": prev, "git_sha": self.fill.hexs(40), "deployer": deployer,
                "strategy": strategy, "status": status,
                "duration_seconds": r.randint(*ds["duration_seconds"]),
                "change_summary": summary,
                "metadata": json.dumps({"pr_number": r.randint(100, 5000), "commits": r.randint(1, 12),
                                        "pipeline": ds["pipeline"], "team": team}, separators=(",", ":")),
            })
        # Version lookup by service and environment. Staging and development
        # logs should not silently inherit the production deployment stream.
        self.version_index = collections.defaultdict(lambda: ([], []))
        for s in slots:
            if s["status"] != "failed":
                ts_, vs = self.version_index[(s["service"], s["environment"])]
                ts_.append(s["at"])
                vs.append(s["version"])
        self.initial_version = {s: "%d.%d.%d" % (v["major"], 0, 0) for s, v in self.services.items()}
        self.deployments = rows
        return rows

    def version_at(self, service, when, environment="production"):
        ts_, vs = self.version_index[(service, environment)]
        i = bisect.bisect_right(ts_, when) - 1
        return vs[i] if i >= 0 else self.initial_version[service]

    # ----------------------------------------------------------------- events
    def build_events(self):
        r = self.rng
        es = self.events_seed
        rows = []
        inc_rows = sum(inc["rows"] for inc in self.incidents)
        routine_n = max(0, self.args.events - inc_rows)

        # --- routine background traffic
        svc_w = {s: v["event_weight"] for s, v in self.services.items()}
        svc_list = list(svc_w)
        svc_weights = [svc_w[s] for s in svc_list]
        tpl_cache = {s: ([t for t in self.routine[s]], [t["weight"] for t in self.routine[s]]) for s in svc_list if s in self.routine}
        env_keys = list(es["environments"])
        env_w = [es["environments"][k] for k in env_keys]
        reg_keys = list(es["regions"])
        reg_w = [es["regions"][k] for k in reg_keys]
        lat_lo, lat_hi = es["latency_ms_range"]
        for _ in range(routine_n):
            svc = r.choices(svc_list, weights=svc_weights, k=1)[0]
            if svc not in tpl_cache:
                continue
            tpls, tw = tpl_cache[svc]
            tpl = r.choices(tpls, weights=tw, k=1)[0]
            when = self.random_time(self.start, self.end, es["hour_weights"], es["weekday_weights"])
            region = r.choices(reg_keys, weights=reg_w, k=1)[0]
            environment = r.choices(env_keys, weights=env_w, k=1)[0]
            ver = self.version_at(svc, when, environment)
            pod, node = self.event_identity(svc, environment, region, ver)
            trace = self.fill.hexs(32)
            ctx = {
                "region": region, "when": when, "ver": ver, "service": svc,
                "pod": pod, "node": node, "trace": trace,
            }
            content = self.fill.fill(tpl["template"], ctx, tpl["samples"])
            meta = {"pod": pod, "node": node, "trace_id": trace, "version": ver}
            if tpl.get("latency"):
                meta["latency_ms"] = r.randint(lat_lo, lat_hi)
            rows.append((when, svc, environment, tpl["severity"], tpl["event_type"],
                         region, tpl["error_code"], "", content, json.dumps(meta, separators=(",", ":"))))

        # --- incident storylines
        phase_model = es["phases"]
        for inc in self.incidents:
            fam = self.families[inc["family"]]
            tpls_by_phase = collections.defaultdict(list)
            for t in fam["event_templates"]:
                tpls_by_phase[t["phase"]].append(t)
            total = (inc["end"] - inc["start"]).total_seconds()
            # phase windows: proportional to time fractions, with small gaps between
            fracs = [phase_model[p]["time_fraction"] for p in PHASES]
            gap = (1.0 - sum(fracs)) / len(PHASES)
            cursor = 0.0
            phase_counts = self.allocate_counts(
                inc["rows"], [phase_model[p]["row_fraction"] for p in PHASES]
            )
            ctx_base = {
                "region": inc["region"], "inc": inc["id"], "person": inc["commander"],
                "dep": inc["trigger"]["deploy_id"] if inc["trigger"] else None,
                "ver_new": inc.get("ver_new"), "ver_old": inc.get("ver_old"),
            }
            for p, frac, n in zip(PHASES, fracs, phase_counts):
                p_start = inc["start"] + timedelta(seconds=total * cursor)
                p_end = inc["start"] + timedelta(seconds=total * (cursor + frac))
                cursor += frac + gap
                tpls = tpls_by_phase.get(p)
                if not tpls or n == 0:
                    continue
                tw = [t["weight"] for t in tpls]
                span = (p_end - p_start).total_seconds()
                times = sorted(p_start + timedelta(seconds=r.random() * span) for _ in range(n))
                if p == PHASES[0]:
                    times[0] = inc["start"]
                if p == PHASES[-1]:
                    times[-1] = inc["end"]
                for when in times:
                    t = r.choices(tpls, weights=tw, k=1)[0]
                    svc = t["service"]
                    ver = self.version_at(svc, when)
                    if inc["trigger"] and svc == inc["trigger"]["service"]:
                        ver = inc["ver_new"] if p in ("precursor", "onset", "peak") else inc["ver_old"] if inc["fix"] and inc["fix"]["kind"] == "rollback" else inc["ver_new"]
                    pod, node = self.event_identity(svc, "production", inc["region"], ver)
                    trace = self.incident_trace(inc["id"], when)
                    ctx = dict(
                        ctx_base, when=when, ver=ver, service=svc,
                        pod=pod, node=node, trace=trace,
                    )
                    content = self.fill.fill(t["template"], ctx, t["samples"])
                    meta = collections.OrderedDict()
                    meta["incident_id"] = inc["id"]
                    meta["incident_family"] = inc["family"]
                    meta["phase"] = p
                    meta["pod"] = pod
                    meta["node"] = node
                    meta["trace_id"] = trace
                    meta["version"] = ver
                    if t["event_type"] == "alert":
                        meta["alertname"] = t["alertname"]
                        meta["state"] = t["state"]
                    if inc["trigger"]:
                        meta["deploy_id"] = inc["trigger"]["deploy_id"]
                    rows.append((when, svc, "production", t["severity"], t["event_type"], inc["region"],
                                 t["error_code"], inc["id"], content, json.dumps(meta, separators=(",", ":"))))
        rows.sort(key=lambda x: x[0])
        self.events = rows
        return rows

    # -------------------------------------------------------------- documents
    def build_documents(self):
        r = self.rng
        docs = []
        doc_lo = self.start - timedelta(days=400)
        doc_hi = self.start - timedelta(days=30)

        def rand_day(lo, hi):
            return fmt_s((lo + timedelta(days=r.randrange((hi - lo).days))).replace(hour=0, minute=0, second=0, microsecond=0))

        def add(**kw):
            kw["doc_id"] = "doc-%05d" % (len(docs) + 1)
            docs.append(kw)

        for f, fam in self.families.items():
            for sec in fam["runbook"]:
                add(doc_type="runbook", title="Runbook: " + fam["title"], section=sec["section"],
                    service=fam["primary_service"], incident_family=f, incident_id="",
                    published_at=rand_day(doc_lo, doc_hi), content=sec["content"])

        went_well = self.docs_seed["went_well"]
        ww_text = [w[0] for w in went_well]
        ww_w = [w[1] for w in went_well]
        for inc in sorted(self.incidents, key=lambda x: x["start"]):
            fam = self.families[inc["family"]]
            pub = (inc["end"] + timedelta(hours=r.randint(48, 130))).replace(second=0, microsecond=0)
            dur = inc["end"] - inc["start"]
            t1 = inc["start"]
            t2 = inc["start"] + dur * r.uniform(0.18, 0.30)
            t3 = t2 + timedelta(minutes=r.randint(4, 9))
            t4 = inc["start"] + dur * r.uniform(0.68, 0.76)
            t5 = inc["end"] + timedelta(minutes=1)
            subs = {
                "<<inc>>": inc["id"], "<<region>>": inc["region"], "<<commander>>": inc["commander"],
                "<<team>>": inc["team"], "<<dep>>": inc["trigger"]["deploy_id"] if inc["trigger"] else "",
                "<<pm_date>>": pub.strftime("%Y-%m-%d"), "<<date>>": inc["start"].strftime("%Y-%m-%d"),
                "<<duration>>": str(inc["duration_min"]),
                "<<t1>>": t1.strftime("%H:%M"), "<<t2>>": t2.strftime("%H:%M"), "<<t3>>": t3.strftime("%H:%M"),
                "<<t4>>": t4.strftime("%H:%M"), "<<t5>>": t5.strftime("%H:%M"),
            }
            sections = []
            for sec in fam["postmortem"]:
                c = sec["content"]
                for k, v in subs.items():
                    c = c.replace(k, v)
                if "<<n>>" in c:
                    c = self.fill.fill(c, {}, sec.get("samples"))
                sections.append((sec["section"], c))
            # slot "What went well" before "Action items"
            out = []
            for name, c in sections:
                if name == "Action items":
                    out.append(("What went well", r.choices(ww_text, weights=ww_w, k=1)[0]))
                out.append((name, c))
            for name, c in out:
                add(doc_type="postmortem", title="Postmortem %s: %s" % (inc["id"], fam["title"]), section=name,
                    service=fam["primary_service"], incident_family=inc["family"], incident_id=inc["id"],
                    published_at=fmt_s(pub), content=c)

        for sec in self.docs_seed["handbook"]:
            add(doc_type="handbook", title="On-call handbook", section=sec["section"], service="", incident_family="",
                incident_id="", published_at=rand_day(doc_lo, doc_hi), content=sec["content"])
        for svc, secs in self.docs_seed["architecture"].items():
            for sec in secs:
                add(doc_type="architecture", title="Architecture notes: %s" % svc, section=sec["section"], service=svc,
                    incident_family="", incident_id="", published_at=rand_day(doc_lo, doc_hi), content=sec["content"])

        week = 0
        wk = self.start
        while wk < self.end:
            week += 1
            wk_end = wk + timedelta(days=7)
            incs = sorted((i for i in self.incidents if wk <= i["start"] < wk_end), key=lambda x: x["start"])
            if incs:
                body = "Incidents this week: " + "; ".join(
                    "%s (%s, %s): %s" % (i["id"], i["severity"], self.families[i["family"]]["primary_service"],
                                          self.families[i["family"]]["title"].lower()) for i in incs)
            else:
                body = "No incidents declared this week"
            tail = self.docs_seed["ops_review_tail"]
            tail = tail.replace("<<n>>", str(r.randint(2, 14)), 1).replace("<<n>>", str(r.randint(1, 8)), 1)
            add(doc_type="ops_review", title="Weekly ops review, week %d" % week, section="Week of %s" % wk.strftime("%Y-%m-%d"),
                service="", incident_family="", incident_id="", published_at=fmt_s(wk_end), content=body + tail)
            wk = wk_end
        self.documents = docs
        return docs

    # ----------------------------------------------------------------- issues
    def build_issues(self):
        r = self.rng
        iseed = self.issues_seed
        numbers = dict(iseed["repo_number_start"])
        issues = []

        def next_number(repo):
            numbers[repo] = numbers.get(repo, 100) + r.randint(1, 8)
            return numbers[repo]

        for inc in sorted(self.incidents, key=lambda x: x["start"]):
            fam = self.families[inc["family"]]
            tpls = fam["issues"]
            if not tpls:
                continue
            k = min(len(tpls), r.choice(fam["issues_per_incident"]))
            for t in r.sample(tpls, k):
                created = inc["end"] + timedelta(hours=spread(r, min(t["created_hours_after_end"]), max(t["created_hours_after_end"])))
                created = created.replace(second=0, microsecond=0)
                state = r.choice(t["states"])
                closed = ""
                if state == "closed":
                    days = r.choice(t["closed_days_after"]) if t["closed_days_after"] else r.randint(5, 20)
                    closed = fmt_s(created + timedelta(days=days))
                num = next_number(t["repo"])
                body = t["body"].replace("<<inc>>", inc["id"]).replace("<<dep>>", inc["trigger"]["deploy_id"] if inc["trigger"] else "the deploy")
                issues.append({
                    "issue_id": "%s#%d" % (t["repo"], num), "repo": t["repo"], "number": num, "title": t["title"], "body": body,
                    "state": state, "labels": t["labels"], "author": inc["commander"], "created_at": fmt_s(created),
                    "closed_at": closed, "incident_id": inc["id"], "incident_family": inc["family"],
                })

        tpls = list(iseed["routine_templates"])
        r.shuffle(tpls)
        lo = self.start - timedelta(days=60)
        for i in range(self.args.routine_issues):
            t = tpls[i % len(tpls)]
            created = self.random_time(lo, self.end, [1] * 24, [1] * 7)
            closed = ""
            state = "open"
            if r.random() < iseed["routine_closed_fraction"]:
                state = "closed"
                closed_dt = created + timedelta(days=r.randint(*iseed["routine_closed_days"]))
                closed = fmt_ms(closed_dt)
            num = next_number(t["repo"])
            issues.append({
                "issue_id": "%s#%d" % (t["repo"], num), "repo": t["repo"], "number": num, "title": t["title"], "body": t["body"],
                "state": state, "labels": t["labels"], "author": r.choice(list(self.people)), "created_at": fmt_ms(created),
                "closed_at": closed, "incident_id": "", "incident_family": "",
            })
        self.issues = issues
        return issues

    def build_comments(self):
        r = self.rng
        cs = self.issues_seed["comments"]
        generic = cs["generic"]
        g_text = [g[0] for g in generic]
        g_w = [g[1] for g in generic]
        dist_inc = {int(k): v for k, v in cs["count_dist_incident"].items()}
        dist_rou = {int(k): v for k, v in cs["count_dist_routine"].items()}
        lo_h, hi_h = cs["hours_after_issue"]
        people = list(self.people)
        services = list(self.services)
        out = []
        inc_by_id = {i["id"]: i for i in self.incidents}
        for iss in self.issues:
            n = weighted(r, dist_inc if iss["incident_id"] else dist_rou)
            if n == 0:
                continue
            created = datetime.strptime(iss["created_at"][:19], "%Y-%m-%d %H:%M:%S")
            offsets = sorted(r.randint(max(1, lo_h), hi_h) for _ in range(n))
            for off in offsets:
                author = r.choice([p for p in people if p != iss["author"]])
                roll = r.random()
                if iss["incident_id"] and roll < 0.18:
                    body = "Linking the postmortem doc for %s. Timeline and root cause are in there; this issue tracks the fix." % iss["incident_id"]
                elif roll < 0.28:
                    body = "Should we also cover the %s path? It has the same shape." % r.choice(services)
                elif roll < 0.36:
                    body = "Picked this up. Draft PR incoming this week. Will need a review from %s." % r.choice(people)
                elif roll < 0.44:
                    body = "PR #%d is up. Added a regression test that reproduces the failure mode from the incident." % r.randint(300, 5000)
                elif roll < 0.52:
                    svc = iss["repo"].split("/")[1]
                    ver = self.version_at(svc, created + timedelta(hours=off)) if svc in self.services else "%d.%d.%d" % (r.randint(1, 5), r.randint(0, 30), r.randint(0, 15))
                    body = "Deployed to production in %s. Watching the dashboards for 24h before closing." % ver
                else:
                    body = r.choices(g_text, weights=g_w, k=1)[0]
                out.append({"comment_id": len(out) + 1, "issue_id": iss["issue_id"], "author": author,
                            "created_at": fmt_s(created + timedelta(hours=off)), "body": body})
        self.comments = out
        return out

    # -------------------------------------------------------------- questions
    def build_questions(self):
        qs = []
        notes_tpl = self.questions_seed["notes_template"]
        by_fam = collections.defaultdict(list)
        for inc in self.incidents:
            by_fam[inc["family"]].append(inc["id"])
        for f, fam in self.families.items():
            ids = sorted(by_fam[f])
            for q in fam["questions"]:
                qs.append({
                    "question_id": len(qs) + 1, "question": q["question"], "query_kind": q["query_kind"],
                    "expected_family": f, "expected_incident_ids": pg_array(ids),
                    "expected_services": pg_array(fam["services"]),
                    "notes": notes_tpl.replace("<<family>>", f),
                })
        for q in self.questions_seed["global"]:
            if q["rule"] == "deploy_trigger":
                fams = [f for f, fam in self.families.items() if fam.get("trigger_deploy")]
            else:
                svc = q["rule"].split(":", 1)[1]
                fams = [f for f, fam in self.families.items() if svc in fam["services"]]
            ids = sorted(i for f in fams for i in by_fam[f])
            services = sorted({s for f in fams for s in self.families[f]["services"]})
            qs.append({
                "question_id": len(qs) + 1, "question": q["question"], "query_kind": q["query_kind"],
                "expected_family": "", "expected_incident_ids": pg_array(ids),
                "expected_services": pg_array(services), "notes": q["notes"],
            })
        self.questions = qs
        return qs

    # ------------------------------------------------------------------ write
    def write(self):
        out = Path(self.args.out)
        out.mkdir(parents=True, exist_ok=True)

        def dump(name, cols, rows):
            with open(out / name, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(cols)
                for row in rows:
                    w.writerow([row[c] for c in cols] if isinstance(row, dict) else row)
            print("wrote %-24s %7d rows" % (name, len(rows)))

        ev_cols = ["occurred_at", "service", "environment", "severity", "event_type", "region", "error_code", "incident_id", "content", "metadata"]
        dump("events.csv", ev_cols, [(fmt_ms(r[0]),) + r[1:] for r in self.events])
        dump("deployments.csv", ["deploy_id", "deployed_at", "service", "environment", "version", "previous_version", "git_sha",
                                 "deployer", "strategy", "status", "duration_seconds", "change_summary", "metadata"], self.deployments)
        dump("documents.csv", ["doc_id", "doc_type", "title", "section", "service", "incident_family", "incident_id", "published_at", "content"], self.documents)
        dump("github_issues.csv", ["issue_id", "repo", "number", "title", "body", "state", "labels", "author", "created_at", "closed_at",
                                   "incident_id", "incident_family"], self.issues)
        dump("issue_comments.csv", ["comment_id", "issue_id", "author", "created_at", "body"], self.comments)
        dump("labeled_questions.csv", ["question_id", "question", "query_kind", "expected_family", "expected_incident_ids", "expected_services", "notes"], self.questions)

    def run(self):
        self.plan_incidents()
        self.build_deployments()
        self.build_events()
        self.build_documents()
        self.build_issues()
        self.build_comments()
        self.build_questions()
        self.write()
        print("incidents: %d across %d families, %s to %s" % (
            len(self.incidents), len(self.families), self.start.date(), self.end.date()))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data", help="output folder (default: data)")
    ap.add_argument("--seed-dir", default="seed", help="seed knowledge base folder (default: seed)")
    ap.add_argument("--seed", type=int, default=2026, help="random seed for reproducible output")
    ap.add_argument("--start", default="2026-06-17", help="first day of events, YYYY-MM-DD")
    ap.add_argument("--days", type=int, default=90, help="length of the event window in days")
    ap.add_argument("--events", type=int, default=250000, help="total events to generate (routine + incident)")
    ap.add_argument("--deployments", type=int, default=4900, help="routine deployments to generate")
    ap.add_argument("--incidents", type=int, default=62, help="number of incidents across all families")
    ap.add_argument("--routine-issues", type=int, default=350, help="non-incident GitHub issues to generate")
    args = ap.parse_args()
    Generator(args).run()


if __name__ == "__main__":
    main()
