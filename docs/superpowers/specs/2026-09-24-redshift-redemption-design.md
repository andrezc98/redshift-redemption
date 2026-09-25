# Redshift Redemption — lab design

Date: 2026-09-24. Talk: "Redshift Redemption: los nuevos nodos RG, ¿migrar o no
migrar?" (AWS Women Colombia User Group 2026, level 200). Submitted abstract and
the original lab sketch: `../kcd/kcd-argentina-2026-brainstorm-recap.md` §12.
This spec supersedes that sketch where they differ.

## 1. Question the lab answers

For a team running a small RA3 cluster today: does moving to RG deliver AWS's
promises (up to 2.2x warehouse, up to 2.4x data lake, 30% lower price per vCPU,
no Spectrum scan fee) on the cluster size most teams actually run, and what does
the migration itself cost in time and risk?

Framing: verify, don't attack. AWS measured TPC-DS/TPC-H at 10 TB on
rg.4xlarge; this lab measures 1 TB on 2-node xlplus/xlarge. Deltas are
attributed to "engine + silicon", never silicon alone (RG ships a new
vectorized data-lake engine together with Graviton).

## 2. Facts this design rests on (verified 2026-09-24)

| Fact | Value | Source |
|---|---|---|
| RG sizes | rg.large (2 vCPU/16 GiB), rg.xlarge (4/32), rg.4xlarge (16/128), rg.12xlarge (48/384) | RA3→RG best-practices blog, 2026-06-16 |
| large/12xlarge | current track (P202) only | What's New 2026-07 |
| On-demand us-east-1 | ra3.xlplus 1.086, rg.xlarge 0.7602, ra3.4xlarge 3.26, rg.4xlarge 3.04267, rg.large 0.3801, rg.12xlarge 9.128 USD/h | AWS Price List API, publication 2026-09-11 |
| Managed storage | 0.024 USD/GB-month (RA3 and RG) | same |
| Spectrum | 5 USD/TB scanned on RA3; not required/charged on RG | Redshift pricing page |
| Serverless | 0.375 USD/RPU-hour | Redshift pricing page |
| Mapping | ra3.xlplus (2–32 nodes) → rg.xlarge 1:1; ra3.4xlarge (3–64) → 3 RG per 4 RA3 | RA3→RG best-practices blog |
| Migration paths | elastic resize (~10–15 min, read-only, slices kept → possible skew); classic resize (snapshot ≤10 h, <2 PB, rebalances); snapshot/restore (new endpoint; zero-ETL, DMS, datashares must be redone) | same |
| Iceberg writes | GA 2025-11; `CREATE TABLE "<bucket>@s3tablescatalog".<ns>.<t> ... USING ICEBERG AS SELECT` | Redshift docs, iceberg-writes-sql-syntax |
| Dataset | `s3://redshift-downloads/TPC-DS/2.13/` public, us-east-1: 100GB = 37.8 GB compressed (636 objects), 1TB = 364 GB compressed (6,175 objects) | `aws s3 ls --no-sign-request`, 2026-09-24 |
| Queries | awslabs `CloudDataWarehouseBenchmark/Cloud-DWB-Derived-from-TPCDS`: 99 queries (103 statements), DDL for 1TB/3TB only, no runner | GitHub |
| Prior customer numbers | tombola: 1.16x (light) to 1.57x (heavy) cold; 33% more throughput at 1–20 streams; S3 Tables 57% faster; 4:3 mapping at 4xlarge, ~25% cost cut | AWS Big Data blog, 2026-06-22 |

## 3. Clusters

The mapping is 1:1 at xlplus, so like-for-like and AWS-mapped collapse into one
pair. That is the core lab:

| Name | Config | USD/h |
|---|---|---|
| `rr-ra3` | 2× ra3.xlplus | 2.172 |
| `rr-rg` | 2× rg.xlarge (restored from the `rr-ra3` snapshot) | 1.5204 |
| `rr-sls` | Serverless workgroup, base 32 RPU (restored from the same snapshot) | 12.00 while running |
| optional `rr-ra3-4x` / `rr-rg-4x` | 4× ra3.4xlarge / 3× rg.4xlarge | 13.04 / 9.128 |

