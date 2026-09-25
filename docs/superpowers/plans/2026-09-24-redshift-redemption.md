# Redshift Redemption Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A reproducible lab that measures Amazon Redshift RA3 (2× ra3.xlplus) against RG (2× rg.xlarge) on TPC-DS-derived 1 TB data — power, concurrency, data lake, ELT, migration drill, Serverless context — with time and USD side by side.

**Architecture:** Terraform (local state) creates the IAM role, lake buckets, Glue databases, parameter group, clusters and budget. A small Python runner drives everything else through the Redshift Data API: it runs labeled statement batches, then reads server-side timings from `SYS_QUERY_HISTORY` / `SYS_EXTERNAL_QUERY_DETAIL` by label, writes CSVs, and computes stats and cost. Load once on RA3, build the lake copies, snapshot, restore RG from that snapshot.

**Tech Stack:** Terraform ≥ 1.15 + hashicorp/aws provider (version pinned on the day), Python 3.13 + uv + boto3 (`redshift-data`) + pytest, AWS CLI v2.

**Spec:** `docs/superpowers/specs/2026-09-24-redshift-redemption-design.md`

## Global Constraints

- Region `us-east-1` everywhere; `AWS_PROFILE=sura-sandbox`; every AWS-touching entrypoint calls `require_sandbox()` first.
- `terraform apply`/`destroy`, snapshot restores, resizes and every benchmark scenario wait for the speaker's explicit "go".
- Clusters: `rr-ra3` = 2× `ra3.xlplus`; `rr-rg` = 2× `rg.xlarge` restored from the `rr-ra3` snapshot; `rr-sls` = Serverless base 32 RPU; database `tpcds`; admin `awsuser`; maintenance track `current`.
- Parameter group: `max_concurrency_scaling_clusters=0`, `enable_result_cache_for_session=false`, `require_ssl=true`.
- Dataset `s3://redshift-downloads/TPC-DS/2.13/{100GB|1TB}/`.
- Budget: AWS Budget on service "Amazon Redshift", USD 100 limit, alert at 80% actual and 100% forecast.
- Query labels: `<run 4 hex>.<tag>.<name>`, only `[a-z0-9_.]`, ≤ 30 chars (Redshift truncates `query_group` to 30 in logs).
- A measured query with `result_cache_hit = true`, or `compute_type` other than `primary` (provisioned), or a run spanning more than one `redshift_version`, is reported as invalid, never silently counted.
- Code/tests/commits in English; audience-facing text in neutral Spanish, no voseo.
- Nothing committed contains account IDs, ARNs with accounts, endpoints or credentials: `demo/sanitize-check.sh` prints `sanitize-check: clean` before every commit that touches `results/`.
- Verify every provider argument, API field and SQL syntax against the docs of the day before writing it (CLAUDE.md rule); pin what you verify.

## Review Focus

1. **A query fails or times out mid-run** — the run continues, the row is recorded with `FAILED`/`TIMEOUT` and the error, and stats exclude it while the report lists it. Test: `test_serial_records_failure_and_continues` (Task 5), `test_run_batch_timeout_cancels` (Task 4).
2. **Result cache or concurrency scaling leaks into a measurement** — `problems()` flags it, `rr metrics` exits 3, and the runbook repeats the run instead of reporting it. Test: `test_problems_flags_cache_hit_and_scaling` (Task 6).
3. **RA3 and RG on different Redshift versions** — flagged in the report header, not hidden. Test: `test_problems_flags_version_mix` (Task 6).
4. **A label too long or with unsafe characters** (it is interpolated into `SET query_group`) — rejected before any AWS call. Test: `test_make_label_rejects_long_and_unsafe` (Task 5).
5. **Prices missing or stale** — `load_prices` refuses a `TODO` cell, so no USD figure is ever computed from a guess. Test: `test_load_prices_refuses_todo` (Task 7).

---

## File Structure

```
redshift-redemption/
  CLAUDE.md  README.md  .gitignore                      (exist)
  demo/sanitize-check.sh                                 Task 1 (copied verbatim)
  sql/vendor/query_0.sql  sql/vendor/ddl.sql             Task 3 (awslabs, unmodified)
  sql/tables.sql  sql/copy.sql  sql/expected_counts_1tb.csv   Task 3 (derived by script)
  sql/curated.txt                                        Task 3
  sql/lake_build_s3tables.sql  sql/lake_build_glue.sql
  sql/lake_build_parquet.sql  sql/lake_queries.sql  sql/elt.sql   Task 9
  scripts/split-ddl.sh                                   Task 3
  runner/pyproject.toml                                  Task 2
  runner/rr/__init__.py  runner/rr/config.py             Task 2
  runner/rr/queries.py                                   Task 3
  runner/rr/dataapi.py                                   Task 4
  runner/rr/scenarios.py  runner/rr/results.py           Task 5
  runner/rr/metrics.py                                   Task 6
  runner/rr/stats.py  runner/rr/cost.py                  Task 7
  runner/rr/cli.py                                       Task 8
  runner/tests/test_*.py                                 per task
  infra/versions.tf variables.tf main.tf outputs.tf      Task 10
  runbooks/lab-day.md                                    Task 11
  results/prices.md                                      Task 7 (template), Task 12 (filled)
  results/<date>/*.csv, summary.md                       Tasks 12–13
```

---

### Task 1: Repo guardrails and first commit

**Files:**
- Create: `demo/sanitize-check.sh` (verbatim copy of `../rompe-tu-agente/demo/sanitize-check.sh`)
- Commit: everything already in the repo (CLAUDE.md, README.md, .gitignore, spec, plan)

**Interfaces:**
- Produces: `bash demo/sanitize-check.sh` → prints `sanitize-check: clean` or exits 1; `--selftest` runs its own assertions.

- [ ] **Step 1: Copy the guard**

```bash
cd redshift-redemption
mkdir -p demo
cp ../rompe-tu-agente/demo/sanitize-check.sh demo/sanitize-check.sh
chmod +x demo/sanitize-check.sh
```

- [ ] **Step 2: Run its selftest**

Run: `bash demo/sanitize-check.sh --selftest`
Expected: last line `sanitize-check --selftest: all assertions passed`

- [ ] **Step 3: Scan the repo**

Run: `bash demo/sanitize-check.sh`
Expected: `sanitize-check: clean`

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: repo skeleton, spec, plan and sanitize guard"
```

---

### Task 2: Runner project, sandbox guard and targets

**Files:**
- Create: `runner/pyproject.toml`, `runner/rr/__init__.py`, `runner/rr/config.py`
- Test: `runner/tests/test_config.py`

**Interfaces:**
- Produces:
  - `require_sandbox() -> None` (raises `RuntimeError` unless `AWS_PROFILE` contains `sandbox` or `GITHUB_ACTIONS == "true"`)
  - `REGION: str = "us-east-1"`
  - `@dataclass(frozen=True) class Target(kind: str, name: str, database: str = "tpcds", db_user: str = "awsuser")`
  - `Target.parse(spec: str) -> Target` (`"cluster:rr-ra3"` / `"workgroup:rr-sls"`)
  - `Target.api_kwargs() -> dict` (Data API identity kwargs)
  - `data_client()` → boto3 `redshift-data` client, standard retries, `REGION`

- [ ] **Step 1: Create the project with pinned deps of the day**

```bash
mkdir -p runner/rr runner/tests && cd runner
uv init --bare --python 3.13 --name rr-runner
uv add boto3
uv add --dev pytest
touch rr/__init__.py
```

Then append to `runner/pyproject.toml`:

```toml
[project.scripts]
rr = "rr.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["rr"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

Record the resolved boto3 and pytest versions (from `uv.lock`) in README "Versiones probadas".

- [ ] **Step 2: Write the failing tests**

`runner/tests/test_config.py`:

```python
import pytest

from rr.config import Target, require_sandbox


def test_require_sandbox_refuses_default_profile(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setenv("AWS_PROFILE", "default")
    with pytest.raises(RuntimeError):
        require_sandbox()


def test_require_sandbox_accepts_sandbox_profile(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setenv("AWS_PROFILE", "sura-sandbox")
    require_sandbox()


def test_target_parse_cluster_kwargs():
    t = Target.parse("cluster:rr-ra3")
    assert t.api_kwargs() == {"ClusterIdentifier": "rr-ra3", "Database": "tpcds", "DbUser": "awsuser"}


def test_target_parse_workgroup_kwargs():
    t = Target.parse("workgroup:rr-sls")
    assert t.api_kwargs() == {"WorkgroupName": "rr-sls", "Database": "tpcds"}


@pytest.mark.parametrize("bad", ["rr-ra3", "cluster:", "db:rr-ra3"])
def test_target_parse_rejects_bad_specs(bad):
    with pytest.raises(ValueError):
        Target.parse(bad)
```

- [ ] **Step 3: Run to see them fail**

Run: `cd runner && uv run pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rr.config'`

- [ ] **Step 4: Implement**

`runner/rr/config.py`:

```python
import os
from dataclasses import dataclass

REGION = "us-east-1"


def require_sandbox() -> None:
    """Refuse to touch AWS unless the personal sandbox profile or CI OIDC is in use."""
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return
    profile = os.environ.get("AWS_PROFILE", "")
    if "sandbox" not in profile:
        raise RuntimeError(
            "AWS_PROFILE must be the personal sandbox profile (name contains 'sandbox'); "
            "refusing to use default credentials"
        )


@dataclass(frozen=True)
class Target:
    kind: str  # "cluster" | "workgroup"
    name: str
    database: str = "tpcds"
    db_user: str = "awsuser"

    @classmethod
    def parse(cls, spec: str) -> "Target":
        kind, _, name = spec.partition(":")
        if kind not in ("cluster", "workgroup") or not name:
            raise ValueError(f"target must be cluster:<id> or workgroup:<name>, got {spec!r}")
        return cls(kind, name)

    def api_kwargs(self) -> dict:
        if self.kind == "cluster":
            return {"ClusterIdentifier": self.name, "Database": self.database, "DbUser": self.db_user}
        return {"WorkgroupName": self.name, "Database": self.database}


def data_client():
    import boto3
    from botocore.config import Config

    require_sandbox()
    return boto3.client(
        "redshift-data", region_name=REGION, config=Config(retries={"mode": "standard", "max_attempts": 10})
    )
```

