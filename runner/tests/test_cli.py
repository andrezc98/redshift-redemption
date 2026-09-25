from rr.cli import LAKE_PREFIX, build_parser, out_path
from rr.config import Target


def test_out_path():
    assert out_path(Target.parse("cluster:rr-rg"), "power", "a1b2", "2026-10-03") == "results/2026-10-03/rr-rg-power-a1b2.csv"


def test_parser_power_defaults():
    args = build_parser().parse_args(["power", "--target", "cluster:rr-ra3"])
    assert (args.cmd, args.passes) == ("power", 3)


def test_parser_rejects_unknown_lake_variant():
    import pytest

    with pytest.raises(SystemExit):
        build_parser().parse_args(["lake", "--target", "cluster:rr-ra3", "--variant", "delta"])


def test_lake_prefixes_end_with_dot_or_are_empty():
    assert all(p == "" or p.endswith(".") for p in LAKE_PREFIX.values())


def test_parser_has_query_and_counts():
    p = build_parser()
    assert p.parse_args(["query", "--target", "cluster:rr-rg", "--file", "x.sql"]).cmd == "query"
    assert p.parse_args(["counts", "--target", "cluster:rr-ra3", "--scale", "1TB"]).scale == "1TB"


def test_counts_sql_covers_every_table():
    from rr.cli import counts_sql

    sql = counts_sql(["store_sales", "item"])
    assert "'store_sales' AS t, COUNT(*) AS n FROM store_sales" in sql and " UNION ALL " in sql


def _timings(path, label, cache_hit="False", version="1.0.1"):
    path.write_text(
        "run_id,scenario,stream,pass_no,name,label,status,api_seconds,error,elapsed_s,queue_s,exec_s,compile_s,"
        "planning_s,scanned_bytes,server_status,redshift_version,cache_hit,compute_type\n"
        f"a,power,0,2,query3,{label},FINISHED,1,,2.0,0,2,0,0,0,success,{version},{cache_hit},primary\n")


def _prices(path):
    path.write_text("| item | usd | unit | c |\n|---|---|---|---|\n| ra3.xlplus | 1.086 | h | x |\n| rg.xlarge | 0.7602 | h | x |\n")


def test_report_refuses_invalid_rows(tmp_path):
    from rr.cli import main

    _timings(tmp_path / "b.csv", "a.p2.3")
    _timings(tmp_path / "c.csv", "b.p2.3", cache_hit="True")
    _prices(tmp_path / "p.md")
    rc = main(["report", "--base", str(tmp_path / "b.csv"), "--cand", str(tmp_path / "c.csv"),
               "--prices", str(tmp_path / "p.md"), "--out", str(tmp_path / "s.md")])
    assert rc == 3 and not (tmp_path / "s.md").exists()


def test_report_warns_on_version_mismatch_in_header(tmp_path):
    from rr.cli import main

    _timings(tmp_path / "b.csv", "a.p2.3", version="1.0.1")
    _timings(tmp_path / "c.csv", "b.p2.3", version="1.0.2")
    _prices(tmp_path / "p.md")
    rc = main(["report", "--base", str(tmp_path / "b.csv"), "--cand", str(tmp_path / "c.csv"),
               "--prices", str(tmp_path / "p.md"), "--out", str(tmp_path / "s.md")])
    text = (tmp_path / "s.md").read_text()
    assert rc == 0 and "1.0.1" in text.split("\n")[0] and "1.0.2" in text.split("\n")[0]
