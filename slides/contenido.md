# Redshift Redemption — contenido de las diapositivas

Charla: «Redshift Redemption: los nuevos nodos RG, ¿migrar o no migrar?»
Evento: AWS Women Colombia User Group, Episodio II «El Ataque de los Graviton»,
2026-10-08, 6:00 p. m. (hora de Colombia). Nivel 200. Una hora en total
(apertura del host, charla con demo no en vivo, Kahoot, despedida).

Fuente única de cada número: `results/2026-10-05/` (resumen de potencia:
`summary-power.md`; lago, ELT y concurrencia: `summary-otros.md`; migración:
`drill.md`; tarifas: `results/prices.md`). Ninguna cifra de la charla sale de
otro lado. Las promesas de AWS se citan con su fuente y se presentan como
promesas que probamos, nunca como «marketing contra verdad».

Plantilla: `slides/evento/plantilla-oct-epII.pptx`, variante oscura en toda la
presentación. Tipos de diapositiva de la plantilla: **Agenda**, **Título +
contenido** (panel redondeado a la derecha) y **Transición**. 35 diapositivas
(límite del evento: 40). Sin animaciones ni videos. Unos 45 minutos de charla.

---

## 1 · Portada — *Título + contenido*

**Título:** Redshift Redemption

**Contenido:**
- Los nuevos nodos RG: ¿migrar o no migrar?
- Andrés Zeballos · Solutions Architect, phData
- 100 GB TPC-DS · RA3 frente a RG · 2026-10-05

**Visual:** el número grande «1.90x» en azul acento como gancho visual, con la
etiqueta «más rápido en nuestro lab» debajo.

**Notas del orador:** Buenas tardes. Hoy no vengo a contarles lo que dice el
anuncio de AWS; vengo a contarles qué pasó cuando lo medí. Ese 1.90x es uno de
los números de hoy, y al final van a ver que no es el único que importa.

---

## 2 · Quién soy — *Título + contenido*

**Título:** Quién soy

**Contenido:**
- De Arequipa; Solutions Architect en phData, casi siempre con AWS
- Redes → infraestructura → Kubernetes → datos → agentes de IA
- AWS Golden Jacket · colaboré en las nuevas microcredenciales de análisis de datos de AWS
- Cada charla sale de un laboratorio que armo y publico para que lo repitas

**Visual:** foto del orador (la agrega Andrés) o, si no, cuatro íconos en fila
para la trayectoria.

**Notas del orador:** Me gusta probar las cosas antes de recomendarlas. Esta
charla es eso: un laboratorio que armé esta semana, con su costo y sus errores
incluidos.

---

## 3 · Agenda — *Agenda*

**Título:** AGENDA

**Contenido (6 viñetas de la plantilla):**
- Qué cambió de RA3 a RG
- Cómo lo medimos
- Warehouse: potencia, concurrencia y costo
- Data lake: Iceberg, Parquet y Spectrum
- La migración y sus trampas
- Demo

**Notas del orador:** Cinco temas y una demo. Al final, una respuesta concreta a
la pregunta del título, y tres preguntas de Kahoot.

---

## 4 · La pregunta — *Título + contenido*

**Título:** ¿Migro o no migro?

**Contenido:**
- En mayo de 2026, Redshift estrenó los nodos RG, con procesadores Graviton
- Si administras un Redshift con RA3, o pagas su factura, la pregunta llegó sola
- Hoy tomamos las promesas de AWS y las ponemos a prueba: dónde se cumplen y dónde dependen de tu carga

**Visual:** dos tarjetas lado a lado, «RA3» y «RG», con un signo de pregunta
entre ellas.

**Notas del orador:** La idea no es desmentir a nadie. AWS publica sus
números; nosotros los verificamos en el tamaño de clúster que la mayoría
opera. Cuando se cumplen, lo decimos; cuando dependen de algo, explicamos de qué.

---

## 5 · Transición — *Transición*

**Título:** QUÉ CAMBIÓ

**Notas del orador:** Primero, qué es exactamente un nodo RG y en qué se
diferencia de RA3.

---

## 6 · Lo nuevo de RG — *Título + contenido*

