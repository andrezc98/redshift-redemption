import pytest

from rr.dataapi import BatchResult
from rr.results import read_rows, write_rows
from rr.scenarios import concurrent, make_label, new_run_id, serial

BLOCKS = {"query3": ["select 3"], "query96": ["select 96"]}


def ok(label, sqls):
    return BatchResult(label, "FINISHED", "s1", 1.5)


def test_make_label_format():
    assert make_label("a1b2", "p1", "query96") == "a1b2.p1.96"


@pytest.mark.parametrize("name", ["x" * 30, "query3'; drop table x; --", "Query3"])
def test_make_label_rejects_long_and_unsafe(name):
    with pytest.raises(ValueError):
        make_label("a1b2", "p1", name)


def test_new_run_id_is_4_hex():
    rid = new_run_id()
    assert len(rid) == 4 and int(rid, 16) >= 0


def test_serial_runs_every_block_every_pass_in_order():
    rows = serial(ok, BLOCKS, run_id="a1b2", scenario="power", passes=3)
    assert [(r.pass_no, r.name) for r in rows] == [(p, n) for p in (1, 2, 3) for n in BLOCKS]
    assert rows[0].label == "a1b2.p1.3"


def test_serial_records_failure_and_continues():
    def flaky(label, sqls):
        return BatchResult(label, "FAILED" if label.endswith(".3") else "FINISHED", "s", 0.1, "boom" if label.endswith(".3") else "")

    rows = serial(flaky, BLOCKS, run_id="a1b2", scenario="power", passes=1)
    assert [(r.name, r.status, r.error) for r in rows] == [("query3", "FAILED", "boom"), ("query96", "FINISHED", "")]


def test_concurrent_single_stream_runs_whole_shuffled_rounds_until_deadline():
    calls = []

    def exec_fn(label, sqls):
        calls.append(label)
        return ok(label, sqls)

    # deadline = 0 + 4; the clock jumps past it once 4 statements ran (two rounds of 2 blocks)
    rows = concurrent(exec_fn, BLOCKS, run_id="a1b2", streams=1, duration_s=4, seed=7,
                      clock=lambda: 0 if len(calls) < 4 else 10)
    assert [(r.pass_no, r.stream) for r in rows] == [(1, 1), (1, 1), (2, 1), (2, 1)]
    for rnd in (1, 2):
        assert sorted(r.name for r in rows if r.pass_no == rnd) == sorted(BLOCKS)


def test_concurrent_labels_unique_across_streams():
    calls = []

    def exec_fn(label, sqls):
        calls.append(label)
        return ok(label, sqls)

    rows = concurrent(exec_fn, BLOCKS, run_id="a1b2", streams=3, duration_s=4, seed=7,
                      clock=lambda: 0 if len(calls) < 12 else 10)
    assert rows and {r.stream for r in rows} <= {1, 2, 3}
    assert all(r.label.startswith("a1b2.s") for r in rows)
    assert len({r.label for r in rows}) == len(rows)


def test_write_and_read_rows_roundtrip(tmp_path):
    rows = serial(ok, BLOCKS, run_id="a1b2", scenario="power", passes=1)
    path = tmp_path / "out.csv"
    write_rows(str(path), rows)
    back = read_rows(str(path))
    assert [r["label"] for r in back] == ["a1b2.p1.3", "a1b2.p1.96"]