Identical settings on both provisioned clusters: maintenance track `current`,
one parameter group (`max_concurrency_scaling_clusters=0`,
`enable_result_cache_for_session=false`, auto WLM, `require_ssl=true`), same
database `tpcds`, same Redshift version (recorded from
`SYS_QUERY_HISTORY.redshift_version`; a run on mismatched versions is flagged).

## 4. Scenarios

1. **Power**: 20 curated queries (list in `sql/curated.txt`, chosen to split
   bandwidth-bound scans/aggregations vs CPU-bound joins/window functions),
   serial, 1 warm-up + 2 measured passes; report median per query, p50/p95 of
   the set, total.
2. **Concurrency**: 5 streams, each the 20 curated queries in its own seeded
   shuffle, 30 minutes; queries/hour, queue_time p50/p95.
3. **Data lake**: `store_sales`, `date_dim`, `item`, `store`, `customer` as
   Iceberg in an S3 table bucket (written by `rr-ra3` with CTAS) and as Parquet
   (UNLOAD) behind a Glue external schema; 6 lake queries serial ×3 on both
   clusters. RA3 Spectrum bytes scanned → USD.
4. **ELT**: COPY `store_returns` (1 TB set) into a fresh table + one heavy CTAS
   (`store_sales` ⨝ `date_dim` ⨝ `item` aggregated), 2 runs each.
5. **Migration drill**: restore a second `rr-ra3` copy, elastic resize it to
   2× rg.xlarge, time the read-only window, then measure slice skew
   (`SVV_TABLE_INFO.skew_rows`) against the restored `rr-rg`.
6. **Serverless context**: scenario 1 once on `rr-sls`.

The "porqué" layer: `SYS_QUERY_HISTORY` (queue/compile/planning/execution
split), `SYS_QUERY_DETAIL` per step for the 3 biggest deltas, EXPLAIN equality
check (plans must match; if not, the delta is the plan, not the chip). No eBPF
on managed nodes, said on stage.

Every run: result cache off per statement batch, `result_cache_hit` must be
false for every measured query, `compute_type` must be `primary`; violations
mark the run invalid instead of silently counting.

## 5. Components

- `infra/` — one Terraform root, local state: IAM role (read public dataset,
  read/write own lake bucket, S3 Tables, Glue), lake bucket, S3 table bucket +
  namespace, parameter group, `rr-ra3`, `rr-rg` (from snapshot, toggle),
  Serverless namespace/workgroup (toggle), AWS Budget USD 80.
- `sql/` — DDL + COPY per scale, curated query list, lake build, lake queries,
  ELT statements.
- `runner/` — Python 3.13 + boto3 Data API: split queries, run scenarios, pull
  metrics from system views, write CSV, compute stats and cost.
- `runbooks/lab-day.md` — the gated sequence of CLI steps.
- `results/<date>/` — CSVs + `prices.md`.
- `slides/` — later plan.

## 6. Cost estimate (on-demand, us-east-1)

| Item | Assumption | USD |
|---|---|---|
| Dev at 100 GB | ~6 h both clusters | 15–20 |
| `rr-ra3` at 1 TB | ~14 h (load 3–5 h, scenarios 1–4, idle) | 30 |
| `rr-rg` at 1 TB | ~9 h | 14 |
| Migration drill | ~2 h RA3 + 1 h RG | 6 |
| Serverless | 32 RPU × 1–1.5 h | 12–18 |
| Spectrum | 1–3 TB scanned | 5–15 |
| Storage (RMS, snapshot, S3 Tables, Parquet) | ~2 weeks, ~400 GB copies | 10–15 |
| **Core** | | **≈ 90–120** |
| Optional 4xlarge | ~3 h each | +65–80 |

Controls: pause between sessions, same-day teardown, Budget alert USD 80. The
100 GB load rate re-estimates the 1 TB load before committing to it.

## 7. Out of scope

Snowflake/Databricks/BigQuery numbers; the 4.2x competitive claim; 3 TB+;
concurrency scaling; reserved pricing (one slide of arithmetic at most).