**Título:** Qué trae RG

**Contenido (dos columnas):**
- **Graviton:** instancias basadas en los procesadores Arm de AWS
- **Motor de lago integrado:** las consultas al data lake corren en el propio clúster; RA3 usa Redshift Spectrum, una flota aparte
- **Sin cargo por TB escaneado:** RA3 paga USD 5 por TB que lee Spectrum; RG no tiene ese cargo
- **Lo que no cambia:** mismo motor de Redshift, mismo almacenamiento administrado (RMS, USD 0,024 por GB-mes)

**Visual:** diagrama simple: RA3 → (flecha naranja) → flota Spectrum → S3;
RG → (flecha azul) → S3 directo desde el clúster.

**Notas del orador:** Esto es importante para entender los resultados del lago:
cuando comparamos RA3 con RG en el lago no comparamos solo procesadores,
comparamos dos motores distintos. Por eso siempre hablo de «motor + chip» y
nunca de «solo el chip».

**Fuente:** documentación de Redshift, «Amazon Redshift provisioned clusters»
(RG trae «Graviton-based instance types» e «Integrated data lake query
engine»); tarifas en `results/prices.md`.

---

## 7 · Tamaños y precios — *Título + contenido*

**Título:** Cuatro tamaños, 30 % menos por vCPU

**Contenido:** tabla nativa.

| RA3 | vCPU | USD/h | → | RG | vCPU | USD/h | USD por vCPU-hora |
|---|---|---|---|---|---|---|---|
| — | | | | rg.large | 2 | 0,3801 | 0,190 |
| ra3.xlplus | 4 | 1,086 | 1:1 | rg.xlarge | 4 | 0,7602 | 0,272 → 0,190 |
| ra3.4xlarge | 12 | 3,26 | 4 → 3 | rg.4xlarge | 16 | 3,04267 | 0,272 → 0,190 |
| — | | | | rg.12xlarge | 48 | 9,128 | 0,190 |

Llamada debajo de la tabla: **4 × ra3.4xlarge = 3 × rg.4xlarge = 48 vCPU →
USD 13,04/h frente a 9,13/h.**

**Notas del orador:** El 30 % por vCPU se cumple al centavo: 1,086 entre 4
vCPU contra 0,7602 entre 4. Ojo con el 4xlarge: un ra3.4xlarge tiene 12 vCPU y
un rg.4xlarge tiene 16. AWS recomienda pasar 4 nodos RA3 a 3 nodos RG; si migras
1 a 1 en ese tamaño compras un tercio más de capacidad de la que tenías.

**Fuente:** vCPU de la documentación «Node type details» (leída el
2026-10-05); precios on-demand us-east-1 del Price List API (`results/prices.md`
para xlplus, xlarge y 4xlarge; rg.large y rg.12xlarge del spec, 2026-09-24);
mapeo 4 → 3 del blog de AWS «RA3 to RG migration best practices».

---

## 8 · Las promesas — *Título + contenido*

**Título:** Lo que promete AWS

**Contenido (cuatro tarjetas):**
- **Hasta 2,2x** más rápido en el warehouse
- **Hasta 2,4x** en el data lake (Iceberg; 1,5x en Parquet)
- **−30 %** por vCPU
- **Sin cargo** de Spectrum por TB escaneado

Pie: «AWS midió TPC-DS y TPC-H a 10 TB en rg.4xlarge».

**Notas del orador:** Estas son las cuatro promesas que vamos a probar. Fíjense
en el pie: AWS midió 10 TB en nodos 4xlarge. Yo medí el clúster que la mayoría
de los equipos opera de verdad.

**Fuente:** blog de AWS Big Data «Meet Amazon Redshift RG…», 2026-05-19
(leído el 2026-10-05: «up to 2.2x», «up to 2.4x» Iceberg, «up to 1.5x» Parquet,
«30% lower price per vCPU», sin el cargo de USD 5/TB; TPC-DS y TPC-H a 10 TB en
rg.4xlarge).

---

## 9 · Transición — *Transición*

**Título:** CÓMO LO MEDIMOS

