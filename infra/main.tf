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
  cluster_subnet_group_name    = aws_redshift_subnet_group.lab.name
  vpc_security_group_ids       = [aws_security_group.redshift.id]
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
  cluster_subnet_group_name    = aws_redshift_subnet_group.lab.name
  vpc_security_group_ids       = [aws_security_group.redshift.id]
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
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.redshift.id]
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
