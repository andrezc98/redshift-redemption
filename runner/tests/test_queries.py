from pathlib import Path

import pytest

from rr.queries import load_blocks, load_curated, parse_blocks, render, split_statements

SQL = Path(__file__).resolve().parents[2] / "sql"


def test_vendor_file_has_99_blocks_and_103_statements():
    bench = parse_blocks((SQL / "vendor/query_0.sql").read_text())
    assert len(bench) == 99
    assert sum(len(v) for v in bench.values()) == 103
    assert {k for k, v in bench.items() if len(v) == 2} == {"query14", "query23", "query24", "query39"}


def test_parse_blocks_names_and_statements():
    text = "-- start template query1.tpl query 1 in stream 0\nselect 1;\n-- end template query1.tpl\n"
    assert parse_blocks(text) == {"query1": ["select 1"]}


def test_parse_blocks_rejects_unterminated_block():
    with pytest.raises(ValueError):
        parse_blocks("-- start template lq3\nselect 1;\n")


def test_split_statements_drops_empty_tail():
    assert split_statements("select 1;\n select 2 ;\n\n") == ["select 1", "select 2"]


def test_render_replaces_and_rejects_leftovers():
    assert render("from {lake}t", {"lake": "pq."}) == "from pq.t"
    with pytest.raises(ValueError):
        render("from {lake}t where {x}", {"lake": ""})


def test_curated_has_20_known_names_split_10_10():
    bench = parse_blocks((SQL / "vendor/query_0.sql").read_text())
    curated = load_curated(str(SQL / "curated.txt"), bench)
    assert len(curated) == 20
    assert sorted(set(curated.values())) == ["cpu", "scan"]
    assert list(curated.values()).count("scan") == 10


def test_curated_rejects_unknown_name(tmp_path):
    p = tmp_path / "c.txt"
    p.write_text("query999 scan nope\n")
    with pytest.raises(ValueError):
        load_curated(str(p), {"query3": ["select 1"]})


def test_load_blocks_renders_scale():
    blocks = load_blocks(str(SQL / "tables.sql"), str(SQL / "copy.sql"), "100GB")
    assert len(blocks["tables"]) == 25
    assert len(blocks) == 25  # tables + 24 copy blocks
    assert "/2.13/100GB/store_sales/" in blocks["store_sales"][1]  # [0] is the TRUNCATE


def test_load_blocks_rejects_unknown_scale():
    with pytest.raises(ValueError):
        load_blocks(str(SQL / "tables.sql"), str(SQL / "copy.sql"), "10TB")


def test_load_blocks_rerun_safe_create_if_not_exists_and_truncate_before_copy():
    # Final review C1: a restarted load must not append the data twice.
    blocks = load_blocks(str(SQL / "tables.sql"), str(SQL / "copy.sql"), "100GB")
    assert all(s.lower().startswith("create table if not exists ") for s in blocks["tables"])
    assert blocks["store_sales"][0] == "TRUNCATE store_sales"
    assert blocks["store_sales"][1].startswith("copy store_sales from")


def test_compare_counts_reports_mismatch_and_missing():
    from rr.queries import compare_counts

    assert compare_counts({"a": 10, "b": 5}, {"a": 10, "b": 5}) == []
    assert compare_counts({"a": 20}, {"a": 10, "b": 5}) == ["a: 20 rows, expected 10", "b: missing"]
