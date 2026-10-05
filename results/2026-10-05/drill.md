# Simulacro de migración RA3 → RG (elastic resize), 2026-10-05

Origen: `rr-drill` restaurado de `rr-ra3-100gb` (2x ra3.xlplus, 100 GB TPC-DS).
Destino: 2x rg.xlarge, elastic resize (`ResizeType = ElasticResize`).
Método: `scripts/drill.sh`, que cada 30 s registra el estado del resize y prueba
una escritura (`INSERT` en una tabla de prueba). Datos crudos en `drill-log.csv`.

| Momento (UTC) | Evento |
|---|---|
| 19:02:30 | `rr-drill` disponible tras restaurar (unos 3 min desde el pedido) |
| 19:04:25 | Snapshot previo al resize (tardó unos 17 s) |
| 19:05:47 | Inicio del elastic resize |
| 19:05:53 | Escritura OK |
| 19:06:25 | Primera escritura rechazada: empieza la ventana de solo lectura |
| 19:08:00 | Última escritura rechazada |
| 19:08:35 | Resize `SUCCEEDED`, escritura OK, nodo `rg.xlarge` |

- **Duración total del resize:** unos 2 min 48 s.
- **Ventana de solo lectura:** entre 2 min 07 s (lo observado, 19:06:25 → 19:08:00)
  y 2 min 42 s (cota superior con sondeo de 30 s, 19:05:53 → 19:08:35).
- **Skew:** idéntico antes y después en todas las tablas (`skew-drill.csv` frente
  a `skew-rg.csv`; `skew_rows` 1.00–1.01 en las tablas de hechos). El mapeo 1:1
  ra3.xlplus → rg.xlarge con la misma cantidad de nodos conserva la distribución
  por slices, así que no aparece skew. El riesgo de skew que advierte la
  documentación del elastic resize aplica cuando cambia la cantidad de nodos
  (por ejemplo, 4 ra3.4xlarge → 3 rg.4xlarge); este simulacro no lo cubre.

Requisitos que aparecieron en el camino (ya resueltos en `scripts/drill.sh`):
1. Un snapshot con contraseña administrada por Redshift solo se restaura con
   `--manage-master-password`.
2. Un clúster restaurado de snapshot no acepta elastic resize hasta tener un
   backup propio: hay que sacar un snapshot manual antes (la documentación lo
   recomienda igual para acortar el resize).
3. Tras restaurar y sacar el snapshot, `ClusterStatus` dice `available` pero
   `ClusterAvailabilityStatus` sigue en `Modifying`; el resize falla con
   "being modified by a concurrent operation" hasta que pasa a `Available`.
