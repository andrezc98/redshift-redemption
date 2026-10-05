# RA3 (2x ra3.xlplus) frente a RG (2x rg.xlarge): lago, ELT y concurrencia, 100 GB

Mismo snapshot, misma versión (Redshift 1.0.434008), corridas en paralelo el
2026-10-05. Método idéntico a `rr report` (`runner/rr/stats.py`: mediana por
consulta de `elapsed_s` del servidor, sin la pasada de calentamiento; ninguna
fila excluida por caché ni por escalado de concurrencia). `rr report` solo
admite las 20 consultas curadas del escenario de potencia (`summary-power.md`),
por eso estas cifras se calcularon con las mismas funciones fuera del reporte.

| Escenario | RA3 total (s) | RG total (s) | Aceleración RG (media geométrica) |
|---|---|---|---|
| Potencia (20 consultas, `summary-power.md`) | 148.3 | 96.7 | **1.90x** (scan 2.28x, cpu 1.58x) |
| Lago: tablas locales (6 consultas) | 7.6 | 4.5 | 1.77x |
| Lago: Iceberg en S3 vía Glue (`ice.*`) | 29.4 | 14.6 | 1.87x |
| Lago: Parquet en S3 vía Glue (`pq.*`) | 31.7 | 50.6 | **0.82x** (RG más lento) |
| ELT: COPY `store_returns` | 40.1 | 26.8 | 1.50x |
| ELT: CTAS pesado | 7.7 | 4.8 | 1.62x |

Concurrencia (5 flujos, 30 min): RA3 **680** consultas/hora, RG **1224**
consultas/hora (1.8x), sin cola (p50 y p95 de espera 0 s) y sin fallas en ambos.

Spectrum en RA3 (USD 5 por TB escaneado, `prices.md`): la corrida de Iceberg
escaneó 18.2 GB (USD 0.083) y la de Parquet 20.2 GB (USD 0.092). RG no paga
Spectrum.

## Lo que hay que mirar antes de llevarlo a un slide

- **Parquet en RG:** `lq3` (≈18 s frente a 1.8 s en RA3) y `lqst` (≈18 s frente
  a 10 s) son más lentas en RG en las tres pasadas, así que no es caché fría.
  En las otras cuatro consultas RG empata o gana.
  **Revisado el 2026-10-05 (19:50 UTC):**
  - `EXPLAIN` de `lq3` y `lqst` da **el mismo plan** en ambos clústeres: mismo
    orden de joins, mismas estrategias (`DS_BCAST_INNER`), mismas estimaciones
    de filas. Por la regla del spec, la diferencia no es el plan.
  - Las estadísticas están: las tablas `pq.*` tienen `numRows` correcto
    (`store_sales` = 287.997.024). Descartada esa sospecha.
  - Lo único distinto en el plan es el operador de lectura: RA3 lee S3 con
    Spectrum (`S3 Query Scan`), RG con su motor integrado (`XN Seq Scan ...
    format:PARQUET`).
  - El formato en S3 es muy distinto: Parquet `store_sales` quedó en **4
    archivos de ≈3,8 GB** (uno por slice del clúster que lo escribió con CETAS);
    Iceberg `store_sales` en **28 archivos de ≈480 MB**.
  - Causa del tamaño: `CREATE EXTERNAL TABLE AS` escribe un archivo por slice
    con tope por defecto de 6.200 MB (`write.maxfilesize.mb`, documentación de
    CREATE EXTERNAL TABLE, leída el 2026-10-05).
  - **Prueba (20:07 UTC):** `pq.store_sales` reescrito con
    `'write.maxfilesize.mb'='480'` → 31 archivos de ≈496 MB (mismos 15.379 MB),
    y `rr lake --variant parquet` repetido en ambos clústeres en paralelo
    (`rr-ra3-lake-parquet-df42`, `rr-rg-lake-parquet-f7c8`, sin exclusiones).

    | Parquet `store_sales` | RA3 total (s) | RG total (s) | RG frente a RA3 |
    |---|---|---|---|
    | 4 archivos de ≈3,8 GB | 31.7 | 50.6 | 0.82x |
    | 31 archivos de ≈0,5 GB | 46.5 | 36.3 | 1.76x |

    - RG mejora con archivos chicos: `lq3` 18,0 → 12,7 s y `lqst` 19,2 → 12,5 s
      (≈30 %). El tamaño de archivo pesa en el motor integrado de RG.
    - Pero RG sigue más lento en esas dos consultas que con los mismos datos en
      Iceberg (`lq3` ≈12,7 s en Parquet frente a ≈2,4 s en Iceberg): el tamaño
      explica una parte de la brecha, no toda.
    - RA3 empeoró con los archivos chicos (31,7 → 46,5 s; `lq42` 3,9 → 8,1 s):
      Spectrum manejaba bien pocos archivos grandes. Es una sola repetición, así
      que puede haber variación entre corridas.
    - El 1.76x mezcla ambos efectos; lo sólido es la dirección, no el número.
  - Mensaje para el slide, con lo verificado: con el mismo plan, el resultado
    del lago depende de cómo están escritos los archivos, y el mismo cambio de
    formato ayuda a un motor (RG) y perjudica al otro (Spectrum en RA3).
- **Iceberg en RG:** la primera pasada es lenta (hasta 27 s, frente a ≈2 s
  después) y luego RG es mucho más rápido que RA3: RG cachea los datos del lago
  tras la primera lectura. El 1.87x excluye la pasada de calentamiento, igual
  que todos los escenarios; es una cifra con caché caliente.
- **ELT:** con 2 pasadas, la mediana sin calentamiento es una sola corrida.