- [ ] **Step 5: Run the tests**

Run: `cd runner && uv run pytest tests/test_config.py -v`
Expected: 7 passed

- [ ] **Step 6: Commit**

```bash
git add runner
git commit -m "feat(runner): project, sandbox guard and Data API targets"
```

---

### Task 3: Vendored SQL, DDL split, curated list and parsers

**Files:**
- Create: `sql/vendor/query_0.sql`, `sql/vendor/ddl.sql` (downloaded, unmodified)
- Create: `scripts/split-ddl.sh` → generates `sql/tables.sql`, `sql/copy.sql`, `sql/expected_counts_1tb.csv`
- Create: `sql/curated.txt`
- Create: `runner/rr/queries.py`
- Test: `runner/tests/test_queries.py`

**Interfaces:**
- Produces:
  - `parse_blocks(text: str) -> dict[str, list[str]]` — `-- start template <name>` … `-- end template` blocks; `<name>` is `[A-Za-z0-9_]+` (so `query96.tpl` → `query96`); value = statements split on `;`
  - `split_statements(sql: str) -> list[str]`
  - `render(text: str, values: dict[str, str]) -> str` — replaces `{key}`; raises `ValueError` if any `{word}` remains
  - `load_curated(path: str, bench: dict) -> dict[str, str]` — `name -> class` (`scan` | `cpu`), raises if a name is not in `bench`
  - `load_blocks(tables_sql: str, copy_sql: str, scale: str) -> dict[str, list[str]]` — `{"tables": [...create...], "<table>": [copy]}` with the scale path rendered
  - `SCALES = ("100GB", "1TB")`
- Facts (verified 2026-09-24): `query_0.sql` has 99 blocks / 103 statements; two-statement blocks are `query14`, `query23`, `query24`, `query39`. `ddl.sql` has 25 `create table`, 24 `copy`, 24 `select count(*)` lines with expected 1 TB counts, and a `/* … */` comment block (lines 554–570) that contains a `;`, which is why it is split by script instead of parsed.

- [ ] **Step 1: Vendor the awslabs files**

```bash
mkdir -p sql/vendor scripts
base=https://raw.githubusercontent.com/awslabs/amazon-redshift-utils/master/src/CloudDataWarehouseBenchmark/Cloud-DWB-Derived-from-TPCDS/1TB
curl -sfL "$base/queries/query_0.sql" -o sql/vendor/query_0.sql
curl -sfL "$base/ddl.sql" -o sql/vendor/ddl.sql
git ls-remote https://github.com/awslabs/amazon-redshift-utils HEAD
```

Record the commit hash from `git ls-remote` in README "Versiones probadas" (source of the vendored files).

- [ ] **Step 2: Write the split script**

`scripts/split-ddl.sh`:

```bash
#!/usr/bin/env bash
# Splits the vendored awslabs ddl.sql into the three files the runner reads.
# The vendor file has a /* */ comment containing a ';', so it is never parsed whole.
set -euo pipefail
cd "$(dirname "$0")/.."
src=sql/vendor/ddl.sql
sed -n '1,/^\/\*/p' "$src" | sed '$d' > sql/tables.sql
grep '^copy ' "$src" > sql/copy.sql
grep '^select count' "$src" \
  | sed -E 's/^select count\(\*\) from ([a-z_]+); *-- *([0-9]+).*/\1,\2/' \
  | { echo "table,rows"; cat; } > sql/expected_counts_1tb.csv
echo "tables: $(grep -c '^create table' sql/tables.sql) copy: $(wc -l < sql/copy.sql | tr -d ' ') counts: $(($(wc -l < sql/expected_counts_1tb.csv) - 1))"
```

Run: `bash scripts/split-ddl.sh`
Expected: `tables: 25 copy: 24 counts: 24`

- [ ] **Step 3: Write the curated list**

`sql/curated.txt` (name, class; `scan` = bandwidth-bound scans/aggregations, `cpu` = join/window/CPU-bound):

```
# name      class   why
query3      scan    one fact table, filter + group by
query7      scan    fact + 4 dims, averages
query19     scan    fact + 5 dims, group by brand
query28     scan    six aggregate buckets over store_sales
query42     scan    fact + 2 dims, group by category
query43     scan    weekday pivot over store_sales
query48     scan    wide OR predicates, single sum
query52     scan    fact + 2 dims, group by brand
query55     scan    fact + 2 dims, group by brand
query96     scan    count with 3 dims
query14     cpu     cross-channel intersect, 2 statements
query23     cpu     frequent items/best customers, 2 statements
query47     cpu     window functions over monthly sales
query57     cpu     window functions over catalog sales
query64     cpu     15-way join
query67     cpu     rollup + rank
query72     cpu     inventory join, large intermediate
query78     cpu     3 channel CTEs joined
query89     cpu     window avg per group
query98     cpu     ratio window over category
```

- [ ] **Step 4: Write the failing tests**

`runner/tests/test_queries.py`:

```python
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
    assert "/2.13/100GB/store_sales/" in blocks["store_sales"][0]


def test_load_blocks_rejects_unknown_scale():
    with pytest.raises(ValueError):
        load_blocks(str(SQL / "tables.sql"), str(SQL / "copy.sql"), "10TB")
```

- [ ] **Step 5: Run to see them fail**

Run: `cd runner && uv run pytest tests/test_queries.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rr.queries'`

- [ ] **Step 6: Implement**

`runner/rr/queries.py`:

```python
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
    blocks = {"tables": split_statements(open(tables_sql).read())}
    for line in open(copy_sql):
        stmt = line.strip().rstrip(";").replace("/2.13/1TB/", f"/2.13/{scale}/")
        blocks[_COPY_TABLE.match(stmt).group(1)] = [stmt]
    return blocks
```

- [ ] **Step 7: Run the tests**

Run: `cd runner && uv run pytest tests/test_queries.py -v`
Expected: 9 passed

- [ ] **Step 8: Commit**

```bash
git add sql scripts runner
git commit -m "feat(sql): vendored TPC-DS-derived queries/DDL, curated 20 and parsers"
```

---

### Task 4: Data API executor

**Files:**
- Create: `runner/rr/dataapi.py`
- Create: `runner/tests/fakes.py`
- Test: `runner/tests/test_dataapi.py`

**Interfaces:**
- Consumes: `Target.api_kwargs()` (Task 2)
- Produces:
  - `@dataclass class BatchResult(label: str, status: str, statement_id: str, duration_s: float, error: str = "")` — `status` ∈ `FINISHED | FAILED | ABORTED | TIMEOUT`
  - `preamble(label: str) -> list[str]` — `["SET enable_result_cache_for_session TO off", "SET query_group TO '<label>'"]`
  - `run_batch(client, target, label, sqls, *, poll_s=2.0, timeout_s=3600, sleep=time.sleep, clock=time.monotonic) -> BatchResult` — `batch_execute_statement` (one session, so the SETs apply), polls `describe_statement`, cancels on timeout
  - `fetch(client, target, sql, *, poll_s=1.0, timeout_s=600, sleep=time.sleep, clock=time.monotonic) -> list[dict]` — `execute_statement` + paginated `get_statement_result`, rows as `{column: value}`
- API facts to re-verify on the day (boto3 `redshift-data` docs): `describe_statement` returns `Status`, `Duration` (nanoseconds), `Error`; `get_statement_result` returns `ColumnMetadata[].name`, `Records[][]` of one-key dicts (`stringValue`, `longValue`, `doubleValue`, `booleanValue`, `isNull`), `NextToken`.

- [ ] **Step 1: Write the fake client**

`runner/tests/fakes.py`:

```python
class FakeDataClient:
    """Scripted stand-in for boto3 redshift-data: each statement walks through `statuses`."""

    def __init__(self, statuses=("STARTED", "FINISHED"), duration_ns=2_000_000_000, error="", pages=None):
        self.statuses = list(statuses)
        self.duration_ns = duration_ns
        self.error = error
        self.pages = pages or []
        self.calls = []
        self._polls = {}

    def batch_execute_statement(self, **kw):
        self.calls.append(("batch", kw))
        return {"Id": f"s{len(self.calls)}"}

    def execute_statement(self, **kw):
        self.calls.append(("exec", kw))
        return {"Id": f"s{len(self.calls)}"}

    def describe_statement(self, Id):
        n = self._polls.get(Id, 0)
        self._polls[Id] = n + 1
        status = self.statuses[min(n, len(self.statuses) - 1)]
        return {"Id": Id, "Status": status, "Duration": self.duration_ns, "Error": self.error}

    def cancel_statement(self, Id):
        self.calls.append(("cancel", {"Id": Id}))
        return {"Status": True}

    def get_statement_result(self, Id, NextToken=None):
        index = int(NextToken or 0)
        page = dict(self.pages[index])
        if index + 1 < len(self.pages):
            page["NextToken"] = str(index + 1)
        return page
```

- [ ] **Step 2: Write the failing tests**

`runner/tests/test_dataapi.py`:

