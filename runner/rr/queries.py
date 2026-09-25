import re

SCALES = ("100GB", "1TB")
_START = re.compile(r"^-- start template ([A-Za-z0-9_]+)")
_LEFTOVER = re.compile(r"\{[a-z_]+\}")
_COPY_TABLE = re.compile(r"^copy (\w+) from")


def split_statements(sql: str) -> list[str]:
    return [s.strip() for s in sql.split(";") if s.strip()]


def parse_blocks(text: str) -> dict[str, list[str]]:
    blocks: dict[str, list[str]] = {}
    current, buf = None, []
    for line in text.splitlines():
        m = _START.match(line)
        if m:
            current, buf = m.group(1), []
        elif line.startswith("-- end template"):
            if current is None:
                raise ValueError("end marker without a start marker")
            blocks[current] = split_statements("\n".join(buf))
            current = None
        elif current is not None:
            buf.append(line)
    if current is not None:
        raise ValueError(f"unterminated block {current}")
    return blocks


def render(text: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        text = text.replace("{" + key + "}", value)
    leftover = _LEFTOVER.search(text)
    if leftover:
        raise ValueError(f"unrendered placeholder {leftover.group(0)}")
    return text


def load_curated(path: str, bench: dict) -> dict[str, str]:
    curated = {}
    for line in open(path):
        if not line.strip() or line.startswith("#"):
            continue
        name, cls = line.split()[:2]
        if name not in bench:
            raise ValueError(f"{name} is not in the benchmark file")
        curated[name] = cls
    return curated


def load_blocks(tables_sql: str, copy_sql: str, scale: str) -> dict[str, list[str]]:
    if scale not in SCALES:
        raise ValueError(f"scale must be one of {SCALES}, got {scale!r}")
    # Re-runnable: a restarted load must not append the data twice (TRUNCATE commits on its own).
    creates = split_statements(open(tables_sql).read())
    blocks = {"tables": [re.sub(r"(?i)^create table ", "create table if not exists ", s) for s in creates]}
    for line in open(copy_sql):
        stmt = line.strip().rstrip(";").replace("/2.13/1TB/", f"/2.13/{scale}/")
        table = _COPY_TABLE.match(stmt).group(1)
        blocks[table] = [f"TRUNCATE {table}", stmt]
    return blocks


def compare_counts(actual: dict[str, int], expected: dict[str, int]) -> list[str]:
    out = []
    for table, rows in expected.items():
        if table not in actual:
            out.append(f"{table}: missing")
        elif int(actual[table]) != rows:
            out.append(f"{table}: {actual[table]} rows, expected {rows}")
    return out