**Notas del orador:** Antes de mostrar un solo número, cómo lo obtuve, porque un
benchmark sin método es una opinión con decimales.

---

## 10 · El laboratorio — *Título + contenido*

**Título:** El laboratorio

**Contenido:** imagen `slides/assets/arquitectura-lab.png` ocupando el panel.

**Visual:** diagrama de arquitectura (también cumple el pedido del evento de una
imagen de arquitectura de la demo).

**Notas del orador:** Una VPC propia con enhanced VPC routing y endpoints para
S3, Glue, Lake Formation y S3 Tables. RA3 con 2 nodos ra3.xlplus; RG con 2 nodos
rg.xlarge restaurado del mismo snapshot, así que los dos clústeres tienen
exactamente los mismos datos. El lago en S3: Iceberg y Parquet registrados en
Glue. Las consultas las lanza un runner en Python por la Data API, y la
infraestructura la crea GitHub Actions con OIDC, sin llaves guardadas en ningún
lado.

---

## 11 · Método justo — *Título + contenido*

**Título:** Un método justo

**Contenido:**
- Mismo snapshot y misma versión de Redshift (1.0.434008) en los dos clústeres
- Caché de resultados apagada y escalado de concurrencia en 0
- Tiempos medidos en el servidor (`SYS_QUERY_HISTORY`), no en mi laptop
- Mediana por consulta, sin la pasada de calentamiento
- Una corrida con caché o escalado se invalida sola y no se reporta

**Visual:** checklist con íconos de verificación.

**Notas del orador:** Lo más importante es el último punto: el runner revisa
cada consulta y si alguna usó la caché de resultados, la corrida entera se
descarta. Ninguna se descartó hoy.

**Fuente:** `runner/rr/stats.py`, `runner/rr/metrics.py`,
`summary-power.md` (encabezado de versión).

---

## 12 · Lo que no medimos — *Título + contenido*

**Título:** Lo que no medimos

**Contenido:**
- 100 GB, no 10 TB: con este volumen pesan más los costos fijos de cada consulta
- 2 nodos de tamaño xlarge, no 4xlarge ni 12xlarge
- No medimos Serverless (lo vemos solo con documentación y precios)
- No medimos S3 Tables (más adelante, el porqué)

**Visual:** cuatro tarjetas con ícono de «fuera de alcance».

**Notas del orador:** Prefiero decirlo al principio. Con 100 GB los datos
calientes caben en buena parte en memoria, y eso reduce la ventaja de RG en
escaneos grandes. Si aun así vemos ventaja, es una buena señal; con más datos
esperaría que la brecha de scan crezca, pero no lo medí.

---

## 13 · Transición — *Transición*

**Título:** WAREHOUSE

**Notas del orador:** Empecemos por lo que hace todo warehouse: consultas sobre
tablas propias.

---

## 14 · Potencia — *Título + contenido*

**Título:** 1,90x más rápido

**Contenido:** gráfico nativo de barras horizontales: aceleración de RG por
consulta (20 consultas TPC-DS), color por clase (scan / cpu), línea de
referencia en 1x.

Llamada lateral: **total 148,3 s → 96,7 s · p50 1,65 s → 0,58 s**

**Notas del orador:** Veinte consultas, cada una tres veces, primera de
calentamiento. RG fue más rápido en las veinte. La que más ganó, query48, 3,58
veces; la que menos, query57, 1,08 veces. La media geométrica, que es la forma
justa de promediar aceleraciones, da 1,90x.

**Fuente:** `summary-power.md`.

---

## 15 · Scan frente a CPU — *Título + contenido*

**Título:** Gana más el que escanea

**Contenido (dos estadísticas grandes):**
- **2,28x** consultas de scan y agregación (10 consultas)
- **1,58x** consultas de CPU: ventanas, joins grandes, rollups (10 consultas)

Pie: «La promesa de AWS es hasta 2,2x: en scan la superamos; en CPU, no.»

**Notas del orador:** Separé las consultas en dos clases antes de correrlas, no
después. Las que leen mucho y agregan ganaron 2,28 veces: ahí es donde Graviton
y el ancho de banda de memoria brillan. Las de CPU, con funciones de ventana y
joins de quince tablas, ganaron 1,58. Si tu warehouse es mayormente dashboards
con agregaciones, estás del lado bueno.