```python
from rr.config import Target
from rr.dataapi import fetch, preamble, run_batch
from tests.fakes import FakeDataClient

T = Target.parse("cluster:rr-ra3")


def test_run_batch_prepends_cache_off_and_label():
    client = FakeDataClient()
    r = run_batch(client, T, "a1b2.p1.96", ["select 1"], sleep=lambda s: None)
    kind, kw = client.calls[0]
    assert kind == "batch"
    assert kw["Sqls"] == preamble("a1b2.p1.96") + ["select 1"]
    assert kw["ClusterIdentifier"] == "rr-ra3"
    assert (r.status, r.duration_s) == ("FINISHED", 2.0)


def test_run_batch_reports_failure_with_error():
    client = FakeDataClient(statuses=("FAILED",), error="relation does not exist")
    r = run_batch(client, T, "a1b2.p1.3", ["select * from nope"], sleep=lambda s: None)
    assert (r.status, r.error) == ("FAILED", "relation does not exist")


def test_run_batch_timeout_cancels():
    client = FakeDataClient(statuses=("STARTED",))
    ticks = iter(range(0, 10_000, 100))
    r = run_batch(client, T, "a1b2.p1.72", ["select 1"], timeout_s=250, sleep=lambda s: None, clock=lambda: next(ticks))
    assert r.status == "TIMEOUT"
    assert ("cancel", {"Id": r.statement_id}) in client.calls


def test_fetch_paginates_and_maps_values():
    pages = [
        {"ColumnMetadata": [{"name": "query_label"}, {"name": "result_cache_hit"}],
         "Records": [[{"stringValue": "a1b2.p1.3"}, {"booleanValue": False}]]},
        {"ColumnMetadata": [{"name": "query_label"}, {"name": "result_cache_hit"}],
         "Records": [[{"stringValue": "a1b2.p1.7"}, {"isNull": True}]]},
    ]
    rows = fetch(FakeDataClient(pages=pages), T, "select 1", sleep=lambda s: None)
    assert rows == [
        {"query_label": "a1b2.p1.3", "result_cache_hit": False},
        {"query_label": "a1b2.p1.7", "result_cache_hit": None},
    ]
```

Add `runner/tests/__init__.py` (empty) so `tests.fakes` imports, and set `pythonpath = ["."]` under `[tool.pytest.ini_options]` in `runner/pyproject.toml`.

- [ ] **Step 3: Run to see them fail**

Run: `cd runner && uv run pytest tests/test_dataapi.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rr.dataapi'`

- [ ] **Step 4: Implement**

`runner/rr/dataapi.py`:

```python
import time
from dataclasses import dataclass

TERMINAL = {"FINISHED", "FAILED", "ABORTED"}


@dataclass
class BatchResult:
    label: str
    status: str  # FINISHED | FAILED | ABORTED | TIMEOUT
    statement_id: str
    duration_s: float  # Data API wall clock for the batch; server-side timings come from SYS_QUERY_HISTORY
    error: str = ""


def preamble(label: str) -> list[str]:
    return ["SET enable_result_cache_for_session TO off", f"SET query_group TO '{label}'"]


def _wait(client, sid, poll_s, timeout_s, sleep, clock):
    start = clock()
    while True:
        d = client.describe_statement(Id=sid)
        if d["Status"] in TERMINAL:
            return d, clock() - start
        if clock() - start > timeout_s:
            client.cancel_statement(Id=sid)
            return None, clock() - start
        sleep(poll_s)


def run_batch(client, target, label, sqls, *, poll_s=2.0, timeout_s=3600, sleep=time.sleep, clock=time.monotonic):
    # AUTO_COMMIT: same session (the SETs stick) but no wrapping transaction, which
    # CREATE EXTERNAL TABLE and VACUUM refuse to run inside.
    sid = client.batch_execute_statement(Sqls=preamble(label) + list(sqls), StatementName=label,
                                         ExecutionMode="AUTO_COMMIT", **target.api_kwargs())["Id"]
    d, waited = _wait(client, sid, poll_s, timeout_s, sleep, clock)
    if d is None:
        return BatchResult(label, "TIMEOUT", sid, waited, f"timeout after {timeout_s}s")
    return BatchResult(label, d["Status"], sid, d.get("Duration", 0) / 1e9, d.get("Error", ""))


def _value(field: dict):
    if field.get("isNull"):
        return None
    (value,) = field.values()
    return value


def fetch(client, target, sql, *, poll_s=1.0, timeout_s=600, sleep=time.sleep, clock=time.monotonic):
    sid = client.execute_statement(Sql=sql, **target.api_kwargs())["Id"]
    d, _ = _wait(client, sid, poll_s, timeout_s, sleep, clock)
    if d is None:
        raise TimeoutError(sql[:80])
    if d["Status"] != "FINISHED":
        raise RuntimeError(d.get("Error") or d["Status"])
    rows, token = [], None
    while True:
        page = client.get_statement_result(Id=sid, **({"NextToken": token} if token else {}))
        cols = [c["name"] for c in page["ColumnMetadata"]]
        rows += [dict(zip(cols, map(_value, rec))) for rec in page["Records"]]
        token = page.get("NextToken")
        if not token:
            return rows
```

- [ ] **Step 5: Run the tests**

Run: `cd runner && uv run pytest -v`
Expected: all passed (config, queries, dataapi)

- [ ] **Step 6: Commit**

```bash
git add runner
git commit -m "feat(runner): Data API batch executor with cache-off preamble, labels, timeout"
```

---

### Task 5: Scenarios and CSV output

**Files:**
- Create: `runner/rr/scenarios.py`, `runner/rr/results.py`
- Test: `runner/tests/test_scenarios.py`

**Interfaces:**
- Consumes: `BatchResult` (Task 4)
- Produces:
  - `new_run_id() -> str` (4 hex chars)
  - `make_label(run_id: str, tag: str, name: str) -> str` — `f"{run_id}.{tag}.{name.removeprefix('query')}"`, `[a-z0-9_.]` only, ≤ 30 chars, else `ValueError`
  - `@dataclass class Row(run_id, scenario, stream: int, pass_no: int, name, label, status, api_seconds: float, error: str)`
  - `Exec = Callable[[str, list[str]], BatchResult]` — `(label, sqls) -> BatchResult`
  - `serial(exec_fn, blocks, *, run_id, scenario, passes) -> list[Row]` — tag `f"{scenario[0]}{pass}"`
  - `concurrent(exec_fn, blocks, *, run_id, streams, duration_s, seed, clock=time.monotonic) -> list[Row]` — each stream runs its own seeded shuffle of all blocks until the deadline; tag `f"s{stream}{round}"`
  - `write_rows(path: str, rows: list) -> None`, `read_rows(path: str) -> list[dict]` (csv, header from dataclass fields)

- [ ] **Step 1: Write the failing tests**

`runner/tests/test_scenarios.py`:

```python
import pytest

from rr.dataapi import BatchResult
from rr.results import read_rows, write_rows
from rr.scenarios import concurrent, make_label, new_run_id, serial

BLOCKS = {"query3": ["select 3"], "query96": ["select 96"]}


def ok(label, sqls):
    return BatchResult(label, "FINISHED", "s1", 1.5)


def test_make_label_format():
    assert make_label("a1b2", "p1", "query96") == "a1b2.p1.96"


@pytest.mark.parametrize("name", ["x" * 30, "query3'; drop table x; --", "Query3"])
def test_make_label_rejects_long_and_unsafe(name):
    with pytest.raises(ValueError):
        make_label("a1b2", "p1", name)


def test_new_run_id_is_4_hex():
    rid = new_run_id()
    assert len(rid) == 4 and int(rid, 16) >= 0


def test_serial_runs_every_block_every_pass_in_order():
    rows = serial(ok, BLOCKS, run_id="a1b2", scenario="power", passes=3)
    assert [(r.pass_no, r.name) for r in rows] == [(p, n) for p in (1, 2, 3) for n in BLOCKS]
    assert rows[0].label == "a1b2.p1.3"


def test_serial_records_failure_and_continues():
    def flaky(label, sqls):
        return BatchResult(label, "FAILED" if label.endswith(".3") else "FINISHED", "s", 0.1, "boom" if label.endswith(".3") else "")

    rows = serial(flaky, BLOCKS, run_id="a1b2", scenario="power", passes=1)
    assert [(r.name, r.status, r.error) for r in rows] == [("query3", "FAILED", "boom"), ("query96", "FINISHED", "")]


def test_concurrent_single_stream_runs_whole_shuffled_rounds_until_deadline():
    calls = []

    def exec_fn(label, sqls):
        calls.append(label)
        return ok(label, sqls)

    # deadline = 0 + 4; the clock jumps past it once 4 statements ran (two rounds of 2 blocks)
    rows = concurrent(exec_fn, BLOCKS, run_id="a1b2", streams=1, duration_s=4, seed=7,
                      clock=lambda: 0 if len(calls) < 4 else 10)
    assert [(r.pass_no, r.stream) for r in rows] == [(1, 1), (1, 1), (2, 1), (2, 1)]
    for rnd in (1, 2):
        assert sorted(r.name for r in rows if r.pass_no == rnd) == sorted(BLOCKS)


def test_concurrent_labels_unique_across_streams():
    calls = []

    def exec_fn(label, sqls):
        calls.append(label)
        return ok(label, sqls)

    rows = concurrent(exec_fn, BLOCKS, run_id="a1b2", streams=3, duration_s=4, seed=7,
                      clock=lambda: 0 if len(calls) < 12 else 10)
    assert rows and {r.stream for r in rows} <= {1, 2, 3}
    assert all(r.label.startswith("a1b2.s") for r in rows)
    assert len({r.label for r in rows}) == len(rows)


def test_write_and_read_rows_roundtrip(tmp_path):
    rows = serial(ok, BLOCKS, run_id="a1b2", scenario="power", passes=1)
    path = tmp_path / "out.csv"
    write_rows(str(path), rows)
    back = read_rows(str(path))
    assert [r["label"] for r in back] == ["a1b2.p1.3", "a1b2.p1.96"]
```

