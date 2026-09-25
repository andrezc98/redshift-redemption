import re
from collections import defaultdict

_RUN = re.compile(r"^[0-9a-f]{4}$")
_US = {"elapsed_s": "elapsed_time", "queue_s": "queue_time", "exec_s": "execution_time",
       "compile_s": "compile_time", "planning_s": "planning_time"}


def _check(run_id: str) -> str:
    if not _RUN.match(run_id):
        raise ValueError(f"run id must be 4 hex chars, got {run_id!r}")
    return run_id


def history_sql(run_id: str) -> str:
    return f"""
SELECT TRIM(query_label) AS query_label, query_id, TRIM(query_type) AS query_type, TRIM(status) AS status,
       result_cache_hit, TRIM(compute_type) AS compute_type, TRIM(redshift_version) AS redshift_version,
       elapsed_time, queue_time, execution_time, compile_time, planning_time
FROM sys_query_history
WHERE query_label LIKE '{_check(run_id)}.%' AND query_type <> 'UTILITY'
ORDER BY start_time"""


def external_sql(run_id: str) -> str:
    return f"""
SELECT TRIM(h.query_label) AS query_label, SUM(e.returned_bytes) AS scanned_bytes
FROM sys_external_query_detail e JOIN sys_query_history h ON h.query_id = e.query_id
WHERE h.query_label LIKE '{_check(run_id)}.%' AND TRIM(e.source_type) = 'S3'
GROUP BY 1"""


def aggregate(history: list[dict], external: list[dict]) -> dict[str, dict]:
    agg = defaultdict(lambda: {**{k: 0.0 for k in _US}, "status": "success", "cache_hit": False,
                               "compute_types": set(), "versions": set(), "scanned_bytes": 0})
    for q in history:
        a = agg[q["query_label"]]
        for key, col in _US.items():
            a[key] += (q[col] or 0) / 1e6
        if q["status"] != "success":
            a["status"] = q["status"]
        a["cache_hit"] |= bool(q["result_cache_hit"])
        a["compute_types"].add(q["compute_type"] or "")
        a["versions"].add(q["redshift_version"])
    for e in external:
        agg[e["query_label"]]["scanned_bytes"] = int(e["scanned_bytes"] or 0)
    return dict(agg)


def problems(history: list[dict]) -> list[str]:
    found = []
    hits = sorted({q["query_label"] for q in history if q["result_cache_hit"]})
    if hits:
        found.append(f"result cache hit on {len(hits)} labels: {hits[:5]}")
    scaled = sorted({(q["query_label"], q["compute_type"]) for q in history
                     if (q["compute_type"] or "") not in ("", "primary")})
    if scaled:
        found.append(f"non-primary compute_type (concurrency scaling?): {scaled[:5]}")
    versions = {q["redshift_version"] for q in history}
    if len(versions) > 1:
        found.append(f"run spans several Redshift versions: {sorted(versions)}")
    return found


def timings(rows: list[dict], agg: dict) -> list[dict]:
    out = []
    for r in rows:
        a = agg.get(r["label"])
        extra = {k: (round(a[k], 6) if a else "") for k in _US}
        extra["scanned_bytes"] = a["scanned_bytes"] if a else ""
        extra["redshift_version"] = ";".join(sorted(a["versions"])) if a else ""
        extra["cache_hit"] = a["cache_hit"] if a else ""
        extra["compute_type"] = ";".join(sorted(a["compute_types"])) if a else ""
        extra["server_status"] = a["status"] if a else ""
        out.append({**r, **extra})
    return out


def report_checks(base: list[dict], cand: list[dict]) -> tuple[list[str], list[str]]:
    """(warnings, fatal) for a base-vs-candidate report. Fatal rows must never reach a slide."""
    warnings, fatal = [], []
    versions = [sorted({r["redshift_version"] for r in rows if r.get("redshift_version")}) for rows in (base, cand)]
    if versions[0] != versions[1]:
        warnings.append(f"Redshift versions differ: base {versions[0]} vs candidato {versions[1]}")
    for side, rows in (("base", base), ("candidato", cand)):
        hits = [r["label"] for r in rows if str(r.get("cache_hit")) == "True"]
        if hits:
            fatal.append(f"{side}: result cache hit on {hits[:5]}")
        scaled = sorted({r["compute_type"] for r in rows if r.get("compute_type") not in (None, "", "primary")})
        if scaled:
            fatal.append(f"{side}: non-primary compute_type {scaled}")
    return warnings, fatal
