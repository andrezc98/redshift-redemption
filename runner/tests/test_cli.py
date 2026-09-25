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