- [ ] **Step 2: Run to see them fail**

Run: `cd runner && uv run pytest tests/test_scenarios.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rr.results'`

- [ ] **Step 3: Implement**

`runner/rr/scenarios.py`:

```python
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
```

`runner/rr/results.py`:

```python
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
```

- [ ] **Step 4: Run the tests**

Run: `cd runner && uv run pytest -v`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add runner
git commit -m "feat(runner): serial and concurrent scenarios with safe labels and CSV rows"
```

---

### Task 6: Server-side metrics and validity checks

**Files:**
- Create: `runner/rr/metrics.py`
- Test: `runner/tests/test_metrics.py`

**Interfaces:**
- Consumes: `fetch` (Task 4), rows from `read_rows` (Task 5)
- Produces:
  - `history_sql(run_id: str) -> str` — `SYS_QUERY_HISTORY` rows whose `query_label LIKE '<run_id>.%'` and `query_type <> 'UTILITY'` (drops the two SETs)
  - `external_sql(run_id: str) -> str` — `SUM(returned_bytes)` from `SYS_EXTERNAL_QUERY_DETAIL` joined on `query_id`, per label (for S3 sources `returned_bytes` = bytes scanned)
  - `aggregate(history: list[dict], external: list[dict]) -> dict[str, dict]` — per label: `elapsed_s, queue_s, exec_s, compile_s, planning_s` (sums over the block's statements, µs → s), `status` (`success` only if all statements succeeded), `cache_hit`, `compute_types`, `versions`, `scanned_bytes`
  - `problems(history: list[dict]) -> list[str]`
  - `timings(rows: list[dict], agg: dict) -> list[dict]` — run rows joined with `agg` by label; a row missing from history keeps its runner status and empty timings
- Column facts (verified 2026-09-24, SYS_QUERY_HISTORY docs): `query_label`, `query_id`, `query_type`, `status` (`success`/`failed`/`canceled`…), `result_cache_hit` (bool), `compute_type` (`primary`/`secondary`/`primary-scale`, provisioned only), `redshift_version`, `elapsed_time`/`queue_time`/`execution_time`/`compile_time`/`planning_time` in µs. SYS_EXTERNAL_QUERY_DETAIL: `query_id`, `source_type`, `returned_bytes` (scanned bytes for S3), `file_format`.

- [ ] **Step 1: Write the failing tests**

`runner/tests/test_metrics.py`:

```python
import pytest

from rr.metrics import aggregate, external_sql, history_sql, problems, timings


def h(label, qid, **kw):
    base = {"query_label": label, "query_id": qid, "query_type": "SELECT", "status": "success",
            "result_cache_hit": False, "compute_type": "primary", "redshift_version": "1.0.99999",
            "elapsed_time": 2_000_000, "queue_time": 0, "execution_time": 1_500_000,
            "compile_time": 100_000, "planning_time": 50_000}
    base.update(kw)
    return base


def test_history_sql_filters_run_and_utility():
    sql = history_sql("a1b2")
    assert "query_label LIKE 'a1b2.%'" in sql and "query_type <> 'UTILITY'" in sql


@pytest.mark.parametrize("bad", ["a1b2'--", "zzzz", "a1b2c"])
def test_history_sql_rejects_bad_run_id(bad):
    with pytest.raises(ValueError):
        history_sql(bad)


def test_external_sql_joins_on_query_id():
    assert "sys_external_query_detail" in external_sql("a1b2").lower()


def test_aggregate_sums_two_statement_block():
    agg = aggregate([h("a1b2.p1.14", 1), h("a1b2.p1.14", 2, elapsed_time=3_000_000)], [])
    assert agg["a1b2.p1.14"]["elapsed_s"] == 5.0
    assert agg["a1b2.p1.14"]["status"] == "success"


def test_aggregate_block_fails_if_any_statement_failed():
    agg = aggregate([h("a1b2.p1.14", 1), h("a1b2.p1.14", 2, status="failed")], [])
    assert agg["a1b2.p1.14"]["status"] == "failed"


def test_aggregate_adds_scanned_bytes():
    agg = aggregate([h("a1b2.l1.lq3", 9)], [{"query_label": "a1b2.l1.lq3", "scanned_bytes": 1024}])
    assert agg["a1b2.l1.lq3"]["scanned_bytes"] == 1024


def test_problems_clean_run_is_empty():
    assert problems([h("a1b2.p1.3", 1), h("a1b2.p1.7", 2)]) == []


def test_problems_flags_cache_hit_and_scaling():
    found = problems([h("a1b2.p1.3", 1, result_cache_hit=True), h("a1b2.p1.7", 2, compute_type="primary-scale")])
    assert any("result cache" in p for p in found)
    assert any("primary-scale" in p for p in found)


def test_problems_accepts_serverless_empty_compute_type():
    assert problems([h("a1b2.p1.3", 1, compute_type=None), h("a1b2.p1.7", 2, compute_type="")]) == []


def test_problems_flags_version_mix():
    found = problems([h("a1b2.p1.3", 1), h("a1b2.p1.7", 2, redshift_version="1.0.11111")])
    assert any("version" in p for p in found)


def test_timings_keeps_rows_missing_from_history():
    rows = [{"label": "a1b2.p1.3", "name": "query3", "pass_no": "1", "stream": "0", "status": "TIMEOUT"}]
    out = timings(rows, {})
    assert out[0]["status"] == "TIMEOUT" and out[0]["elapsed_s"] == ""
```

- [ ] **Step 2: Run to see them fail**

Run: `cd runner && uv run pytest tests/test_metrics.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rr.metrics'`

- [ ] **Step 3: Implement**

`runner/rr/metrics.py`:

```python
import re
from collections import defaultdict

_RUN = re.compile(r"^[0-9a-f]{4}$")
_US = {"elapsed_s": "elapsed_time", "queue_s": "queue_time", "exec_s": "execution_time",
       "compile_s": "compile_time", "planning_s": "planning_time"}


def _check(run_id: str) -> str:
    if not _RUN.match(run_id):
        raise ValueError(f"run id must be 4 hex chars, got {run_id!r}")
    return run_id


def history_sql(run_id: str) -> str:
    return f"""
SELECT TRIM(query_label) AS query_label, query_id, TRIM(query_type) AS query_type, TRIM(status) AS status,
       result_cache_hit, TRIM(compute_type) AS compute_type, TRIM(redshift_version) AS redshift_version,
       elapsed_time, queue_time, execution_time, compile_time, planning_time
FROM sys_query_history
WHERE query_label LIKE '{_check(run_id)}.%' AND query_type <> 'UTILITY'
ORDER BY start_time"""


def external_sql(run_id: str) -> str:
    return f"""
SELECT TRIM(h.query_label) AS query_label, SUM(e.returned_bytes) AS scanned_bytes
FROM sys_external_query_detail e JOIN sys_query_history h ON h.query_id = e.query_id
WHERE h.query_label LIKE '{_check(run_id)}.%' AND TRIM(e.source_type) = 'S3'
GROUP BY 1"""


def aggregate(history: list[dict], external: list[dict]) -> dict[str, dict]:
    agg = defaultdict(lambda: {**{k: 0.0 for k in _US}, "status": "success", "cache_hit": False,
                               "compute_types": set(), "versions": set(), "scanned_bytes": 0})
    for q in history:
        a = agg[q["query_label"]]
        for key, col in _US.items():
            a[key] += (q[col] or 0) / 1e6
        if q["status"] != "success":
            a["status"] = q["status"]
        a["cache_hit"] |= bool(q["result_cache_hit"])
        a["compute_types"].add(q["compute_type"] or "")
        a["versions"].add(q["redshift_version"])
    for e in external:
        agg[e["query_label"]]["scanned_bytes"] = int(e["scanned_bytes"] or 0)
    return dict(agg)


def problems(history: list[dict]) -> list[str]:
    found = []
    hits = sorted({q["query_label"] for q in history if q["result_cache_hit"]})
    if hits:
        found.append(f"result cache hit on {len(hits)} labels: {hits[:5]}")
    scaled = sorted({(q["query_label"], q["compute_type"]) for q in history
                     if (q["compute_type"] or "") not in ("", "primary")})
    if scaled:
        found.append(f"non-primary compute_type (concurrency scaling?): {scaled[:5]}")
    versions = {q["redshift_version"] for q in history}
    if len(versions) > 1:
        found.append(f"run spans several Redshift versions: {sorted(versions)}")
    return found


def timings(rows: list[dict], agg: dict) -> list[dict]:
    out = []
    for r in rows:
        a = agg.get(r["label"])
        extra = {k: (round(a[k], 6) if a else "") for k in _US}
        extra["scanned_bytes"] = a["scanned_bytes"] if a else ""
        extra["server_status"] = a["status"] if a else ""
        out.append({**r, **extra})
    return out
```

- [ ] **Step 4: Run the tests**

