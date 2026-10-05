# Lab day — Redshift Redemption

Todo desde la raíz del repo, en us-east-1:

```bash
export AWS_PROFILE=morrislabs-poc AWS_REGION=us-east-1          # aws sso login --profile morrislabs-poc
rr() { PYTHONPATH="$PWD/runner" uv run --project runner rr "$@"; }   # PYTHONPATH: ver README, problemas conocidos
tf() { terraform -chdir=infra "$@"; }                            # solo lectura (output); los apply van por GitHub Actions
infra() { gh workflow run infra.yml "$@" && sleep 5 && gh run watch "$(gh run list -w infra.yml -L1 --json databaseId -q ".[0].databaseId")" --exit-status; }
```

Cada paso marcado **GO** espera el "dale" del speaker. Al cerrar cada sesión:
clústeres pausados o borrados, verificado con `aws redshift describe-clusters`.

## 0. Antes de gastar
1. Llenar `results/prices.md` con la API de precios del día.
2. Una sola vez, **GO**: bootstrap de GitHub Actions (bucket de estado + rol OIDC `rr-gha`) desde la laptop:
   ```bash
   echo "lab_account_id = \"$(aws sts get-caller-identity --query Account --output text)\"" > infra/bootstrap/terraform.tfvars
   terraform -chdir=infra/bootstrap init && terraform -chdir=infra/bootstrap apply
   gh api -X PUT repos/andrezc98/redshift-redemption/environments/lab
   gh variable set AWS_ROLE_ARN --body "$(terraform -chdir=infra/bootstrap output -raw gha_role_arn)"
   gh variable set TF_STATE_BUCKET --body "$(terraform -chdir=infra/bootstrap output -raw state_bucket)"
   gh variable set ALERT_EMAIL --body "<correo real>"
   tf init -backend-config="bucket=$(terraform -chdir=infra/bootstrap output -raw state_bucket)"
   ```
   Si la cuenta ya tiene el proveedor OIDC de GitHub, el apply falla con
   `EntityAlreadyExists`: importarlo (comentario en `infra/bootstrap/main.tf`).
3. `infra -f action=plan` y revisar el plan (artefacto del run).
4. **GO** `infra -f action=apply` (crea `rr-ra3`, endpoints y el budget). Confirmar el correo de suscripción del budget.

## 1. Carga 100 GB, lago, permisos y snapshot (una sola sesión)
Escala única del lab: 100 GB (decisión del 2026-10-05, para recortar horas).
```bash
rr load --target cluster:rr-ra3 --scale 100GB                   # GO, ~30 min
rr counts --target cluster:rr-ra3 --scale 100GB                 # sale 4 si alguna tabla queda en 0: NO seguir
rr sql --target cluster:rr-ra3 --file sql/analyze.sql
rr query --target cluster:rr-ra3 --file sql/show_automount.sql
```
`rr load` se puede relanzar si se corta: crea tablas con `IF NOT EXISTS` y
hace `TRUNCATE` antes de cada `COPY`, así que no duplica datos.

Lago. Lake Formation gobierna el catálogo de Glue en esta cuenta: sin estos
permisos al rol `rr-redshift` los builds fallan con
`Insufficient Lake Formation permission(s): Required Create Table on rr_iceberg`.
```bash
A=$(aws sts get-caller-identity --query Account --output text)
R="arn:aws:iam::$A:role/rr-redshift"
for DB in rr_iceberg rr_parquet; do                             # GO
  aws lakeformation grant-permissions --principal DataLakePrincipalIdentifier="$R" \
    --resource "{\"Database\":{\"CatalogId\":\"$A\",\"Name\":\"$DB\"}}" \
    --permissions CREATE_TABLE DESCRIBE ALTER DROP
  aws lakeformation grant-permissions --principal DataLakePrincipalIdentifier="$R" \
    --resource "{\"Table\":{\"CatalogId\":\"$A\",\"DatabaseName\":\"$DB\",\"TableWildcard\":{}}}" \
    --permissions ALL
done
```
Los permisos tardan unos segundos en propagarse: si la primera tabla del build
falla con el mismo error, esperar y relanzar el build.
```bash
BUCKET=$(tf output -raw lake_bucket)
rr sql --target cluster:rr-ra3 --file sql/lake_build_glue.sql --var bucket=$BUCKET     # GO
rr sql --target cluster:rr-ra3 --file sql/lake_build_parquet.sql --var bucket=$BUCKET
rr lake --target cluster:rr-ra3 --variant glue --passes 1       # humo: todas las filas en FINISHED
rr lake --target cluster:rr-ra3 --variant parquet --passes 1
```
S3 Tables queda fuera del lab. Los nombres `"rr-lake@s3tablescatalog"` pasan por
el catálogo auto-montado, que exige conectarse con una identidad IAM (usuarios
`IAM:`/`IAMR:`, federated access to Spectrum); el runner usa `awsuser` en todos
los warehouses y recibe `ERROR: cross-database reference to database "rr-lake@s3tablescatalog" is not supported`.
Cambiar de usuario solo para esa variante mediría otra ruta de permisos. Iceberg
se mide con `glue` (esquema externo `ice`, rol del clúster).
Fuente: https://docs.aws.amazon.com/redshift/latest/dg/querying-s3Tables.html
("Method 3: Auto-mounted awsdatacatalog", leído el 2026-10-05).
```bash
rr sql --target cluster:rr-ra3 --file sql/grant.sql             # antes del snapshot (Serverless lo necesita)
aws redshift create-cluster-snapshot --cluster-identifier rr-ra3 --snapshot-identifier rr-ra3-100gb
aws redshift wait snapshot-available --snapshot-identifier rr-ra3-100gb
```

