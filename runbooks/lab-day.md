# Lab day — Redshift Redemption

Todo desde la raíz del repo, en us-east-1:

```bash
export AWS_PROFILE=sura-sandbox AWS_REGION=us-east-1
rr() { uv run --project runner rr "$@"; }
tf() { terraform -chdir=infra "$@"; }
```

Cada paso marcado **GO** espera el "dale" del speaker. Al cerrar cada sesión:
clústeres pausados o borrados, verificado con `aws redshift describe-clusters`.
Si `rr` falla con `No module named 'rr'`, ver "Problemas conocidos" en el README.

## 0. Antes de gastar
1. Llenar `results/prices.md` con la API de precios del día.
2. `cp infra/example.tfvars infra/terraform.tfvars` y poner el correo real en `alert_email`.
3. **GO** `tf apply -var ra3_enabled=true` (crea también el budget). Confirmar el correo de suscripción del budget.

## 1. Sesión dev (100 GB): todo lo que puede fallar, en el clúster barato
```bash
rr load --target cluster:rr-ra3 --scale 100GB                   # GO
rr counts --target cluster:rr-ra3 --scale 100GB                 # 24 tablas, ninguna en 0
rr sql --target cluster:rr-ra3 --file sql/analyze.sql
rr power --target cluster:rr-ra3 --passes 2                     # GO
rr metrics --target cluster:rr-ra3 --csv <csv que imprimió power>
rr query --target cluster:rr-ra3 --file sql/show_automount.sql
```
Anotar el tiempo total de `load` (una fila por tabla) y extrapolar a 1 TB
(×~9.6 por bytes comprimidos: 364 / 37.8 GB). Si pasa de 6 h, parar y hablarlo.

Lago, ahora y no en el clúster de 1 TB. S3 Tables primero: en la consola de S3,
habilitar "Integration with AWS analytics services" para la table bucket
`rr-lake` y dar permisos de Lake Formation al rol `rr-redshift` sobre
`s3tablescatalog/rr-lake/tpcds`
(https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-tables-integrating-aws.html).
```bash
BUCKET=$(tf output -raw lake_bucket)
rr sql --target cluster:rr-ra3 --file sql/lake_build_s3tables.sql              # GO
rr sql --target cluster:rr-ra3 --file sql/lake_build_parquet.sql --var bucket=$BUCKET
rr lake --target cluster:rr-ra3 --variant s3tables --passes 1
rr lake --target cluster:rr-ra3 --variant parquet --passes 1
```
Cada CSV debe tener todas sus filas en `FINISHED`. Si S3 Tables no funciona en
1 hora, probar el respaldo ahora:
`rr sql --target cluster:rr-ra3 --file sql/lake_build_glue.sql --var bucket=$BUCKET`
y `rr lake ... --variant glue`. Anotar cuál variante queda para la sesión de 1 TB.

Cierre dev (dejar el lago limpio para la carga de 1 TB):
```bash
rr sql --target cluster:rr-ra3 --file sql/lake_drop.sql       # tablas que no existen fallan, es normal
aws s3 rm "s3://$BUCKET/" --recursive
tf apply -var ra3_enabled=false                                 # GO (borra rr-ra3)
```

## 2. Carga 1 TB, lago, permisos y snapshot
```bash
tf apply -var ra3_enabled=true                                  # GO
rr load --target cluster:rr-ra3 --scale 1TB                     # GO, 3–5 h
rr counts --target cluster:rr-ra3 --scale 1TB                   # sale 4 si algún conteo no coincide: NO seguir
rr sql --target cluster:rr-ra3 --file sql/analyze.sql
rr sql --target cluster:rr-ra3 --file sql/lake_build_s3tables.sql              # o la variante que funcionó en dev
rr sql --target cluster:rr-ra3 --file sql/lake_build_parquet.sql --var bucket=$BUCKET
rr sql --target cluster:rr-ra3 --file sql/grant.sql             # antes del snapshot (Serverless lo necesita)
aws redshift create-cluster-snapshot --cluster-identifier rr-ra3 --snapshot-identifier rr-ra3-1tb
aws redshift wait snapshot-available --snapshot-identifier rr-ra3-1tb
```
`rr load` se puede relanzar si se corta: crea tablas con `IF NOT EXISTS` y
hace `TRUNCATE` antes de cada `COPY`, así que no duplica datos.