Run: `cd runner && uv run pytest -v`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add runner
git commit -m "feat(runner): server-side timings by label and validity checks"
```

---

### Task 7: Stats and cost

**Files:**
- Create: `runner/rr/stats.py`, `runner/rr/cost.py`, `results/prices.md`
- Test: `runner/tests/test_stats.py`, `runner/tests/test_cost.py`

**Interfaces:**
- Consumes: timing dicts from `metrics.timings` (Task 6; numeric fields may arrive as strings from CSV)
- Produces:
  - `percentile(values: list[float], q: float) -> float` (linear interpolation, `q` in 0–100)
  - `per_query(timings: list[dict], warmup: int = 1) -> dict[str, float]` — median `elapsed_s` per name over passes > `warmup`, only rows with `server_status == "success"`
  - `summary(per_q: dict[str, float]) -> dict` — `{"n", "total_s", "p50_s", "p95_s"}`
  - `speedups(base: dict, cand: dict) -> dict[str, float]` — `base/cand` for names in both
  - `geomean(values) -> float`
  - `by_class(sp: dict, classes: dict[str, str]) -> dict[str, float]` — geomean per class
  - `throughput(timings, duration_s) -> dict` — `{"queries_per_hour", "queue_p50_s", "queue_p95_s", "failed"}`
  - `load_prices(path: str) -> dict[str, float]` — reads `results/prices.md` table, raises on `TODO`
  - `cluster_usd(prices, node_type, nodes, seconds) -> float`
  - `spectrum_usd(prices, scanned_bytes_per_query: list[int]) -> float` — per query `max(bytes, 10 MB)`, TB = 2^40 bytes, × `prices["spectrum_per_tb"]` (re-verify minimum and TB definition on the pricing page on the day)

- [ ] **Step 1: Write the price template**

`results/prices.md`:

```markdown
# Tarifas del lab

Única fuente de precios del proyecto. Se completa el día del lab con la tarifa
on-demand vigente en us-east-1; `rr report` se niega a calcular mientras alguna
celda diga TODO.

Cómo leerlas (API de precios, la misma que usó el spec el 2026-09-24):

    aws pricing get-products --region us-east-1 --service-code AmazonRedshift \
      --filters Type=TERM_MATCH,Field=instanceType,Value=rg.xlarge \
                Type=TERM_MATCH,Field=location,Value='US East (N. Virginia)'

| item | usd | unit | captured (date, source) |
|---|---|---|---|
| ra3.xlplus | TODO | node-hour | |
| rg.xlarge | TODO | node-hour | |
| ra3.4xlarge | TODO | node-hour | |
| rg.4xlarge | TODO | node-hour | |
| serverless_rpu | TODO | RPU-hour | |
| spectrum_per_tb | TODO | TB scanned | |
| rms_gb_month | TODO | GB-month | |
```

- [ ] **Step 2: Write the failing tests**

`runner/tests/test_stats.py`:

```python
import pytest

from rr.stats import by_class, geomean, per_query, percentile, speedups, summary, throughput


def t(name, pass_no, elapsed, status="success", queue=0.0):
    return {"name": name, "pass_no": str(pass_no), "elapsed_s": str(elapsed), "queue_s": str(queue),
            "server_status": status}


def test_percentile_interpolates():
    assert percentile([1, 2, 3, 4], 50) == 2.5
    assert percentile([5], 95) == 5


def test_per_query_drops_warmup_and_failures():
    rows = [t("q3", 1, 100), t("q3", 2, 10), t("q3", 3, 12), t("q7", 2, 5, status="failed"), t("q7", 3, 7)]
    assert per_query(rows) == {"q3": 11.0, "q7": 7.0}


def test_summary():
    s = summary({"a": 1.0, "b": 3.0})
    assert s == {"n": 2, "total_s": 4.0, "p50_s": 2.0, "p95_s": pytest.approx(2.9)}


def test_speedups_and_geomean_and_classes():
    sp = speedups({"a": 4.0, "b": 9.0, "only_base": 1.0}, {"a": 2.0, "b": 3.0})
    assert sp == {"a": 2.0, "b": 3.0}
    assert geomean(sp.values()) == pytest.approx(6 ** 0.5)
    assert by_class(sp, {"a": "scan", "b": "cpu"}) == {"scan": pytest.approx(2.0), "cpu": pytest.approx(3.0)}


def test_throughput_counts_success_per_hour():
    rows = [t("a", 1, 1, queue=0.5), t("b", 1, 1, queue=1.5), t("c", 1, 1, status="failed")]
    out = throughput(rows, duration_s=1800)
    assert out["queries_per_hour"] == 4.0 and out["failed"] == 1 and out["queue_p50_s"] == 1.0
```

`runner/tests/test_cost.py`:

```python
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
```

- [ ] **Step 3: Run to see them fail**

Run: `cd runner && uv run pytest tests/test_stats.py tests/test_cost.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rr.stats'`

- [ ] **Step 4: Implement**

`runner/rr/stats.py`:

```python
import math
from collections import defaultdict
from statistics import median


def percentile(values: list[float], q: float) -> float:
    xs = sorted(values)
    if len(xs) == 1:
        return float(xs[0])
    pos = (len(xs) - 1) * q / 100
    lo, hi = math.floor(pos), math.ceil(pos)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def _ok(rows):
    return [r for r in rows if r["server_status"] == "success"]


def per_query(timings: list[dict], warmup: int = 1) -> dict[str, float]:
    by_name = defaultdict(list)
    for r in _ok(timings):
        if int(r["pass_no"]) > warmup:
            by_name[r["name"]].append(float(r["elapsed_s"]))
    return {name: median(xs) for name, xs in by_name.items()}


def summary(per_q: dict[str, float]) -> dict:
    xs = list(per_q.values())
    return {"n": len(xs), "total_s": sum(xs), "p50_s": percentile(xs, 50), "p95_s": percentile(xs, 95)}


def speedups(base: dict, cand: dict) -> dict[str, float]:
    return {k: base[k] / cand[k] for k in base if k in cand and cand[k] > 0}


def geomean(values) -> float:
    xs = list(values)
    return math.exp(sum(math.log(x) for x in xs) / len(xs))


def by_class(sp: dict, classes: dict[str, str]) -> dict[str, float]:
    groups = defaultdict(list)
    for name, value in sp.items():
        groups[classes[name]].append(value)
    return {cls: geomean(vs) for cls, vs in groups.items()}


def throughput(timings: list[dict], duration_s: float) -> dict:
    ok = _ok(timings)
    queues = [float(r["queue_s"]) for r in ok] or [0.0]
    return {"queries_per_hour": len(ok) * 3600 / duration_s, "queue_p50_s": percentile(queues, 50),
            "queue_p95_s": percentile(queues, 95), "failed": len(timings) - len(ok)}
```

`runner/rr/cost.py`:

```python
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
```

- [ ] **Step 5: Run the tests**

Run: `cd runner && uv run pytest -v`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add runner results/prices.md
git commit -m "feat(runner): per-query medians, speedups by class, throughput and cost"
```

---

### Task 8: CLI

**Files:**
- Create: `runner/rr/cli.py`
- Test: `runner/tests/test_cli.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `rr <command>`; every AWS command calls `require_sandbox()` (through `data_client()`), prints the run id, and writes `results/<YYYY-MM-DD>/<target-name>-<scenario>-<run>.csv`:
  - `rr load --target T --scale {100GB,1TB}` — `tables` block, then one COPY block per table (per-table load time)
  - `rr power --target T [--passes 3]` — curated 20
  - `rr concurrency --target T [--streams 5] [--minutes 30] [--seed 7]`
  - `rr lake --target T --variant {local,s3tables,glue,parquet} [--passes 3]` — renders `{lake}` in `sql/lake_queries.sql`
  - `rr elt --target T --scale S [--passes 2]`
  - `rr sql --target T --file F [--var k=v ...]` — every block of a marker file once (lake builds)
  - `rr metrics --target T --csv RUN_CSV` — writes `<RUN_CSV stem>-timings.csv`, prints `problems()`; exits 3 if any
  - `rr report --base TIMINGS --cand TIMINGS [--classes sql/curated.txt] --out summary.md` — power table, class geomeans, `$ /benchmark` with `results/prices.md` (`--base-node ra3.xlplus --cand-node rg.xlarge --nodes 2`)
- Helpers: `out_path(target: Target, scenario: str, run_id: str, day: str) -> str`; `LAKE_PREFIX = {"local": "", "s3tables": '"rr-lake@s3tablescatalog".tpcds.', "glue": "awsdatacatalog.rr_iceberg.", "parquet": "pq."}`

- [ ] **Step 1: Write the failing tests**

`runner/tests/test_cli.py`:

```python
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
```

- [ ] **Step 2: Run to see them fail**

Run: `cd runner && uv run pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rr.cli'`

- [ ] **Step 3: Implement**

`runner/rr/cli.py`:

```python
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
```

- [ ] **Step 4: Run the tests**

Run: `cd runner && uv run pytest -v`
Expected: all passed

- [ ] **Step 5: Smoke the entry point without AWS**

Run: `cd runner && uv run rr power --help && AWS_PROFILE=default uv run rr power --target cluster:rr-ra3; echo "exit $?"`
Expected: help text, then a `RuntimeError: AWS_PROFILE must be the personal sandbox profile…` traceback and a non-zero exit (the guard fires before any AWS call)

- [ ] **Step 6: Commit**

```bash
git add runner
git commit -m "feat(runner): rr CLI for load, scenarios, metrics and report"
```

---

### Task 9: Lake and ELT SQL

**Files:**
- Create: `sql/lake_build_s3tables.sql`, `sql/lake_build_glue.sql`, `sql/lake_build_parquet.sql`, `sql/lake_queries.sql`, `sql/elt.sql`
- Test: `runner/tests/test_sql_files.py`

**Interfaces:**
- Consumes: `parse_blocks`, `render` (Task 3); `LAKE_PREFIX` (Task 8)
- Produces: marker files the CLI runs. Placeholders: `{bucket}` (lake bucket name, from terraform output), `{lake}` (prefix), `{scale}`.
- Syntax facts (Redshift docs, iceberg-writes-sql-syntax, verified 2026-09-24): `CREATE TABLE "<bucket>@s3tablescatalog".<ns>.<t> USING ICEBERG AS SELECT …` (no LOCATION for table buckets); `CREATE TABLE awsdatacatalog.<db>.<t> USING ICEBERG LOCATION 's3://…/' AS SELECT …` (Glue fallback; location must be empty and in-region). Re-verify `CREATE EXTERNAL TABLE … STORED AS PARQUET LOCATION … AS SELECT` (CETAS) on the day. If a CTAS fails on a column type, the error names the column: cast that `CHAR(n)` to `VARCHAR(n)` in that table's SELECT and note it in README.