**Fuente:** `summary-power.md` (tabla por clase); clases en `sql/curated.txt`.

---

## 16 · Concurrencia — *Título + contenido*

**Título:** Concurrencia: 1,8x más consultas

**Contenido:** gráfico nativo de dos barras: consultas por hora, RA3 680 frente
a RG 1224.

Pie: «5 flujos durante 30 minutos · sin cola en ninguno · cero fallas»

**Notas del orador:** Cinco usuarios lanzando las mismas veinte consultas en
orden aleatorio durante media hora. RG completó 1224 consultas por hora contra
680 de RA3. Ninguno tuvo que encolar consultas.

**Fuente:** `summary-otros.md` (concurrencia).

---

## 17 · Carga y ELT — *Título + contenido*

**Título:** Cargar y transformar

**Contenido:**
- **100 GB en 20 min 44 s** con COPY desde S3 en 2 × ra3.xlplus
- COPY de `store_returns`: 40,1 s → 26,8 s (**1,50x**)
- CTAS pesado (ventas × fechas × ítems): 7,7 s → 4,8 s (**1,62x**)

**Visual:** gráfico nativo de barras agrupadas RA3/RG para COPY y CTAS.

**Notas del orador:** La carga inicial la hice una sola vez, en RA3, y RG nació
del snapshot. El escenario de ELT repite un COPY y un CTAS en los dos: RG fue
1,5 y 1,6 veces más rápido. Son dos corridas por escenario, así que lo tomo como
dirección, no como número exacto.

**Fuente:** `results/2026-10-05/rr-ra3-load-0703.csv`; `summary-otros.md`
(ELT).

---

## 18 · Costo — *Título + contenido*

**Título:** Más rápido y más barato

**Contenido (dos estadísticas grandes):**
- **USD 0,089 → 0,041** por corrida del escenario de potencia
- **2,2 veces menos** costo por la misma carga

Pie: «Se suman dos efectos: el nodo cuesta 30 % menos por hora y termina antes.»

**Notas del orador:** Esto es lo que más le interesa a quien paga la factura. No
es solo que el nodo sea más barato: como también termina antes, cada corrida
cuesta menos de la mitad.

**Fuente:** `summary-power.md` (USD por corrida); `results/prices.md`.

---

## 19 · Transición — *Transición*

**Título:** DATA LAKE

**Notas del orador:** Ahora la parte más interesante, y la que más depende de
cómo tienes tus datos.

---

## 20 · Tres formas de leer — *Título + contenido*

**Título:** El mismo dato, tres formas

**Contenido (tres columnas):**
- **Local:** tablas cargadas en el warehouse
- **Iceberg:** tablas en S3, registradas en Glue (`ice.*`)
- **Parquet:** tablas externas en S3, registradas en Glue (`pq.*`)

Pie: «Mismas 6 consultas en las tres. RA3 lee S3 con Spectrum (fuera de tu
VPC); RG, con su motor integrado (dentro de tu VPC).»

**Notas del orador:** Escribí las mismas cinco tablas en Iceberg y en Parquet
desde el warehouse, y comprobé que las seis consultas del lago devuelven
exactamente las mismas 483 filas en las tres versiones. Así lo único que cambia
es cómo se leen.

**Fuente:** `summary-otros.md`; verificación de filas en la sesión del
2026-10-05.

---

## 21 · Iceberg — *Título + contenido*

**Título:** Iceberg: 1,87x con caché caliente

**Contenido:** gráfico nativo de barras: RA3 29,4 s frente a RG 14,6 s
(total de 6 consultas).

Llamada: **Primera lectura en RG: hasta 27 s. Después: unos 2 s.**

**Notas del orador:** RG lee Iceberg casi dos veces más rápido que RA3, pero hay
letra chica: la primera vez que RG toca los datos tarda bastante más, porque los
trae y los guarda en caché. Mi método descarta la primera pasada, así que este
1,87x es con caché caliente. Si tus consultas al lago son esporádicas, cuenta
con esa primera lectura.

