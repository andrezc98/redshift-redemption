import pytest

from rr.stats import by_class, geomean, per_query, percentile, speedups, summary, throughput


def t(name, pass_no, elapsed, status="success", queue=0.0):
    return {"name": name, "pass_no": str(pass_no), "elapsed_s": str(elapsed), "queue_s": str(queue),
            "server_status": status}


def test_percentile_interpolates():
    assert percentile([1, 2, 3, 4], 50) == 2.5
    assert percentile([5], 95) == 5


def test_per_query_drops_warmup_and_failures():
    rows = [t("q3", 1, 100), t("q3", 2, 10), t("q3", 3, 12), t("q7", 2, 5, status="failed"), t("q7", 3, 7)]
    assert per_query(rows) == {"q3": 11.0, "q7": 7.0}


def test_summary():
    s = summary({"a": 1.0, "b": 3.0})
    assert s == {"n": 2, "total_s": 4.0, "p50_s": 2.0, "p95_s": pytest.approx(2.9)}


def test_speedups_and_geomean_and_classes():
    sp = speedups({"a": 4.0, "b": 9.0, "only_base": 1.0}, {"a": 2.0, "b": 3.0})
    assert sp == {"a": 2.0, "b": 3.0}
    assert geomean(sp.values()) == pytest.approx(6 ** 0.5)
    assert by_class(sp, {"a": "scan", "b": "cpu"}) == {"scan": pytest.approx(2.0), "cpu": pytest.approx(3.0)}


def test_throughput_counts_success_per_hour():
    rows = [t("a", 1, 1, queue=0.5), t("b", 1, 1, queue=1.5), t("c", 1, 1, status="failed")]
    out = throughput(rows, duration_s=1800)
    assert out["queries_per_hour"] == 4.0 and out["failed"] == 1 and out["queue_p50_s"] == 1.0