- [ ] **Step 1: Write the failing test**

`runner/tests/test_sql_files.py`:

```python
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
```

- [ ] **Step 2: Run to see it fail**

Run: `cd runner && uv run pytest tests/test_sql_files.py -v`
Expected: FAIL with `FileNotFoundError` for `lake_build_s3tables.sql`

- [ ] **Step 3: Write the SQL files**

`sql/lake_build_s3tables.sql`:

```sql
-- Iceberg copies in the S3 table bucket rr-lake, namespace tpcds, written by the RA3 cluster.
-- start template b_date_dim
CREATE TABLE "rr-lake@s3tablescatalog".tpcds.date_dim USING ICEBERG AS SELECT * FROM public.date_dim;
-- end template b_date_dim
-- start template b_item
CREATE TABLE "rr-lake@s3tablescatalog".tpcds.item USING ICEBERG AS SELECT * FROM public.item;
-- end template b_item
-- start template b_store
CREATE TABLE "rr-lake@s3tablescatalog".tpcds.store USING ICEBERG AS SELECT * FROM public.store;
-- end template b_store
-- start template b_customer
CREATE TABLE "rr-lake@s3tablescatalog".tpcds.customer USING ICEBERG AS SELECT * FROM public.customer;
-- end template b_customer
-- start template b_store_sales
CREATE TABLE "rr-lake@s3tablescatalog".tpcds.store_sales USING ICEBERG AS SELECT * FROM public.store_sales;
-- end template b_store_sales
```

`sql/lake_build_glue.sql` (fallback when the S3 Tables integration blocks for more than 1 hour):

```sql
-- start template b_date_dim
CREATE TABLE awsdatacatalog.rr_iceberg.date_dim USING ICEBERG LOCATION 's3://{bucket}/iceberg/date_dim/' AS SELECT * FROM public.date_dim;
-- end template b_date_dim
-- start template b_item
CREATE TABLE awsdatacatalog.rr_iceberg.item USING ICEBERG LOCATION 's3://{bucket}/iceberg/item/' AS SELECT * FROM public.item;
-- end template b_item
-- start template b_store
CREATE TABLE awsdatacatalog.rr_iceberg.store USING ICEBERG LOCATION 's3://{bucket}/iceberg/store/' AS SELECT * FROM public.store;
-- end template b_store
-- start template b_customer
CREATE TABLE awsdatacatalog.rr_iceberg.customer USING ICEBERG LOCATION 's3://{bucket}/iceberg/customer/' AS SELECT * FROM public.customer;
-- end template b_customer
-- start template b_store_sales
CREATE TABLE awsdatacatalog.rr_iceberg.store_sales USING ICEBERG LOCATION 's3://{bucket}/iceberg/store_sales/' AS SELECT * FROM public.store_sales;
-- end template b_store_sales
```

`sql/lake_build_parquet.sql`:

```sql
-- start template schema
CREATE EXTERNAL SCHEMA IF NOT EXISTS pq FROM DATA CATALOG DATABASE 'rr_parquet' IAM_ROLE default;
-- end template schema
-- start template b_date_dim
CREATE EXTERNAL TABLE pq.date_dim STORED AS PARQUET LOCATION 's3://{bucket}/parquet/date_dim/' AS SELECT * FROM public.date_dim;
-- end template b_date_dim
-- start template b_item
CREATE EXTERNAL TABLE pq.item STORED AS PARQUET LOCATION 's3://{bucket}/parquet/item/' AS SELECT * FROM public.item;
-- end template b_item
-- start template b_store
CREATE EXTERNAL TABLE pq.store STORED AS PARQUET LOCATION 's3://{bucket}/parquet/store/' AS SELECT * FROM public.store;
-- end template b_store
-- start template b_customer
CREATE EXTERNAL TABLE pq.customer STORED AS PARQUET LOCATION 's3://{bucket}/parquet/customer/' AS SELECT * FROM public.customer;
-- end template b_customer
-- start template b_store_sales
CREATE EXTERNAL TABLE pq.store_sales STORED AS PARQUET LOCATION 's3://{bucket}/parquet/store_sales/' AS SELECT * FROM public.store_sales;
-- end template b_store_sales
```

`sql/lake_queries.sql` (`{lake}` is empty for the local baseline, so the same six run on managed storage too):

```sql
-- start template lq3
SELECT dt.d_year, it.i_brand_id AS brand_id, it.i_brand AS brand, SUM(ss.ss_ext_sales_price) AS sum_agg
FROM {lake}date_dim dt JOIN {lake}store_sales ss ON dt.d_date_sk = ss.ss_sold_date_sk
JOIN {lake}item it ON ss.ss_item_sk = it.i_item_sk
WHERE it.i_manufact_id = 128 AND dt.d_moy = 11
GROUP BY dt.d_year, it.i_brand, it.i_brand_id
ORDER BY dt.d_year, sum_agg DESC, brand_id
LIMIT 100;
-- end template lq3
-- start template lq42
SELECT dt.d_year, it.i_category_id, it.i_category, SUM(ss.ss_ext_sales_price) AS total
FROM {lake}date_dim dt JOIN {lake}store_sales ss ON dt.d_date_sk = ss.ss_sold_date_sk
JOIN {lake}item it ON ss.ss_item_sk = it.i_item_sk
WHERE it.i_manager_id = 1 AND dt.d_moy = 11 AND dt.d_year = 2000
GROUP BY 1, 2, 3 ORDER BY total DESC, 1, 2, 3
LIMIT 100;
-- end template lq42
-- start template lq52
SELECT dt.d_year, it.i_brand_id AS brand_id, it.i_brand AS brand, SUM(ss.ss_ext_sales_price) AS ext_price
FROM {lake}date_dim dt JOIN {lake}store_sales ss ON dt.d_date_sk = ss.ss_sold_date_sk
JOIN {lake}item it ON ss.ss_item_sk = it.i_item_sk
WHERE it.i_manager_id = 1 AND dt.d_moy = 11 AND dt.d_year = 2000
GROUP BY 1, 2, 3 ORDER BY 1, ext_price DESC, brand_id
LIMIT 100;
-- end template lq52
-- start template lq55
SELECT it.i_brand_id AS brand_id, it.i_brand AS brand, SUM(ss.ss_ext_sales_price) AS ext_price
FROM {lake}date_dim dt JOIN {lake}store_sales ss ON dt.d_date_sk = ss.ss_sold_date_sk
JOIN {lake}item it ON ss.ss_item_sk = it.i_item_sk
WHERE it.i_manager_id = 28 AND dt.d_moy = 11 AND dt.d_year = 1999
GROUP BY 1, 2 ORDER BY ext_price DESC, brand_id
LIMIT 100;
-- end template lq55
-- start template lqst
SELECT s.s_state, dt.d_year, SUM(ss.ss_net_paid) AS net_paid, COUNT(*) AS n
FROM {lake}store_sales ss JOIN {lake}store s ON ss.ss_store_sk = s.s_store_sk
JOIN {lake}date_dim dt ON ss.ss_sold_date_sk = dt.d_date_sk
GROUP BY 1, 2 ORDER BY 1, 2;
-- end template lqst
-- start template lqcu
SELECT c.c_customer_id, c.c_last_name, SUM(ss.ss_net_paid) AS net_paid
FROM {lake}store_sales ss JOIN {lake}customer c ON ss.ss_customer_sk = c.c_customer_sk
JOIN {lake}date_dim dt ON ss.ss_sold_date_sk = dt.d_date_sk
WHERE dt.d_year = 2001
GROUP BY 1, 2 ORDER BY net_paid DESC
LIMIT 100;
-- end template lqcu
```

`sql/elt.sql`:

```sql
-- start template ecopy
DROP TABLE IF EXISTS elt_store_returns;
CREATE TABLE elt_store_returns (LIKE store_returns);
copy elt_store_returns from 's3://redshift-downloads/TPC-DS/2.13/{scale}/store_returns/' iam_role default gzip delimiter '|' EMPTYASNULL region 'us-east-1';
-- end template ecopy
-- start template ectas
DROP TABLE IF EXISTS elt_sales_by_item_month;
CREATE TABLE elt_sales_by_item_month AS
SELECT it.i_category, it.i_brand, dt.d_year, dt.d_moy, SUM(ss.ss_net_paid) AS net_paid, COUNT(*) AS n
FROM store_sales ss JOIN date_dim dt ON ss.ss_sold_date_sk = dt.d_date_sk
JOIN item it ON ss.ss_item_sk = it.i_item_sk
GROUP BY 1, 2, 3, 4;
-- end template ectas
```

- [ ] **Step 4: Run the tests**

