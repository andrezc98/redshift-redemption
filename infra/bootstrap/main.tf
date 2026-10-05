# Applied once, by hand, from the laptop with AWS_PROFILE=morrislabs-poc. Creates
# what GitHub Actions needs before it can run infra/: the state bucket and the
# OIDC role. Adapted from ../armed-and-dangerous/infra/bootstrap/ (same comments
# and doc quotes apply), with one change: the role is NOT AdministratorAccess,
# because the POC account is shared.
terraform {
  required_version = ">= 1.15"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.66"
    }
  }
  # No backend: this root creates the bucket. Its state stays local and git-ignored.
}

provider "aws" {
  region = "us-east-1"
  default_tags {
    tags = { project = "redshift-redemption" }
  }
}

variable "lab_account_id" {
  description = "12-digit POC account id. Git-ignored terraform.tfvars only; the precondition refuses any other account."
  type        = string
  validation {
    condition     = can(regex("^[0-9]{12}$", var.lab_account_id))
    error_message = "lab_account_id must be 12 digits."
  }
}

variable "github_sub" {
  # Repo created 2026-09-25, after GitHub's 2026-07-15 cutoff, so the token carries
  # the immutable form repo:OWNER@OWNER-ID/REPO@REPO-ID:... (verified
  # https://docs.github.com/en/actions/reference/security/oidc and
  # `gh api repos/andrezc98/redshift-redemption` on 2026-10-05).
  type    = string
  default = "repo:andrezc98@169932969/redshift-redemption@1386597894:environment:lab"
}

data "aws_caller_identity" "me" {}

resource "terraform_data" "account_gate" {
  input = var.lab_account_id
  lifecycle {
    precondition {
      condition     = data.aws_caller_identity.me.account_id == var.lab_account_id
      error_message = "Wrong account. Export AWS_PROFILE=morrislabs-poc; do not widen this gate."
    }
  }
}

# --- state bucket (versioned, SSE-S3, private, old versions expire) ---
resource "aws_s3_bucket" "tfstate" {
  bucket_prefix = "rr-tfstate-"
}

resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "tfstate" {
  bucket                  = aws_s3_bucket.tfstate.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "tfstate" {
  depends_on = [aws_s3_bucket_versioning.tfstate]
  bucket     = aws_s3_bucket.tfstate.id
  rule {
    id     = "expire-noncurrent-state-versions"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

# --- GitHub OIDC provider + role ---
# If the account already has the GitHub provider (IAM allows one per URL), import
# it instead of creating: terraform import aws_iam_openid_connect_provider.github <arn>
resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = [var.github_sub]
    }
  }
}

resource "aws_iam_role" "gha" {
  name                 = "rr-gha"
  description          = "GitHub Actions (redshift-redemption, environment lab) runs infra/ through OIDC"
  assume_role_policy   = data.aws_iam_policy_document.assume.json
  max_session_duration = 3600
}

# PowerUserAccess covers Redshift, EC2/VPC, S3, S3 Tables, Glue, Lake Formation
# and Budgets, but no IAM. infra/ creates exactly one IAM role (rr-redshift), so
# IAM is granted on rr-* roles only.
resource "aws_iam_role_policy_attachment" "power" {
  role       = aws_iam_role.gha.name
  policy_arn = "arn:aws:iam::aws:policy/PowerUserAccess"
}

data "aws_iam_policy_document" "iam_rr" {
  statement {
    sid = "LabRolesOnly"
    actions = ["iam:CreateRole", "iam:DeleteRole", "iam:GetRole", "iam:TagRole", "iam:UntagRole",
      "iam:UpdateAssumeRolePolicy", "iam:PutRolePolicy", "iam:GetRolePolicy", "iam:DeleteRolePolicy",
    "iam:ListRolePolicies", "iam:ListAttachedRolePolicies", "iam:ListInstanceProfilesForRole", "iam:PassRole"]
    resources = ["arn:aws:iam::${var.lab_account_id}:role/rr-redshift"]
  }
  statement {
    sid       = "RedshiftServiceLinkedRole"
    actions   = ["iam:CreateServiceLinkedRole"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "iam:AWSServiceName"
      values   = ["redshift.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "iam_rr" {
  role   = aws_iam_role.gha.id
  policy = data.aws_iam_policy_document.iam_rr.json
}

# Both go into GitHub repository variables (runbook §0). Not committed: the bucket
# name is random and the ARN carries the account id.
output "state_bucket" {
  value = aws_s3_bucket.tfstate.id
}

output "gha_role_arn" {
  value = aws_iam_role.gha.arn
}