**Fuente:** `summary-otros.md` (Iceberg y nota de caché).

---

## 22 · Parquet — *Título + contenido*

**Título:** Parquet: mandan los archivos

**Contenido:** tabla nativa.

| Parquet `store_sales` | RA3 (total) | RG (total) | RG frente a RA3 (media geométrica) |
|---|---|---|---|
| 4 archivos de ≈3,8 GB | 31,7 s | 50,6 s | **0,82x** |
| 31 archivos de ≈0,5 GB | 46,5 s | 36,3 s | **1,76x** |

Pie: «Mismo plan de ejecución en los dos clústeres (EXPLAIN idéntico).»

**Notas del orador:** Este fue el resultado que más me sorprendió. Con Parquet,
RG empezó siendo más lento que RA3. Revisé el plan de ejecución: idéntico en los
dos. Lo distinto era el formato de los archivos: Redshift los había escrito en
solo cuatro archivos enormes. Los reescribí en archivos de medio giga y RG pasó a
ganar 1,76 veces, mientras que RA3 empeoró. El mismo cambio ayuda a un motor y
perjudica al otro. Es una sola repetición: crean la dirección, no el número
exacto.

**Fuente:** `summary-otros.md` (revisión de Parquet, 19:50 y 20:07 UTC).

---

## 23 · El costo de Spectrum — *Título + contenido*

**Título:** Spectrum se cobra aparte

**Contenido (dos estadísticas):**
- **18,2 GB** en Iceberg (2 pasadas medidas, RA3) → **USD 0,083**
- **20,2 GB** en Parquet (2 pasadas medidas) → **USD 0,092**
- En RG: **USD 0** por escaneo

Pie: «USD 5 por TB escaneado en RA3. Multiplica por tus consultas al lago de
un mes.»

**Notas del orador:** En nuestro lab son centavos, porque son 100 GB. Pero esto
escala con el volumen y con la frecuencia: un equipo que escanea decenas de TB
al mes en el lago lo nota en la factura. En RG ese cargo desaparece.

**Fuente:** `summary-otros.md` (Spectrum); `results/prices.md`.

---

## 24 · Lo que no pudimos medir — *Título + contenido*

**Título:** Lo que el lago nos enseñó

**Contenido:**
- **S3 Tables: IAM:** las tablas `"bucket@s3tablescatalog"` se leen por el catálogo montado automáticamente, que exige conectarse con identidad IAM; un usuario de base de datos recibe «cross-database reference … is not supported»
- **Iceberg: sin CHAR:** al escribir desde Redshift hay que convertir `char(n)` a `varchar(n)`
- **Lake Formation:** sin permisos explícitos, «Insufficient Lake Formation permission(s)»

**Visual:** tres tarjetas con el mensaje de error real en tipografía monoespaciada.

**Notas del orador:** Quería medir S3 Tables y no pude, por una razón de diseño:
el runner se conecta con un usuario de base de datos y S3 Tables exige identidad
IAM. Cambiar de usuario solo para esa variante habría medido otra ruta de
permisos. Si piensas usar S3 Tables desde Redshift, define primero tu modelo de
autenticación.

**Fuente:** documentación de Redshift «Query Amazon S3 Tables from Amazon
Redshift» (método 3, auto-mount); runbook §1.

---

## 25 · Transición — *Transición*

**Título:** LA MIGRACIÓN

**Notas del orador:** Supongamos que decides migrar. ¿Cuánto duele?

---

## 26 · Simulacro de migración — *Título + contenido*

**Título:** Migrar tomó 2 min 48 s

**Contenido:** línea de tiempo.
- 19:05:47 inicio del elastic resize (2 × ra3.xlplus → 2 × rg.xlarge)
- 19:06:25 primera escritura rechazada: empieza el solo lectura
- 19:08:35 resize terminado, escrituras de vuelta

Llamadas: **Solo lectura: entre 1 min 35 s y 2 min 42 s** · **Skew: sin
cambios**