Run: `cd runner && uv run pytest -v`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add sql runner/tests/test_sql_files.py
git commit -m "feat(sql): lake builds (S3 Tables, Glue Iceberg fallback, Parquet), lake queries and ELT"
```

---

### Task 10: Terraform infrastructure (plan only, no apply)

**Files:**
- Create: `infra/versions.tf`, `infra/variables.tf`, `infra/main.tf`, `infra/outputs.tf`, `infra/example.tfvars`

**Interfaces:**
- Produces (outputs): `role_arn`, `lake_bucket`, `table_bucket_arn`, `ra3_id`, `rg_id`, `workgroup`
- Variables: `alert_email` (string, required), `ra3_enabled` (bool, false), `rg_snapshot_id` (string, ""), `serverless_enabled` (bool, false)

- [ ] **Step 1: Verify on the day before writing**

Check in the Terraform registry (hashicorp/aws latest) that these exist with these arguments, and pin the provider to the verified minor: `aws_redshift_cluster` (`node_type`, `number_of_nodes`, `manage_master_password`, `maintenance_track_name`, `snapshot_identifier`, `default_iam_role_arn`, `iam_roles`), `aws_redshift_parameter_group`, `aws_redshiftserverless_namespace`, `aws_redshiftserverless_workgroup` (`base_capacity`), `aws_s3tables_table_bucket`, `aws_s3tables_namespace`, `aws_glue_catalog_database`, `aws_budgets_budget` (`cost_filter`). Also confirm the sandbox has a default VPC:

```bash
AWS_PROFILE=sura-sandbox aws ec2 describe-vpcs --region us-east-1 --filters Name=isDefault,Values=true --query 'Vpcs[].VpcId'
```

Expected: one VPC id. If empty, STOP and ask the speaker (the clusters below rely on the default subnet group).

- [ ] **Step 2: Write the files**

`infra/versions.tf`:

```hcl
terraform {
  # Local state on purpose: one operator, lab lives days. State is git-ignored (carries account data).
  required_version = ">= 1.15"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.66" # 6.66.0 validated this config on 2026-09-24; bump to the minor verified in Step 1
    }
  }
}

provider "aws" {
  region = "us-east-1"
  default_tags {
    tags = { project = "redshift-redemption" }
  }
}
```

`infra/variables.tf`:

```hcl
variable "alert_email" {
  type        = string
  description = "Budget alert recipient"
}

variable "ra3_enabled" {
  type    = bool
  default = false
}

variable "rg_snapshot_id" {
  type        = string
  default     = ""
  description = "Manual snapshot of rr-ra3 to restore rr-rg from; empty = no RG cluster"
}

variable "serverless_enabled" {
  type    = bool
  default = false
}
```

`infra/main.tf`:

```hcl
data "aws_caller_identity" "me" {}

