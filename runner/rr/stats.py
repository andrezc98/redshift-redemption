import math
from collections import defaultdict
from statistics import median


def percentile(values: list[float], q: float) -> float:
    xs = sorted(values)
    if len(xs) == 1:
        return float(xs[0])
    pos = (len(xs) - 1) * q / 100
    lo, hi = math.floor(pos), math.ceil(pos)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def _ok(rows):
    return [r for r in rows if r["server_status"] == "success"]


def per_query(timings: list[dict], warmup: int = 1) -> dict[str, float]:
    by_name = defaultdict(list)
    for r in _ok(timings):
        if int(r["pass_no"]) > warmup:
            by_name[r["name"]].append(float(r["elapsed_s"]))
    return {name: median(xs) for name, xs in by_name.items()}


def summary(per_q: dict[str, float]) -> dict:
    xs = list(per_q.values())
    return {"n": len(xs), "total_s": sum(xs), "p50_s": percentile(xs, 50), "p95_s": percentile(xs, 95)}


def speedups(base: dict, cand: dict) -> dict[str, float]:
    return {k: base[k] / cand[k] for k in base if k in cand and cand[k] > 0}


def geomean(values) -> float:
    xs = list(values)
    return math.exp(sum(math.log(x) for x in xs) / len(xs))


def by_class(sp: dict, classes: dict[str, str]) -> dict[str, float]:
    groups = defaultdict(list)
    for name, value in sp.items():
        groups[classes[name]].append(value)
    return {cls: geomean(vs) for cls, vs in groups.items()}


def throughput(timings: list[dict], duration_s: float) -> dict:
    ok = _ok(timings)
    queues = [float(r["queue_s"]) for r in ok] or [0.0]
    return {"queries_per_hour": len(ok) * 3600 / duration_s, "queue_p50_s": percentile(queues, 50),
            "queue_p95_s": percentile(queues, 95), "failed": len(timings) - len(ok)}