**Notas del orador:** Restauré una copia de RA3 e hice el elastic resize a RG,
probando una escritura cada 30 segundos. El clúster estuvo en solo lectura entre
1 min 35 s y 2 min 42 s. Con el mapeo 1 a 1 se conserva la cantidad de slices, así
que la distribución de los datos no cambió. Ojo: eso vale para 2 nodos a 2
nodos; si cambias la cantidad de nodos, como en el 4 → 3 de los 4xlarge, el skew
sí puede aparecer.

**Fuente:** `drill.md`, `drill-log.csv`.

---

## 27 · Trampas — *Título + contenido*

**Título:** Trampas del camino

**Contenido:**
- **Contraseña administrada:** un snapshot con contraseña administrada por Redshift solo se restaura con `--manage-master-password`
- **Primero un backup:** un clúster restaurado de snapshot no acepta elastic resize hasta tener un snapshot propio
- **«Available» no siempre es disponible:** tras restaurar, el estado dice `available` mientras otro campo sigue en `Modifying`
- **El 4 → 3 y el skew:** cambiar la cantidad de nodos puede desbalancear los slices
- **Restore = endpoint nuevo:** si migras restaurando, reconfigura zero-ETL, DMS y datashares

**Visual:** cinco filas con ícono de advertencia.

**Notas del orador:** Las tres primeras me pasaron en el simulacro, en ese
orden, y no las encontré en la guía de migración. Las dos últimas sí están en la
documentación y en el blog de AWS. Todas quedaron resueltas en el script del
repo.

**Fuente:** `drill.md`; documentación de resize; blog «RA3 to RG migration best
practices».

---

## 28 · Transición — *Transición*

**Título:** DEMO

**Notas del orador:** Ahora veamos las consultas y los datos reales.

---

## 29 · Demo: una consulta — *Título + contenido*

**Título:** Demo: una consulta, dos generaciones

**Contenido (dos columnas):** izquierda, el SQL de `query96` en monoespaciado:

```sql
SELECT count(*)
FROM store_sales, household_demographics, time_dim, store
WHERE ss_sold_time_sk = time_dim.t_time_sk
  AND ss_hdemo_sk = household_demographics.hd_demo_sk
  AND ss_store_sk = s_store_sk
  AND time_dim.t_hour = 15 AND time_dim.t_minute >= 30
  AND household_demographics.hd_dep_count = 7
  AND store.s_store_name = 'ese'
LIMIT 100;
```

derecha, dos estadísticas: **RA3 1,77 s · RG 0,67 s · 2,64x**

**Notas del orador:** Una consulta típica de scan: cuenta ventas filtrando por
tres dimensiones. 288 millones de filas en la tabla de hechos. En RA3 tarda 1,77
segundos; en RG, 0,67.

**Fuente:** `summary-power.md` (query96); SQL de `sql/vendor/query_0.sql`
(awslabs, derivado de TPC-DS).

---

## 30 · Demo: mismo plan — *Título + contenido*

**Título:** Demo: mismo plan, distinto motor

**Contenido (dos columnas):** extracto del EXPLAIN de `lq3` sobre Parquet:
- RA3: `XN Hash Join DS_BCAST_INNER` → `XN S3 Query Scan ss` (Spectrum)
- RG: `XN Hash Join DS_BCAST_INNER` → `XN Seq Scan pq.store_sales … format:PARQUET` (motor integrado)

Debajo: «Mismas estimaciones de filas (287.997.024 en `store_sales`). Lo único
distinto: quién lee S3.»

**Notas del orador:** Así diagnostiqué el caso de Parquet. Si los planes fueran
distintos, la diferencia sería el plan y no el motor. Son iguales; cambia el
operador que lee S3. Cuando veas una diferencia rara entre clústeres, empieza
por aquí.

**Fuente:** `summary-otros.md` (revisión de Parquet).

---

## 31 · Demo: los resultados — *Título + contenido*

**Título:** Demo: todos los resultados

**Contenido:** captura de la página interactiva de resultados y su enlace.
- Aceleración por consulta, filtrable por clase
- El lago antes y después de reescribir Parquet
- La línea de tiempo del simulacro

**Visual:** captura de pantalla de `slides/demo/resultados.html` (en la charla
se abre en el navegador).

