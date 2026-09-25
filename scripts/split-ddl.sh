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
