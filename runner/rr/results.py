import csv
from dataclasses import asdict, fields


def write_rows(path: str, rows: list) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[x.name for x in fields(rows[0])])
        writer.writeheader()
        writer.writerows(asdict(r) for r in rows)


def read_rows(path: str) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))
