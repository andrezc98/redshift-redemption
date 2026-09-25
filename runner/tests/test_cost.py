import pytest

from rr.cost import cluster_usd, load_prices, spectrum_usd

FILLED = """| item | usd | unit | captured |
|---|---|---|---|
| rg.xlarge | 0.7602 | node-hour | 2026-09-24 |
| spectrum_per_tb | 5.00 | TB scanned | 2026-09-24 |
"""


def test_load_prices_reads_table(tmp_path):
    p = tmp_path / "prices.md"
    p.write_text("# x\n\n" + FILLED)
    assert load_prices(str(p)) == {"rg.xlarge": 0.7602, "spectrum_per_tb": 5.0}


def test_load_prices_refuses_todo(tmp_path):
    p = tmp_path / "prices.md"
    p.write_text(FILLED + "| ra3.xlplus | TODO | node-hour | |\n")
    with pytest.raises(ValueError):
        load_prices(str(p))


def test_cluster_usd():
    assert cluster_usd({"rg.xlarge": 0.7602}, "rg.xlarge", 2, 1800) == pytest.approx(0.7602)


def test_spectrum_usd_applies_10mb_minimum():
    tb = 2 ** 40
    assert spectrum_usd({"spectrum_per_tb": 5.0}, [tb, 1]) == pytest.approx(5.0 + 5.0 * 10 * 2 ** 20 / tb)