**Notas del orador:** Esta página tiene todos los números de la charla, sacados
directamente de los archivos del repo. La voy a abrir un momento para que vean
cada consulta. Enlace (privado, con la sesión del orador):
https://claude.ai/artifact/1MgMakVPq4URRXQMZp4aVk; copia local `slides/demo/resultados.html`.

---

## 32 · ¿Migrar o no migrar? — *Título + contenido*

**Título:** ¿Migrar o no migrar?

**Contenido (tres columnas):**
- **Migra si:** tu carga es de scan y agregación · lees el data lake con frecuencia · estás en xlplus o 4xlarge (30 % menos por vCPU)
- **Prueba antes si:** tu carga es de CPU (ventanas, joins grandes) · tu lago es Parquet con archivos grandes · necesitas S3 Tables con usuarios de base de datos
- **Serverless si:** tu uso es intermitente y no quieres operar un clúster (USD 0,375 por RPU-hora; no lo medimos)

**Notas del orador:** Esta es mi respuesta a la pregunta del título. Para la
mayoría de los equipos con RA3 la migración conviene: es más rápida y más
barata, y el resize toma minutos. Pero prueba con tus datos, sobre todo si tu
lago es Parquet o tu carga es de CPU. Serverless es otra decisión, sobre la forma
de tu uso, y no la medí, así que no te doy un número.

---

## 33 · Llévate el lab — *Título + contenido*

**Título:** Llévate el laboratorio

**Contenido:**
- **github.com/andrezc98/redshift-redemption**
- Terraform + GitHub Actions con OIDC · runner en Python · runbook paso a paso
- Todos los resultados y su método en `results/`
- Este lab, a 100 GB: un día de trabajo y unas decenas de dólares

**Visual:** código QR del repositorio (se genera el 2026-10-07, cuando el repo
sea público).

**Notas del orador:** Todo lo que vieron está en el repo: la infraestructura, el
runner, el runbook con cada paso y los errores que encontré. Cámbiale el dataset
por el tuyo y repite las mediciones.

---

## 34 · Kahoot — *Título + contenido*

**Título:** Kahoot

**Contenido:** las tres preguntas de la sección siguiente (las maneja el host).

**Notas del orador:** Momento del Kahoot. Después de cada pregunta comento la
respuesta.

---

## 35 · Gracias — *Título + contenido*

**Título:** ¡Gracias!

**Contenido:**
- Andrés Zeballos · Solutions Architect, phData
- LinkedIn y GitHub: andrezc98 (confirmar el usuario de LinkedIn antes del evento)
- Repo del lab: github.com/andrezc98/redshift-redemption

**Notas del orador:** Gracias. Respondo preguntas en el chat. Si te preguntan
por Snowflake u otras plataformas: «Trabajo con varias y son buenas respuestas a
contextos distintos; hoy vine a medir la decisión que los equipos nativos de AWS
ya tienen enfrente: RA3 o RG».

---

## Preguntas de Kahoot (con respuesta)

**1. ¿Con qué leen el data lake los clústeres RG?**
- a) Redshift Spectrum
- b) **Un motor de lago integrado en el propio clúster** ✅
- c) Amazon Athena
- d) Trabajos ETL de AWS Glue

Comentario: RA3 usa Spectrum, una flota aparte que cobra USD 5 por TB
escaneado; RG lee el lago con sus propios nodos y sin ese cargo.

**2. En el laboratorio, ¿qué tipo de consultas ganó más al pasar de RA3 a RG?**
- a) Las de CPU: funciones de ventana y joins grandes
- b) **Las de scan y agregación** ✅
- c) Ninguna: dieron igual
- d) Solo las del data lake

Comentario: scan 2,28x frente a CPU 1,58x; la media de las 20 consultas fue
1,90x.

**3. Si migras 4 nodos ra3.4xlarge, ¿cuántos rg.4xlarge recomienda AWS?**
- a) 4
- b) **3** ✅
- c) 2
- d) 8

Comentario: un ra3.4xlarge tiene 12 vCPU y un rg.4xlarge tiene 16; 4 × 12 = 3 ×
16 = 48. Migrar 1 a 1 en ese tamaño sobredimensiona un tercio.
