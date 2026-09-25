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
