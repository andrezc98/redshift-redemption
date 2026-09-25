output "role_arn" { value = aws_iam_role.redshift.arn }
output "lake_bucket" { value = aws_s3_bucket.lake.bucket }
output "table_bucket_arn" { value = aws_s3tables_table_bucket.lake.arn }
output "ra3_id" { value = one(aws_redshift_cluster.ra3[*].cluster_identifier) }
output "rg_id" { value = one(aws_redshift_cluster.rg[*].cluster_identifier) }
output "workgroup" { value = one(aws_redshiftserverless_workgroup.sls[*].workgroup_name) }
output "security_group_id" { value = aws_security_group.redshift.id }