# --- lake storage ---
resource "aws_s3_bucket" "lake" {
  bucket        = "rr-lake-${data.aws_caller_identity.me.account_id}"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "lake" {
  bucket                  = aws_s3_bucket.lake.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3tables_table_bucket" "lake" {
  name = "rr-lake"
}

resource "aws_s3tables_namespace" "tpcds" {
  namespace        = "tpcds"
  table_bucket_arn = aws_s3tables_table_bucket.lake.arn
}

resource "aws_glue_catalog_database" "iceberg" {
  name = "rr_iceberg"
}

resource "aws_glue_catalog_database" "parquet" {
  name = "rr_parquet"
}

# --- IAM role Redshift assumes (COPY, UNLOAD/CETAS, Iceberg writes) ---
data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["redshift.amazonaws.com", "redshift-serverless.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "redshift" {
  name               = "rr-redshift"
  assume_role_policy = data.aws_iam_policy_document.assume.json
}

data "aws_iam_policy_document" "redshift" {
  statement {
    sid       = "PublicDataset"
    actions   = ["s3:GetObject", "s3:ListBucket"]
    resources = ["arn:aws:s3:::redshift-downloads", "arn:aws:s3:::redshift-downloads/*"]
  }
  statement {
    sid       = "LakeBucket"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket", "s3:GetBucketLocation"]
    resources = [aws_s3_bucket.lake.arn, "${aws_s3_bucket.lake.arn}/*"]
  }
  statement {
    sid       = "TableBucket"
    actions   = ["s3tables:*"]
    resources = [aws_s3tables_table_bucket.lake.arn, "${aws_s3tables_table_bucket.lake.arn}/*"]
  }
  statement {
    sid = "GlueCatalog"
    actions = ["glue:GetCatalog", "glue:GetCatalogs", "glue:GetDatabase", "glue:GetDatabases", "glue:GetTable",
    "glue:GetTables", "glue:CreateTable", "glue:UpdateTable", "glue:DeleteTable", "glue:GetPartitions"]
    resources = ["*"]
  }
  statement {
    sid       = "LakeFormation"
    actions   = ["lakeformation:GetDataAccess"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "redshift" {
  role   = aws_iam_role.redshift.id
  policy = data.aws_iam_policy_document.redshift.json
}

# --- identical settings for every provisioned cluster ---
resource "aws_redshift_parameter_group" "rr" {
  name   = "rr-params"
  family = "redshift-2.0"
  parameter {
    name  = "max_concurrency_scaling_clusters"
    value = "0"
  }
  parameter {
    name  = "enable_result_cache_for_session"
    value = "false"
  }
  parameter {
    name  = "require_ssl"
    value = "true"
  }
}

resource "aws_redshift_cluster" "ra3" {
  count                        = var.ra3_enabled ? 1 : 0
  cluster_identifier           = "rr-ra3"
  node_type                    = "ra3.xlplus"
  cluster_type                 = "multi-node"
  number_of_nodes              = 2
  database_name                = "tpcds"
  master_username              = "awsuser"
  manage_master_password       = true
  iam_roles                    = [aws_iam_role.redshift.arn]
  default_iam_role_arn         = aws_iam_role.redshift.arn
  cluster_parameter_group_name = aws_redshift_parameter_group.rr.name
  maintenance_track_name       = "current"
  publicly_accessible          = false
  encrypted                    = true
  skip_final_snapshot          = true
}

resource "aws_redshift_cluster" "rg" {
  count                        = var.rg_snapshot_id == "" ? 0 : 1
  cluster_identifier           = "rr-rg"
  snapshot_identifier          = var.rg_snapshot_id
  node_type                    = "rg.xlarge"
  cluster_type                 = "multi-node"
  number_of_nodes              = 2
  master_username              = "awsuser"
  manage_master_password       = true
  iam_roles                    = [aws_iam_role.redshift.arn]
  default_iam_role_arn         = aws_iam_role.redshift.arn
  cluster_parameter_group_name = aws_redshift_parameter_group.rr.name
  maintenance_track_name       = "current"
  publicly_accessible          = false
  encrypted                    = true
  skip_final_snapshot          = true
}

# --- Serverless context run: empty namespace; data arrives via restore-from-snapshot (runbook) ---
resource "aws_redshiftserverless_namespace" "sls" {
  count                = var.serverless_enabled ? 1 : 0
  namespace_name       = "rr-sls"
  iam_roles            = [aws_iam_role.redshift.arn]
  default_iam_role_arn = aws_iam_role.redshift.arn
}

resource "aws_redshiftserverless_workgroup" "sls" {
  count               = var.serverless_enabled ? 1 : 0
  workgroup_name      = "rr-sls"
  namespace_name      = aws_redshiftserverless_namespace.sls[0].namespace_name
  base_capacity       = 32
  publicly_accessible = false
}

# --- spend guard: Redshift only, so the ARMed lab in the same sandbox doesn't trip it ---
resource "aws_budgets_budget" "rr" {
  name         = "rr-lab"
  budget_type  = "COST"
  limit_amount = "100"
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  cost_filter {
    name   = "Service"
    values = ["Amazon Redshift"]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.alert_email]
  }
}
```

`infra/outputs.tf`:

```hcl
output "role_arn" { value = aws_iam_role.redshift.arn }
output "lake_bucket" { value = aws_s3_bucket.lake.bucket }
output "table_bucket_arn" { value = aws_s3tables_table_bucket.lake.arn }
output "ra3_id" { value = one(aws_redshift_cluster.ra3[*].cluster_identifier) }
output "rg_id" { value = one(aws_redshift_cluster.rg[*].cluster_identifier) }
output "workgroup" { value = one(aws_redshiftserverless_workgroup.sls[*].workgroup_name) }
```

`infra/example.tfvars`:

```hcl
alert_email        = "you@example.com"
ra3_enabled        = false
rg_snapshot_id     = ""
serverless_enabled = false
```

- [ ] **Step 3: Validate without touching AWS state**

```bash
cd infra
terraform fmt -check
terraform init -backend=false
terraform validate
```

Expected: `Success! The configuration is valid.`

- [ ] **Step 4: Plan with read-only credentials**

```bash
cp example.tfvars terraform.tfvars   # set alert_email; terraform.tfvars is git-ignored
AWS_PROFILE=sura-sandbox terraform init
AWS_PROFILE=sura-sandbox terraform plan -var ra3_enabled=true -out rr.tfplan
```

Expected: plan creates the role, policy, buckets, table bucket + namespace, 2 Glue databases, parameter group, `rr-ra3`, budget. No `rr-rg`, no Serverless. Do NOT apply.

- [ ] **Step 5: Commit**

```bash
git add infra/*.tf infra/example.tfvars infra/.terraform.lock.hcl
bash demo/sanitize-check.sh
git commit -m "feat(infra): IAM, lake buckets, parameter group, RA3/RG/Serverless toggles and budget"
```

---

### Task 11: Lab-day runbook

**Files:**
- Create: `runbooks/lab-day.md`

**Interfaces:**
- Consumes: `rr` commands (Task 8), terraform variables/outputs (Task 10), SQL files (Tasks 3, 9)
- Produces: the gated sequence Tasks 12–13 execute. Every `apply`, restore, resize and scenario is marked **GO** (speaker says go first).

- [ ] **Step 1: Write the runbook**

`runbooks/lab-day.md`:

````markdown
# Lab day — Redshift Redemption

Todo en us-east-1 con `export AWS_PROFILE=sura-sandbox AWS_REGION=us-east-1`.
Cada paso marcado **GO** espera el "dale" del speaker. Al cerrar cada sesión:
clústeres pausados o borrados, verificado con `aws redshift describe-clusters`.

## 0. Antes de gastar
1. Llenar `results/prices.md` con la API de precios del día.
2. **GO** `cd infra && terraform apply -var ra3_enabled=true` (crea también el budget).
3. Confirmar el correo de suscripción del budget.

## 1. Sesión dev (100 GB)
```bash
cd runner
uv run rr load --target cluster:rr-ra3 --scale 100GB          # GO
uv run rr sql --target cluster:rr-ra3 --file ../sql/analyze.sql
uv run rr power --target cluster:rr-ra3 --passes 1              # GO
uv run rr metrics --target cluster:rr-ra3 --csv <csv>
```
Anotar el tiempo total de `load` (fila por tabla) y extrapolar a 1 TB (×~9.6
por bytes comprimidos: 364 / 37.8 GB). Si la extrapolación pasa de 6 h,
parar y hablarlo antes de la sesión de 1 TB.
Cierre: `aws redshift delete-cluster --cluster-identifier rr-ra3 --skip-final-cluster-snapshot`
**o** `terraform apply -var ra3_enabled=false`.

## 2. Carga 1 TB, lago y snapshot
```bash
terraform apply -var ra3_enabled=true                            # GO
uv run rr load --target cluster:rr-ra3 --scale 1TB               # GO, 3–5 h
uv run rr sql --target cluster:rr-ra3 --file ../sql/analyze.sql
# conteos contra sql/expected_counts_1tb.csv
BUCKET=$(terraform -chdir=../infra output -raw lake_bucket)
uv run rr sql --target cluster:rr-ra3 --file ../sql/lake_build_s3tables.sql   # GO
uv run rr sql --target cluster:rr-ra3 --file ../sql/lake_build_parquet.sql --var bucket=$BUCKET  # GO
aws redshift create-cluster-snapshot --cluster-identifier rr-ra3 --snapshot-identifier rr-ra3-1tb
aws redshift wait snapshot-available --snapshot-identifier rr-ra3-1tb
```
S3 Tables: antes de `lake_build_s3tables.sql`, habilitar en la consola de S3
"Integration with AWS analytics services" para la table bucket `rr-lake` y dar
permisos de Lake Formation al rol `rr-redshift` sobre `s3tablescatalog/rr-lake/tpcds`
(ver https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-tables-integrating-aws.html).
Si en 1 hora no funciona: `lake_build_glue.sql --var bucket=$BUCKET` y variante `glue`.

## 3. RG desde el mismo snapshot
```bash
terraform apply -var ra3_enabled=true -var rg_snapshot_id=rr-ra3-1tb   # GO
```
Comprobar que ambos corren la misma versión:
`uv run rr sql --target cluster:rr-rg --file ../sql/version.sql` y lo mismo en rr-ra3.

## 4. Escenarios (en cada clúster, primero rr-ra3 y luego rr-rg)
```bash
uv run rr power --target cluster:<id>                            # GO
uv run rr concurrency --target cluster:<id>                      # GO, 30 min
uv run rr lake --target cluster:<id> --variant local
uv run rr lake --target cluster:<id> --variant s3tables
uv run rr lake --target cluster:<id> --variant parquet
uv run rr elt --target cluster:<id> --scale 1TB
uv run rr metrics --target cluster:<id> --csv <cada csv>
```
`rr metrics` que sale con código 3 invalida esa corrida: se repite, no se reporta.
Pausar el clúster que no se está midiendo: `aws redshift pause-cluster --cluster-identifier <id>`.

## 5. Simulacro de migración (elastic resize)
```bash
aws redshift restore-from-cluster-snapshot --cluster-identifier rr-drill \
  --snapshot-identifier rr-ra3-1tb --node-type ra3.xlplus --number-of-nodes 2 \
  --iam-roles "$(terraform -chdir=../infra output -raw role_arn)" \
  --cluster-parameter-group-name rr-params                        # GO
aws redshift wait cluster-available --cluster-identifier rr-drill
date -u; aws redshift resize-cluster --cluster-identifier rr-drill --node-type rg.xlarge --number-of-nodes 2   # GO
watch -n 30 aws redshift describe-resize --cluster-identifier rr-drill
uv run rr sql --target cluster:rr-drill --file ../sql/skew.sql
uv run rr sql --target cluster:rr-rg --file ../sql/skew.sql
aws redshift delete-cluster --cluster-identifier rr-drill --skip-final-cluster-snapshot
```
Anotar: inicio, fin de la ventana de solo lectura, fin total, skew por tabla en
ambos clústeres.

## 6. Serverless (contexto)
```bash
terraform apply -var ra3_enabled=true -var rg_snapshot_id=rr-ra3-1tb -var serverless_enabled=true   # GO
aws redshift-serverless restore-from-snapshot --namespace-name rr-sls --workgroup-name rr-sls \
  --snapshot-arn "$(aws redshift describe-cluster-snapshots --snapshot-identifier rr-ra3-1tb --query 'Snapshots[0].SnapshotArn' --output text)"
uv run rr power --target workgroup:rr-sls --passes 2             # GO
uv run rr metrics --target workgroup:rr-sls --csv <csv>
```

## 7. Cierre (mismo día)
```bash
cd infra && terraform destroy                                    # GO
aws redshift delete-cluster-snapshot --snapshot-identifier rr-ra3-1tb   # after results are safe
aws redshift describe-clusters --query 'Clusters[].ClusterIdentifier'   # expect []
aws redshift-serverless list-workgroups --query 'workgroups[].workgroupName'  # expect []
```
Tablas de S3 Tables: borrar las 5 tablas antes del `destroy` si falla por
bucket no vacío (`aws s3tables delete-table --table-bucket-arn … --namespace tpcds --name <t>`).
````

- [ ] **Step 2: Add the three tiny SQL files the runbook uses**

`sql/analyze.sql`:

```sql
-- start template analyze
ANALYZE;
-- end template analyze
```

`sql/version.sql`:

```sql
-- start template version
SELECT version();
-- end template version
```

`sql/skew.sql`:

```sql
-- start template skew
SELECT "table", tbl_rows, skew_rows, skew_sortkey1 FROM svv_table_info ORDER BY skew_rows DESC NULLS LAST;
-- end template skew
```

Note: `rr sql` records timings, not result rows. For `version.sql` and `skew.sql`, the values come from `rr metrics` (`redshift_version` column) and, for skew, from running the same statement in the Query Editor v2 and pasting the table into `results/<date>/drill.md`. Re-verify `svv_table_info` column names on the day.

- [ ] **Step 3: Commit**

```bash
git add runbooks sql/analyze.sql sql/version.sql sql/skew.sql
git commit -m "docs(runbook): gated lab-day sequence from dev load to teardown"
```

---

### Task 12: Dev session at 100 GB (GATED — speaker says go)

**Files:**
- Modify: `results/prices.md` (filled), `README.md` (versions), `docs/superpowers/specs/2026-09-24-redshift-redemption-design.md` §6 (re-estimate)
- Create: `results/<date>/*.csv`

- [ ] **Step 1:** Fill `results/prices.md` from the Price List API (runbook §0). Commit.
- [ ] **Step 2:** **GO** runbook §0 apply, then §1.
- [ ] **Step 3:** `rr metrics` exits 0 for the power run. If it exits 3, fix the cause (cache, scaling, version) and repeat before anything else.
- [ ] **Step 4:** Extrapolate the 1 TB load time from the per-table 100 GB rows; update spec §6 with the measured rate and the new estimate.
- [ ] **Step 5:** Tear down (runbook §1 cierre); verify no clusters listed.
- [ ] **Step 6:** Commit

```bash
bash demo/sanitize-check.sh
git add results README.md docs
git commit -m "results: 100 GB dev session, measured load rate and re-estimated cost"
```

---

### Task 13: Headline run at 1 TB (GATED — speaker says go)

**Files:**
- Create: `results/<date>/*.csv`, `results/<date>/*-timings.csv`, `results/<date>/summary.md`, `results/<date>/drill.md`, `results/<date>/cost.md`

- [ ] **Step 1:** **GO** runbook §2–§4 (load, lake, snapshot, RG, scenarios). Every `rr metrics` exits 0 or the run is repeated.
- [ ] **Step 2:** Report:

```bash
cd runner
uv run rr report --base ../results/<date>/rr-ra3-power-<run>-timings.csv \
  --cand ../results/<date>/rr-rg-power-<run>-timings.csv --out ../results/<date>/summary.md
```

- [ ] **Step 3:** **GO** runbook §5 (drill) and §6 (Serverless); write `drill.md` (read-only window, total time, skew table for both clusters).
- [ ] **Step 4:** Write `results/<date>/cost.md`: cluster hours from the console/Cost Explorer for the lab days vs the spec §6 estimate, plus the per-run USD from `summary.md` and Spectrum USD from the RA3 lake runs (`spectrum_usd` over `scanned_bytes`).
- [ ] **Step 5:** **GO** runbook §7 teardown; verify empty listings.
- [ ] **Step 6:** Commit

```bash
bash demo/sanitize-check.sh
git add results
git commit -m "results: 1 TB RA3 vs RG, lake, ELT, drill, Serverless and cost"
```

---

## Self-review notes (2026-09-24)

- Spec §3 clusters → Task 10; §4 scenarios 1–6 → Tasks 5/8 (power, concurrency), 9 (lake, ELT), 11 §5 (drill), 11 §6 (Serverless); "porqué" layer → Task 6 timings split; EXPLAIN equality and `SYS_QUERY_DETAIL` for the 3 biggest deltas are manual analysis in Query Editor v2 after Task 13 (not automated on purpose: three queries).
- Validity rules (cache, scaling, version) → Task 6 `problems()`, enforced by `rr metrics` exit 3.
- Cost → Task 7 + Task 13 Step 4; budget → Task 10.
- Slides are out of this plan (spec §5).
