# Lab day — Redshift Redemption

Todo en us-east-1 con `export AWS_PROFILE=sura-sandbox AWS_REGION=us-east-1`.
Cada paso marcado **GO** espera el "dale" del speaker. Al cerrar cada sesión:
clústeres pausados o borrados, verificado con `aws redshift describe-clusters`.

## 0. Antes de gastar
1. Llenar `results/prices.md` con la API de precios del día.
   `cp infra/example.tfvars infra/terraform.tfvars` y poner el correo real en `alert_email`.
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
  --cluster-parameter-group-name rr-params \
  --cluster-subnet-group-name rr-lab \
  --vpc-security-group-ids "$(terraform -chdir=../infra output -raw security_group_id)"   # GO (sin VPC por defecto: subnet group y SG del lab)
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
