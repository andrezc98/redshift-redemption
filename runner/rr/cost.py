MIN_SCAN_BYTES = 10 * 2 ** 20  # Spectrum bills at least 10 MB per query (re-verify on the pricing page)
TB = 2 ** 40


def load_prices(path: str) -> dict[str, float]:
    prices = {}
    for line in open(path):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2 or cells[0] in ("item", "") or set(cells[0]) <= {"-"}:
            continue
        if cells[1] == "TODO":
            raise ValueError(f"price for {cells[0]} is still TODO in {path}")
        prices[cells[0]] = float(cells[1])
    return prices


def cluster_usd(prices: dict, node_type: str, nodes: int, seconds: float) -> float:
    return prices[node_type] * nodes * seconds / 3600


def spectrum_usd(prices: dict, scanned_bytes_per_query: list[int]) -> float:
    billed = sum(max(b, MIN_SCAN_BYTES) for b in scanned_bytes_per_query)
    return billed / TB * prices["spectrum_per_tb"]