## 3. RG desde el mismo snapshot
```bash
tf apply -var ra3_enabled=true -var rg_snapshot_id=rr-ra3-1tb   # GO
rr query --target cluster:rr-ra3 --file sql/version.sql
rr query --target cluster:rr-rg --file sql/version.sql
```
Si las versiones difieren, anotarlo: `rr report` lo muestra en el encabezado.

## 4. Escenarios (primero rr-ra3, luego rr-rg)
```bash
aws redshift resume-cluster --cluster-identifier <id> 2>/dev/null; aws redshift wait cluster-available --cluster-identifier <id>
rr power --target cluster:<id>                                  # GO
rr concurrency --target cluster:<id>                            # GO, 30 min
rr lake --target cluster:<id> --variant local
rr lake --target cluster:<id> --variant s3tables                # o glue
rr lake --target cluster:<id> --variant parquet
rr elt --target cluster:<id> --scale 1TB
rr metrics --target cluster:<id> --csv <cada csv>
aws redshift pause-cluster --cluster-identifier <id>            # al terminar ese clúster
```
`rr metrics` que sale con código 3 invalida esa corrida: se repite, no se reporta.

Reporte (sin AWS):
```bash
rr report --base results/<fecha>/rr-ra3-power-<run>-timings.csv \
  --cand results/<fecha>/rr-rg-power-<run>-timings.csv --out results/<fecha>/summary.md
```
Sale con código 3 si alguna fila tiene caché o escalado de concurrencia. Revisar
la sección "Excluidas de la comparación" antes de llevar un número a un slide.

## 5. Simulacro de migración (elastic resize)
```bash
aws redshift restore-from-cluster-snapshot --cluster-identifier rr-drill \
  --snapshot-identifier rr-ra3-1tb --node-type ra3.xlplus --number-of-nodes 2 \
  --iam-roles "$(tf output -raw role_arn)" \
  --cluster-parameter-group-name rr-params \
  --cluster-subnet-group-name rr-lab \
  --vpc-security-group-ids "$(tf output -raw security_group_id)"  # GO (sin VPC por defecto: subnet group y SG del lab)
aws redshift wait cluster-available --cluster-identifier rr-drill
date -u; aws redshift resize-cluster --cluster-identifier rr-drill --node-type rg.xlarge --number-of-nodes 2   # GO
watch -n 30 aws redshift describe-resize --cluster-identifier rr-drill
rr query --target cluster:rr-drill --file sql/skew.sql > results/<fecha>/skew-drill.csv
rr query --target cluster:rr-rg --file sql/skew.sql > results/<fecha>/skew-rg.csv
aws redshift delete-cluster --cluster-identifier rr-drill --skip-final-cluster-snapshot
```
Anotar en `results/<fecha>/drill.md`: inicio, fin de la ventana de solo lectura,
fin total, y el skew por tabla de los dos CSV.

## 6. Serverless (contexto)
```bash
tf apply -var ra3_enabled=true -var rg_snapshot_id=rr-ra3-1tb -var serverless_enabled=true   # GO
aws redshift-serverless restore-from-snapshot --namespace-name rr-sls --workgroup-name rr-sls \
  --snapshot-arn "$(aws redshift describe-cluster-snapshots --snapshot-identifier rr-ra3-1tb --query 'Snapshots[0].SnapshotArn' --output text)"
until [ "$(aws redshift-serverless get-namespace --namespace-name rr-sls --query namespace.status --output text)" = AVAILABLE ]; do sleep 30; done
rr power --target workgroup:rr-sls --passes 2                   # GO
rr metrics --target workgroup:rr-sls --csv <csv>
```

## 7. Cierre (mismo día)
```bash
rr sql --target cluster:rr-ra3 --file sql/lake_drop.sql
aws s3 rm "s3://$BUCKET/" --recursive
tf destroy                                                      # GO
aws redshift delete-cluster-snapshot --snapshot-identifier rr-ra3-1tb   # cuando los resultados estén a salvo
aws redshift describe-clusters --query 'Clusters[].ClusterIdentifier'   # esperado []
aws redshift-serverless list-workgroups --query 'workgroups[].workgroupName'  # esperado []
```
Si `tf destroy` falla porque la table bucket no está vacía, borrar las tablas
que queden: `aws s3tables delete-table --table-bucket-arn "$(tf output -raw table_bucket_arn)" --namespace tpcds --name <t>`.
