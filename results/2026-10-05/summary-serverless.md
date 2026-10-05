# RA3 frente a RG frente a Serverless (4 RPU), 100 GB

Serverless restaurado del mismo snapshot `rr-ra3-100gb` (misma versión de Redshift,
1.0.434008), con capacidad fija: base = máximo = 4 RPU y el objetivo automático de
precio-rendimiento apagado. 4 RPU = 64 GB de memoria (1 RPU = 16 GB), la misma memoria
que 2 × rg.xlarge, a USD 1,50/h frente a 1,52/h. `SYS_SERVERLESS_USAGE` confirma 4 RPU
en cada minuto de cada prueba. Corridas del 2026-10-05, 21:58–22:59 UTC.

Método idéntico al de los clústeres (`runner/rr/stats.py`: mediana de `elapsed_s` por
consulta, sin la repetición de calentamiento; ninguna fila excluida por caché).
Parquet: archivos de ≈0,5 GB (el formato vigente en S3 al momento de la prueba), así
que se compara con las corridas `df42` (RA3) y `f7c8` (RG).

| Prueba | RA3 | RG | Serverless 4 RPU | RG frente a Serverless |
|---|---|---|---|---|
| Potencia: total de 20 consultas | 148,3 s | 96,7 s | 243,9 s | 3,09x |
| Potencia: mediana por consulta | 1,65 s | 0,58 s | 3,28 s | — |
| Concurrencia: consultas por hora | 680 | 1224 | 720 | 1,7x |
| Lago: tablas locales | 7,6 s | 4,5 s | 11,5 s | 2,19x |
| Lago: Iceberg | 29,4 s | 14,6 s | 34,7 s | 2,08x |
| Lago: Parquet (archivos de 0,5 GB) | 46,5 s | 36,3 s | 33,3 s | 1,03x |
| ELT: COPY + CTAS | 47,9 s | 31,6 s | 62,1 s | 2,30x |

Las aceleraciones son medias geométricas por consulta. En potencia, Serverless frente a
RA3: 0,54x en lectura y 0,70x en cálculo.

**Costo.** Por ejecución de las 20 consultas, con la tarifa por segundo de cómputo:
RA3 USD 0,089 · RG USD 0,041 · Serverless USD 0,102. Factura real de Serverless
(`SYS_SERVERLESS_USAGE.charged_seconds`, incluye el mínimo de 60 s por consulta):
3.840 RPU-s en potencia = USD 0,40 por las 3 repeticiones (USD 0,133 por ejecución);
todas las pruebas de Serverless del día: 14.164 RPU-s = **USD 1,48**.

## Cómo leerlo

- Con la misma memoria y casi el mismo precio por hora, RG fue unas 3 veces más rápido
  que Serverless de 4 RPU en las consultas del warehouse, y unas 2 veces en el resto.
- Serverless de 4 RPU quedó por debajo de RA3 en casi todo, salvo concurrencia (similar)
  y Parquet con archivos chicos (mejor que RA3, igual a RG).
- Esta prueba fija la capacidad a propósito para comparar en igualdad de condiciones. La
  ventaja de Serverless es otra: escalar solo cuando hace falta y no cobrar cuando no hay
  consultas. 4 RPU es el tamaño de entrada; el valor por defecto de AWS es 128 RPU.

## Pasos que hizo falta resolver (para el runbook)

1. Un `terraform apply` con los clústeres pausados planeaba modificarlos: un clúster
   pausado reporta `cluster_type = single-node`. Se ignora ese campo en Terraform.
2. La Data API sobre un workgroup se conecta como identidad IAM (`IAMR:...`), que no
   tenía permiso sobre los esquemas del lago: hubo que dar `USAGE` sobre `ice` y `pq`
   como administrador.
3. El namespace restaurado no expuso un secreto de administrador; se activó con
   `update-namespace --manage-admin-password`, y la nueva contraseña tardó unos 2 minutos
   en funcionar.
4. La sesión de SSO expiró a mitad de las pruebas: lago y ELT se repitieron después de
   volver a iniciar sesión (los archivos fallidos se borraron, no midieron nada).
