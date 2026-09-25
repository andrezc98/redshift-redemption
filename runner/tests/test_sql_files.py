from pathlib import Path

import pytest

from rr.cli import LAKE_PREFIX
from rr.queries import parse_blocks, render

SQL = Path(__file__).resolve().parents[2] / "sql"
LAKE_TABLES = ["date_dim", "item", "store", "customer", "store_sales"]


@pytest.mark.parametrize("name", ["lake_build_s3tables", "lake_build_glue", "lake_build_parquet"])
def test_lake_builds_cover_the_five_tables(name):
    blocks = parse_blocks(render((SQL / f"{name}.sql").read_text(), {"bucket": "b"}))
    assert [b for b in blocks if b.startswith("b_")] == [f"b_{t}" for t in LAKE_TABLES]


@pytest.mark.parametrize("variant", list(LAKE_PREFIX))
def test_lake_queries_render_for_every_variant(variant):
    blocks = parse_blocks(render((SQL / "lake_queries.sql").read_text(), {"lake": LAKE_PREFIX[variant]}))
    assert list(blocks) == ["lq3", "lq42", "lq52", "lq55", "lqst", "lqcu"]
    assert all(len(v) == 1 for v in blocks.values())


def test_elt_blocks():
    blocks = parse_blocks(render((SQL / "elt.sql").read_text(), {"scale": "1TB"}))
    assert list(blocks) == ["ecopy", "ectas"]
    assert "/2.13/1TB/store_returns/" in blocks["ecopy"][2]


def test_glue_fallback_uses_external_schema_not_auto_mount():
    # Final review I5: awsdatacatalog auto-mount needs an IAM-identity connection; the runner uses DbUser.
    text = (SQL / "lake_build_glue.sql").read_text()
    assert "awsdatacatalog" not in text and "CREATE EXTERNAL SCHEMA IF NOT EXISTS ice" in text
    assert LAKE_PREFIX["glue"] == "ice."
