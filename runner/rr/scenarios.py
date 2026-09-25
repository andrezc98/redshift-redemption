import random
import re
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable

from rr.dataapi import BatchResult

LABEL_MAX = 30  # Redshift truncates query_group to 30 chars in its logs
_SAFE = re.compile(r"^[a-z0-9_.]+$")

Exec = Callable[[str, list[str]], BatchResult]


@dataclass
class Row:
    run_id: str
    scenario: str
    stream: int
    pass_no: int
    name: str
    label: str
    status: str
    api_seconds: float
    error: str


def new_run_id() -> str:
    return secrets.token_hex(2)


def make_label(run_id: str, tag: str, name: str) -> str:
    label = f"{run_id}.{tag}.{name.removeprefix('query')}"
    if len(label) > LABEL_MAX or not _SAFE.match(label):
        raise ValueError(f"unsafe or too long query label: {label!r}")
    return label


def _row(run_id, scenario, stream, pass_no, name, label, r: BatchResult) -> Row:
    return Row(run_id, scenario, stream, pass_no, name, label, r.status, r.duration_s, r.error)


def serial(exec_fn: Exec, blocks: dict, *, run_id: str, scenario: str, passes: int) -> list[Row]:
    rows = []
    for p in range(1, passes + 1):
        for name, sqls in blocks.items():
            label = make_label(run_id, f"{scenario[0]}{p}", name)
            rows.append(_row(run_id, scenario, 0, p, name, label, exec_fn(label, sqls)))
    return rows


def concurrent(exec_fn: Exec, blocks: dict, *, run_id: str, streams: int, duration_s: float, seed: int,
               clock=time.monotonic) -> list[Row]:
    deadline = clock() + duration_s

    def stream(s: int) -> list[Row]:
        rng, out, rnd = random.Random(seed + s), [], 0
        while clock() < deadline:
            rnd += 1
            order = list(blocks)
            rng.shuffle(order)
            for name in order:
                if clock() >= deadline:
                    break
                label = make_label(run_id, f"s{s}{rnd}", name)
                out.append(_row(run_id, "concurrency", s, rnd, name, label, exec_fn(label, blocks[name])))
        return out

    with ThreadPoolExecutor(max_workers=streams) as pool:
        return [row for rows in pool.map(stream, range(1, streams + 1)) for row in rows]
