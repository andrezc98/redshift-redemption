import pytest

from rr.metrics import aggregate, external_sql, history_sql, problems, timings


def h(label, qid, **kw):
    base = {"query_label": label, "query_id": qid, "query_type": "SELECT", "status": "success",
            "result_cache_hit": False, "compute_type": "primary", "redshift_version": "1.0.99999",
            "elapsed_time": 2_000_000, "queue_time": 0, "execution_time": 1_500_000,
            "compile_time": 100_000, "planning_time": 50_000}
    base.update(kw)
    return base


def test_history_sql_filters_run_and_utility():
    sql = history_sql("a1b2")
    assert "query_label LIKE 'a1b2.%'" in sql and "query_type <> 'UTILITY'" in sql


@pytest.mark.parametrize("bad", ["a1b2'--", "zzzz", "a1b2c"])
def test_history_sql_rejects_bad_run_id(bad):
    with pytest.raises(ValueError):
        history_sql(bad)


def test_external_sql_joins_on_query_id():
    assert "sys_external_query_detail" in external_sql("a1b2").lower()


def test_aggregate_sums_two_statement_block():
    agg = aggregate([h("a1b2.p1.14", 1), h("a1b2.p1.14", 2, elapsed_time=3_000_000)], [])
    assert agg["a1b2.p1.14"]["elapsed_s"] == 5.0
    assert agg["a1b2.p1.14"]["status"] == "success"


def test_aggregate_block_fails_if_any_statement_failed():
    agg = aggregate([h("a1b2.p1.14", 1), h("a1b2.p1.14", 2, status="failed")], [])
    assert agg["a1b2.p1.14"]["status"] == "failed"


def test_aggregate_adds_scanned_bytes():
    agg = aggregate([h("a1b2.l1.lq3", 9)], [{"query_label": "a1b2.l1.lq3", "scanned_bytes": 1024}])
    assert agg["a1b2.l1.lq3"]["scanned_bytes"] == 1024


def test_problems_clean_run_is_empty():
    assert problems([h("a1b2.p1.3", 1), h("a1b2.p1.7", 2)]) == []


def test_problems_flags_cache_hit_and_scaling():
    found = problems([h("a1b2.p1.3", 1, result_cache_hit=True), h("a1b2.p1.7", 2, compute_type="primary-scale")])
    assert any("result cache" in p for p in found)
    assert any("primary-scale" in p for p in found)


def test_problems_accepts_serverless_empty_compute_type():
    assert problems([h("a1b2.p1.3", 1, compute_type=None), h("a1b2.p1.7", 2, compute_type="")]) == []


def test_problems_flags_version_mix():
    found = problems([h("a1b2.p1.3", 1), h("a1b2.p1.7", 2, redshift_version="1.0.11111")])
    assert any("version" in p for p in found)


def test_timings_keeps_rows_missing_from_history():
    rows = [{"label": "a1b2.p1.3", "name": "query3", "pass_no": "1", "stream": "0", "status": "TIMEOUT"}]
    out = timings(rows, {})
    assert out[0]["status"] == "TIMEOUT" and out[0]["elapsed_s"] == ""
