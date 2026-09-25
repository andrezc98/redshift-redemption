from rr.config import Target
from rr.dataapi import fetch, preamble, run_batch
from tests.fakes import FakeDataClient

T = Target.parse("cluster:rr-ra3")


def test_run_batch_prepends_cache_off_and_label():
    client = FakeDataClient()
    r = run_batch(client, T, "a1b2.p1.96", ["select 1"], sleep=lambda s: None)
    kind, kw = client.calls[0]
    assert kind == "batch"
    assert kw["Sqls"] == preamble("a1b2.p1.96") + ["select 1"]
    assert kw["ClusterIdentifier"] == "rr-ra3"
    assert (r.status, r.duration_s) == ("FINISHED", 2.0)


def test_run_batch_reports_failure_with_error():
    client = FakeDataClient(statuses=("FAILED",), error="relation does not exist")
    r = run_batch(client, T, "a1b2.p1.3", ["select * from nope"], sleep=lambda s: None)
    assert (r.status, r.error) == ("FAILED", "relation does not exist")


def test_run_batch_timeout_cancels():
    client = FakeDataClient(statuses=("STARTED",))
    ticks = iter(range(0, 10_000, 100))
    r = run_batch(client, T, "a1b2.p1.72", ["select 1"], timeout_s=250, sleep=lambda s: None, clock=lambda: next(ticks))
    assert r.status == "TIMEOUT"
    assert ("cancel", {"Id": r.statement_id}) in client.calls


def test_fetch_paginates_and_maps_values():
    pages = [
        {"ColumnMetadata": [{"name": "query_label"}, {"name": "result_cache_hit"}],
         "Records": [[{"stringValue": "a1b2.p1.3"}, {"booleanValue": False}]]},
        {"ColumnMetadata": [{"name": "query_label"}, {"name": "result_cache_hit"}],
         "Records": [[{"stringValue": "a1b2.p1.7"}, {"isNull": True}]]},
    ]
    rows = fetch(FakeDataClient(pages=pages), T, "select 1", sleep=lambda s: None)
    assert rows == [
        {"query_label": "a1b2.p1.3", "result_cache_hit": False},
        {"query_label": "a1b2.p1.7", "result_cache_hit": None},
    ]
