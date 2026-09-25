import time
from dataclasses import dataclass

TERMINAL = {"FINISHED", "FAILED", "ABORTED"}


@dataclass
class BatchResult:
    label: str
    status: str  # FINISHED | FAILED | ABORTED | TIMEOUT
    statement_id: str
    duration_s: float  # Data API wall clock for the batch; server-side timings come from SYS_QUERY_HISTORY
    error: str = ""


def preamble(label: str) -> list[str]:
    return ["SET enable_result_cache_for_session TO off", f"SET query_group TO '{label}'"]


def _wait(client, sid, poll_s, timeout_s, sleep, clock):
    start = clock()
    while True:
        d = client.describe_statement(Id=sid)
        if d["Status"] in TERMINAL:
            return d, clock() - start
        if clock() - start > timeout_s:
            client.cancel_statement(Id=sid)
            return None, clock() - start
        sleep(poll_s)


def run_batch(client, target, label, sqls, *, poll_s=2.0, timeout_s=3600, sleep=time.sleep, clock=time.monotonic):
    sid = client.batch_execute_statement(Sqls=preamble(label) + list(sqls), StatementName=label, **target.api_kwargs())["Id"]
    d, waited = _wait(client, sid, poll_s, timeout_s, sleep, clock)
    if d is None:
        return BatchResult(label, "TIMEOUT", sid, waited, f"timeout after {timeout_s}s")
    return BatchResult(label, d["Status"], sid, d.get("Duration", 0) / 1e9, d.get("Error", ""))


def _value(field: dict):
    if field.get("isNull"):
        return None
    (value,) = field.values()
    return value


def fetch(client, target, sql, *, poll_s=1.0, timeout_s=600, sleep=time.sleep, clock=time.monotonic):
    sid = client.execute_statement(Sql=sql, **target.api_kwargs())["Id"]
    d, _ = _wait(client, sid, poll_s, timeout_s, sleep, clock)
    if d is None:
        raise TimeoutError(sql[:80])
    if d["Status"] != "FINISHED":
        raise RuntimeError(d.get("Error") or d["Status"])
    rows, token = [], None
    while True:
        page = client.get_statement_result(Id=sid, **({"NextToken": token} if token else {}))
        cols = [c["name"] for c in page["ColumnMetadata"]]
        rows += [dict(zip(cols, map(_value, rec))) for rec in page["Records"]]
        token = page.get("NextToken")
        if not token:
            return rows