## 2. RG desde el mismo snapshot
```bash
infra -f action=apply -f rg_snapshot_id=rr-ra3-100gb            # GO
rr query --target cluster:rr-ra3 --file sql/version.sql
rr query --target cluster:rr-rg --file sql/version.sql
```
Si las versiones difieren, anotarlo: `rr report` lo muestra en el encabezado.

## 3. Escenarios (primero rr-ra3, luego rr-rg)
```bash
aws redshift resume-cluster --cluster-identifier <id> 2>/dev/null; aws redshift wait cluster-available --cluster-identifier <id>
rr power --target cluster:<id>                                  # GO
rr concurrency --target cluster:<id>                            # GO, 30 min
rr lake --target cluster:<id> --variant local
rr lake --target cluster:<id> --variant glue
rr lake --target cluster:<id> --variant parquet
rr elt --target cluster:<id> --scale 100GB
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

## 4. Simulacro de migración (elastic resize)
```bash
aws redshift restore-from-cluster-snapshot --cluster-identifier rr-drill \
  --snapshot-identifier rr-ra3-100gb --node-type ra3.xlplus --number-of-nodes 2 \
  --iam-roles "$(tf output -raw role_arn)" \
  --cluster-parameter-group-name rr-params \
  --cluster-subnet-group-name rr-lab \
  --vpc-security-group-ids "$(tf output -raw security_group_id)" \
  --enhanced-vpc-routing                                          # GO (igual que rr-ra3/rr-rg) (sin VPC por defecto: subnet group y SG del lab)
aws redshift wait cluster-available --cluster-identifier rr-drill
date -u; aws redshift resize-cluster --cluster-identifier rr-drill --node-type rg.xlarge --number-of-nodes 2   # GO
watch -n 30 aws redshift describe-resize --cluster-identifier rr-drill
rr query --target cluster:rr-drill --file sql/skew.sql > results/<fecha>/skew-drill.csv
rr query --target cluster:rr-rg --file sql/skew.sql > results/<fecha>/skew-rg.csv
aws redshift delete-cluster --cluster-identifier rr-drill --skip-final-cluster-snapshot
```
Anotar en `results/<fecha>/drill.md`: inicio, fin de la ventana de solo lectura,
fin total, y el skew por tabla de los dos CSV.

## 5. Serverless (contexto)
```bash
infra -f action=apply -f rg_snapshot_id=rr-ra3-100gb -f serverless_enabled=true   # GO
aws redshift-serverless restore-from-snapshot --namespace-name rr-sls --workgroup-name rr-sls \
  --snapshot-arn "$(aws redshift describe-cluster-snapshots --snapshot-identifier rr-ra3-100gb --query 'Snapshots[0].SnapshotArn' --output text)"
until [ "$(aws redshift-serverless get-namespace --namespace-name rr-sls --query namespace.status --output text)" = AVAILABLE ]; do sleep 30; done
rr power --target workgroup:rr-sls --passes 2                   # GO
rr metrics --target workgroup:rr-sls --csv <csv>
```

## 6. Cierre (mismo día)
```bash
rr sql --target cluster:rr-ra3 --file sql/lake_drop.sql
aws s3 rm "s3://$BUCKET/" --recursive
infra -f action=destroy -f rg_snapshot_id=rr-ra3-100gb -f serverless_enabled=true   # GO (se niega si rr-lake aún tiene tablas)
aws redshift delete-cluster-snapshot --snapshot-identifier rr-ra3-100gb   # cuando los resultados estén a salvo
aws redshift describe-clusters --query 'Clusters[].ClusterIdentifier'   # esperado []
aws redshift-serverless list-workgroups --query 'workgroups[].workgroupName'  # esperado []
```
Solo si se usó S3 Tables: si el destroy falla porque la table bucket no está vacía, borrar las tablas
que queden: `aws s3tables delete-table --table-bucket-arn "$(tf output -raw table_bucket_arn)" --namespace tpcds --name <t>`.
