#!/usr/bin/env bash
# Migration drill (runbook §4): restore rr-ra3-100gb as rr-drill (2x ra3.xlplus),
# elastic-resize it to 2x rg.xlarge and measure the read-only window with a write
# probe every 30 s, then capture slice skew on rr-drill and rr-rg and delete rr-drill.
# Writes results/<day>/drill-log.csv, skew-drill.csv, skew-rg.csv.
#
# DescribeResize Status values (NONE|IN_PROGRESS|FAILED|SUCCEEDED|CANCELLING) and
# ResizeType/DataTransferProgressPercent: API_DescribeResize.html, read 2026-10-05.
# Restore (ra3.xlplus x2) and resize (rg.xlarge x2) options checked with
# describe-node-configuration-options the same day.
set -uo pipefail
case "${AWS_PROFILE:-}" in *sandbox*|morrislabs-poc) ;; *) echo "AWS_PROFILE must be a lab profile" >&2; exit 1 ;; esac
export AWS_REGION=us-east-1
cd "$(dirname "$0")/.."
day="$(date -u +%F)"; out="results/$day"; mkdir -p "$out"
log="$out/drill-log.csv"
rr() { PYTHONPATH="$PWD/runner" uv run --project runner rr "$@"; }
ts() { date -u +%FT%TZ; }

# One statement through the Data API as awsuser; prints FINISHED or FAILED.
sql() {
  local sid st
  sid="$(aws redshift-data execute-statement --cluster-identifier "$1" --database tpcds \
    --db-user awsuser --sql "$2" --query Id --output text 2>/dev/null)" || { echo FAILED; return; }
  while :; do
    st="$(aws redshift-data describe-statement --id "$sid" --query Status --output text)"
    case "$st" in FINISHED|FAILED|ABORTED) echo "$st"; return ;; esac
    sleep 2
  done
}

# Rerun-safe: reuse rr-drill if a previous run already restored it.
if ! aws redshift describe-clusters --cluster-identifier rr-drill >/dev/null 2>&1; then
  echo "$(ts): restoring rr-drill"
  aws redshift restore-from-cluster-snapshot --cluster-identifier rr-drill \
    --snapshot-identifier rr-ra3-100gb --node-type ra3.xlplus --number-of-nodes 2 \
    --iam-roles "$(terraform -chdir=infra output -raw role_arn)" \
    --cluster-parameter-group-name rr-params --cluster-subnet-group-name rr-lab \
    --vpc-security-group-ids "$(terraform -chdir=infra output -raw security_group_id)" \
    --maintenance-track-name current --enhanced-vpc-routing \
    --manage-master-password \
    --query 'Cluster.ClusterStatus' --output text || exit 1
  aws redshift wait cluster-available --cluster-identifier rr-drill || exit 1
fi
aws redshift wait cluster-available --cluster-identifier rr-drill || exit 1
echo "$(ts): rr-drill available; probe table: $(sql rr-drill 'CREATE TABLE IF NOT EXISTS drill_probe (t timestamp)')"

# A cluster restored from a snapshot can't elastic-resize until it has a backup of its own
# (InvalidClusterState, 2026-10-05; also the resizing-cluster.html constraint), and a
# fresh manual snapshot is what the docs recommend before any resize anyway.
echo "$(ts): pre-resize snapshot"
aws redshift create-cluster-snapshot --cluster-identifier rr-drill --snapshot-identifier rr-drill-pre-resize \
  --query 'Snapshot.Status' --output text 2>/dev/null || echo "(already exists)"
aws redshift wait snapshot-available --snapshot-identifier rr-drill-pre-resize || exit 1
echo "$(ts): pre-resize snapshot available"
# ClusterStatus says "available" while ClusterAvailabilityStatus is still "Modifying" after
# restore + snapshot; resize-cluster then fails with "being modified by a concurrent operation".
until [ "$(aws redshift describe-clusters --cluster-identifier rr-drill \
  --query 'Clusters[0].ClusterAvailabilityStatus' --output text)" = Available ]; do sleep 15; done
echo "$(ts): rr-drill fully available"

echo "ts,resize_status,resize_type,transfer_pct,write_probe" > "$log"
echo "$(ts): elastic resize to 2x rg.xlarge"
aws redshift resize-cluster --cluster-identifier rr-drill --node-type rg.xlarge --number-of-nodes 2 \
  --query 'Cluster.ClusterStatus' --output text || exit 1
while :; do
  r="$(aws redshift describe-resize --cluster-identifier rr-drill \
    --query '[Status,ResizeType,DataTransferProgressPercent]' --output text 2>/dev/null | tr '\t' ',')"
  w="$(sql rr-drill 'INSERT INTO drill_probe VALUES (getdate())')"
  echo "$(ts),$r,$w" | tee -a "$log"
  case "$r" in SUCCEEDED*|FAILED*) break ;; esac
  sleep 30
done
aws redshift wait cluster-available --cluster-identifier rr-drill
echo "$(ts): resize done; node type now $(aws redshift describe-clusters --cluster-identifier rr-drill --query 'Clusters[0].NodeType' --output text)"

rr query --target cluster:rr-drill --file sql/skew.sql > "$out/skew-drill.csv"
# rr-rg may already be paused by the scenario run: resume only for the skew query.
st="$(aws redshift describe-clusters --cluster-identifier rr-rg --query 'Clusters[0].ClusterStatus' --output text)"
[ "$st" = paused ] && { aws redshift resume-cluster --cluster-identifier rr-rg >/dev/null; aws redshift wait cluster-available --cluster-identifier rr-rg; }
rr query --target cluster:rr-rg --file sql/skew.sql > "$out/skew-rg.csv"
[ "$st" = paused ] && aws redshift pause-cluster --cluster-identifier rr-rg --query 'Cluster.ClusterStatus' --output text

aws redshift delete-cluster --cluster-identifier rr-drill --skip-final-cluster-snapshot --query 'Cluster.ClusterStatus' --output text
aws redshift delete-cluster-snapshot --snapshot-identifier rr-drill-pre-resize --query 'Snapshot.Status' --output text
echo "$(ts): DONE (log $log)"
