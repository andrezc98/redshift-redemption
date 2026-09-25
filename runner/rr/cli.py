import argparse
import csv
import datetime as dt
import sys
from functools import partial
from pathlib import Path

from rr import cost, metrics, queries, stats
from rr.config import Target, data_client
from rr.dataapi import fetch, run_batch
from rr.results import read_rows, write_rows
from rr.scenarios import concurrent, new_run_id, serial

ROOT = Path(__file__).resolve().parents[2]
SQL = ROOT / "sql"
LAKE_PREFIX = {"local": "", "s3tables": '"rr-lake@s3tablescatalog".tpcds.',
               "glue": "awsdatacatalog.rr_iceberg.", "parquet": "pq."}


def out_path(target: Target, scenario: str, run_id: str, day: str) -> str:
    return f"results/{day}/{target.name}-{scenario}-{run_id}.csv"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="rr")
    sub = p.add_subparsers(dest="cmd", required=True)

    def cmd(name, **extra):
        s = sub.add_parser(name)
        s.add_argument("--target", required=name != "report", type=Target.parse)
        for flag, kw in extra.items():
            s.add_argument(f"--{flag.replace('_', '-')}", **kw)
        return s

    cmd("load", scale=dict(required=True, choices=queries.SCALES))
    cmd("power", passes=dict(type=int, default=3))
    cmd("concurrency", streams=dict(type=int, default=5), minutes=dict(type=float, default=30), seed=dict(type=int, default=7))
    cmd("lake", variant=dict(required=True, choices=list(LAKE_PREFIX)), passes=dict(type=int, default=3))
    cmd("elt", scale=dict(required=True, choices=queries.SCALES), passes=dict(type=int, default=2))
    cmd("sql", file=dict(required=True), var=dict(action="append", default=[]))
    cmd("metrics", csv=dict(required=True))
    cmd("report", base=dict(required=True), cand=dict(required=True), out=dict(required=True),
        classes=dict(default=str(SQL / "curated.txt")), prices=dict(default=str(ROOT / "results/prices.md")),
        base_node=dict(default="ra3.xlplus"), cand_node=dict(default="rg.xlarge"), nodes=dict(type=int, default=2))
    return p


def _blocks(args) -> tuple[str, dict]:
    if args.cmd == "load":
        return "load", queries.load_blocks(str(SQL / "tables.sql"), str(SQL / "copy.sql"), args.scale)
    if args.cmd in ("power", "concurrency"):
        bench = queries.parse_blocks((SQL / "vendor/query_0.sql").read_text())
        return args.cmd, {n: bench[n] for n in queries.load_curated(str(SQL / "curated.txt"), bench)}
    if args.cmd == "lake":
        text = queries.render((SQL / "lake_queries.sql").read_text(), {"lake": LAKE_PREFIX[args.variant]})
        return f"lake-{args.variant}", queries.parse_blocks(text)
    if args.cmd == "elt":
        return "elt", queries.parse_blocks(queries.render((SQL / "elt.sql").read_text(), {"scale": args.scale}))
    values = dict(v.split("=", 1) for v in args.var)
    return Path(args.file).stem, queries.parse_blocks(queries.render(Path(args.file).read_text(), values))


def _run(args) -> int:
    client, run_id = data_client(), new_run_id()
    exec_fn = partial(run_batch, client, args.target, timeout_s=6 * 3600 if args.cmd == "load" else 3600)
    scenario, blocks = _blocks(args)
    print(f"run {run_id}: {scenario} on {args.target.name}, {len(blocks)} blocks", flush=True)
    if args.cmd == "concurrency":
        rows = concurrent(lambda lb, sq: exec_fn(lb, sq), blocks, run_id=run_id, streams=args.streams,
                          duration_s=args.minutes * 60, seed=args.seed)
    else:
        passes = getattr(args, "passes", 1)
        rows = serial(lambda lb, sq: exec_fn(lb, sq), blocks, run_id=run_id, scenario=scenario, passes=passes)
    path = ROOT / out_path(args.target, scenario, run_id, dt.date.today().isoformat())
    path.parent.mkdir(parents=True, exist_ok=True)
    write_rows(str(path), rows)
    failed = [r for r in rows if r.status != "FINISHED"]
    print(f"wrote {path} ({len(rows)} rows, {len(failed)} not FINISHED)")
    return 0


def _metrics(args) -> int:
    client = data_client()
    rows = read_rows(args.csv)
    run_id = rows[0]["run_id"]
    history = fetch(client, args.target, metrics.history_sql(run_id))
    external = fetch(client, args.target, metrics.external_sql(run_id))
    out = metrics.timings(rows, metrics.aggregate(history, external))
    dest = args.csv.removesuffix(".csv") + "-timings.csv"
    with open(dest, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    found = metrics.problems(history)
    print(f"wrote {dest}")
    for p in found:
        print(f"INVALID: {p}", file=sys.stderr)
    return 3 if found else 0


def _report(args) -> int:
    base, cand = read_rows(args.base), read_rows(args.cand)
    bq, cq = stats.per_query(base), stats.per_query(cand)
    sp = stats.speedups(bq, cq)
    bench = queries.parse_blocks((SQL / "vendor/query_0.sql").read_text())
    classes = queries.load_curated(args.classes, bench)
    prices = cost.load_prices(args.prices)
    bs, cs = stats.summary(bq), stats.summary(cq)
    lines = [
        "| | base | candidato |", "|---|---|---|",
        f"| consultas medidas | {bs['n']} | {cs['n']} |",
        f"| total (s) | {bs['total_s']:.1f} | {cs['total_s']:.1f} |",
        f"| p50 / p95 (s) | {bs['p50_s']:.2f} / {bs['p95_s']:.2f} | {cs['p50_s']:.2f} / {cs['p95_s']:.2f} |",
        f"| USD por corrida | {cost.cluster_usd(prices, args.base_node, args.nodes, bs['total_s']):.3f} "
        f"| {cost.cluster_usd(prices, args.cand_node, args.nodes, cs['total_s']):.3f} |",
        "", f"Aceleración (media geométrica): {stats.geomean(sp.values()):.2f}x", "",
        "| clase | aceleración |", "|---|---|",
        *[f"| {c} | {v:.2f}x |" for c, v in sorted(stats.by_class(sp, classes).items())],
        "", "| consulta | base (s) | candidato (s) | aceleración |", "|---|---|---|---|",
        *[f"| {n} | {bq[n]:.2f} | {cq[n]:.2f} | {sp[n]:.2f}x |" for n in sorted(sp)],
    ]
    Path(args.out).write_text("\n".join(lines) + "\n")
    print(f"wrote {args.out}")
    return 0


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "metrics":
        return _metrics(args)
    if args.cmd == "report":
        return _report(args)
    return _run(args)


if __name__ == "__main__":
    sys.exit(main())
