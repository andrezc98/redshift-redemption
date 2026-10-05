# Redshift Redemption — contenido de las diapositivas

Generado por `slides/build_deck.py` a partir del deck; no se edita a mano (cambia el script y
reconstruye). Charla: «Redshift Redemption: los nuevos nodos RG, ¿migrar o no migrar?», AWS Women
Colombia User Group, Episodio II, 2026-10-08. Cada número sale de `results/2026-10-05/` y
`results/prices.md`; las fuentes externas se citan en la diapositiva o en sus notas.

## 1
- Redshift Redemption
- Los nuevos nodos RG: ¿migrar o no migrar?
- Andrés Zeballos · Solutions Architect en phData
- Medido con 100 GB de TPC-DS · octubre de 2026
- 1,90x
- más rápido, en promedio, en nuestras pruebas

**Notas:** Buenas tardes. Hoy no vengo a repetir el anuncio de AWS: vengo a contarles qué pasó cuando lo puse a prueba. Ese 1,90 es uno de los resultados, y al final van a ver que no es el único que importa.

## 2
- Quién soy
- Soy de Arequipa y trabajo como Solutions Architect en phData, casi siempre con AWS.
- Empecé en redes y fui pasando por infraestructura, Kubernetes y datos. Hoy ando metido con agentes de IA.
- Tengo el Golden Jacket de AWS y hace poco me invitaron a ayudar a crear las nuevas microcredenciales de análisis de datos.
- Probar antes de recomendar
- Cada charla que doy sale de un laboratorio que armo y después publico para que cualquiera lo repita.

**Notas:** Me gusta probar las cosas antes de recomendarlas. Esta charla es justamente eso: un laboratorio que armé esta semana, con lo que costó y con los errores que me encontré en el camino.

## 3
- Qué cambia con RG
- Cómo lo medimos
- Warehouse: velocidad, concurrencia y costo
- Data lake: Iceberg, Parquet y Spectrum
- La migración y lo que nadie te cuenta
- Demo

**Notas:** Cinco temas y una demo. Al final les doy una respuesta concreta a la pregunta del título, y cerramos con tres preguntas de Kahoot.

## 4
- ¿Migro o no migro?
- RA3
- Lo que usas hoy
- ?
- RG
- Con Graviton, desde mayo de 2026
- Si tienes un Redshift con nodos RA3, o eres quien paga la factura, seguramente ya te hiciste esta pregunta.
- Hoy revisamos lo que anunció AWS con pruebas propias: en qué se cumple y en qué depende de cómo usas Redshift.

**Notas:** La idea no es desmentir a nadie. AWS publicó sus números y yo los revisé en un clúster chico, como el que tienen muchos equipos. Donde se cumplen, lo digo; donde dependen de algo, les explico de qué.

## 5
- QUÉ
- CAMBIA

**Notas:** Primero, qué es exactamente un nodo RG y en qué se diferencia de RA3.

## 6
- Qué trae RG
- Procesadores Graviton
- Los chips Arm diseñados por AWS
- El data lake sin Spectrum
- RG consulta los datos en S3 con sus propios nodos; RA3 depende de Spectrum, un servicio aparte
- Sin cobro por TB leído
- En RA3, Spectrum cobra USD 5 por cada TB que lee; en RG ese cobro no existe
- Lo que se mantiene
- El mismo Redshift de siempre y el mismo almacenamiento administrado (USD 0,024 por GB al mes)

**Notas:** Esto es clave para entender los resultados del data lake: cuando comparamos RA3 con RG ahí, no comparamos solo procesadores, comparamos dos formas distintas de leer S3. Por eso hablo del chip y de cómo se leen los datos, nunca del chip solo. Fuente: documentación de Redshift, Amazon Redshift provisioned clusters.

## 7
- Cuatro tamaños y 30 % menos por vCPU
- RA3 | vCPU | USD/hora |  | RG | vCPU | USD/hora | USD por vCPU y hora
- — |  |  |  | rg.large | 2 | 0,3801 | 0,190
- ra3.xlplus | 4 | 1,086 | 1 : 1 | rg.xlarge | 4 | 0,7602 | de 0,272 a 0,190
- ra3.4xlarge | 12 | 3,26 | 4 : 3 | rg.4xlarge | 16 | 3,04267 | de 0,272 a 0,190
- — |  |  |  | rg.12xlarge | 48 | 9,128 | 0,190
- 4 nodos ra3.4xlarge equivalen a 3 rg.4xlarge (48 vCPU en total): USD 13,04 frente a 9,13 por hora
- vCPU: documentación de Redshift («Node type details»). Precios on-demand en us-east-1, Price List API.

**Notas:** El 30 % por vCPU se cumple al centavo: 1,086 dividido entre 4 vCPU contra 0,7602 entre 4. Ojo con el tamaño 4xlarge: un ra3.4xlarge tiene 12 vCPU y un rg.4xlarge tiene 16, por eso AWS recomienda pasar de 4 nodos a 3. Si migras uno a uno en ese tamaño, terminas pagando un tercio más de capacidad de la que tenías.

## 8
- Lo que anunció AWS
- Hasta 2,2x
- más rápido en las consultas del warehouse
- Hasta 2,4x
- en el data lake con Iceberg (1,5x con Parquet)
- −30 %
- en el precio por vCPU
- USD 0
- por TB leído desde el data lake
- AWS lo midió con TPC-DS y TPC-H a 10 TB en nodos rg.4xlarge. Nosotros, con 100 GB en un clúster de 2 nodos xlarge.
- Fuente: blog de AWS Big Data «Meet Amazon Redshift RG…», 19 de mayo de 2026.

**Notas:** Estos son los cuatro números del anuncio, y son los que vamos a revisar. Fíjense en la última línea: AWS midió 10 TB en nodos grandes. Yo medí un clúster chico, más parecido al que tienen muchos equipos.

## 9
- CÓMO LO
- MEDIMOS

**Notas:** Antes de mostrar un solo número, les cuento cómo lo obtuve, porque una comparación sin método es solo una opinión con decimales.

## 10
- El laboratorio
- [imagen]

**Notas:** Armé una VPC propia, con enhanced VPC routing y endpoints para S3, Glue, Lake Formation y S3 Tables. El clúster RA3 tiene 2 nodos ra3.xlplus, y el RG, 2 nodos rg.xlarge, creado a partir del mismo snapshot: los dos tienen exactamente los mismos datos. El data lake está en S3, con tablas Iceberg y Parquet registradas en Glue. RA3 lee esos datos con Spectrum, que corre fuera de la VPC; RG los lee con sus propios nodos, desde la VPC. Las consultas las lanza un programa en Python a través de la Data API, y la infraestructura la crea GitHub Actions con OIDC, sin claves guardadas en ningún lado.

## 11
- Una comparación justa
- Los dos clústeres arrancan del mismo snapshot y con la misma versión de Redshift (1.0.434008)
- Sin caché de resultados y sin escalado automático de concurrencia
- Los tiempos los mide Redshift (SYS_QUERY_HISTORY), no mi computadora
- Cada consulta se repite tres veces: la primera no cuenta y nos quedamos con la mediana
- Si alguna consulta usa la caché, la prueba entera se descarta. En este laboratorio no se descartó ninguna.

**Notas:** Lo más importante es el último punto: el programa revisa cada consulta y, si alguna usó la caché de resultados, descarta la prueba completa. No hubo que descartar ninguna.

## 12
- Lo que no probamos
- 100 GB, no 10 TB
- Con pocos datos, el costo fijo de cada consulta pesa más
- Solo el tamaño xlarge
- No probamos 4xlarge ni 12xlarge
- Serverless solo a 4 RPU
- Capacidad fija para comparar; no probamos cómo escala
- S3 Tables
- No lo pudimos probar; más adelante les cuento por qué

**Notas:** Prefiero decirlo desde el principio. Con 100 GB, buena parte de los datos que se consultan cabe en memoria, y eso reduce la ventaja de RG cuando hay que leer mucho. Si aun así RG gana, es buena señal; con más datos esperaría una diferencia mayor, pero eso no lo medí. Serverless lo medimos solo con 4 RPU fijos, sin dejarlo escalar.

## 13
- WAREHOUSE

**Notas:** Empecemos por lo básico de cualquier warehouse: consultas sobre sus propias tablas.

## 14
- RG fue 1,90x más rápido
- [gráfico: Aceleración RG]
- Cuántas veces más rápido fue RG en cada consulta
- ■ lectura   ■ cálculo
- Tiempo total de las 20 consultas
- 148,3 s
- 96,7 s
- RA3
- RG
- menos tiempo es mejor
- Una consulta típica (mediana)
- 1,65 s
- 0,58 s
- RA3
- RG

**Notas:** Veinte consultas, cada una repetida tres veces, sin contar la primera. RG fue más rápido en las veinte. La que más mejoró, query48, fue 3,58 veces más rápida; la que menos, query57, 1,08 veces. En promedio, usando la media geométrica, que es la forma correcta de promediar este tipo de comparaciones, RG fue 1,90 veces más rápido. Para el total de las veinte consultas: RA3 tardó 148 segundos y RG, 97. En azul, las consultas que leen y agregan muchos datos; en naranja, las de cálculo pesado.

## 15
- Donde más gana: leer y agregar
- 2,28x
- consultas que leen y agregan muchos datos (10 consultas)
- 1,58x
- consultas de cálculo pesado: funciones de ventana y joins grandes (10 consultas)
- AWS anuncia hasta 2,2x: en las consultas de lectura lo superamos; en las de cálculo, no llegamos.

**Notas:** Separé las consultas en dos grupos antes de ejecutarlas, no después. Las que leen muchos datos y los agregan mejoraron 2,28 veces: ahí es donde Graviton y el ancho de banda de memoria hacen la diferencia. Las de cálculo pesado, con funciones de ventana y joins de quince tablas, mejoraron 1,58 veces. Si tu warehouse es sobre todo dashboards y reportes con agregaciones, estás en el lado que más gana.

## 16
- Varios usuarios a la vez: 1,8x
- [gráfico: Consultas por hora]
- Consultas por hora (más es mejor)
- Cinco usuarios simulados durante 30 minutos
- Ninguna consulta quedó en espera
- Ningún error

**Notas:** Simulé cinco usuarios lanzando las mismas veinte consultas, en distinto orden, durante media hora. RG completó 1224 consultas por hora y RA3, 680. En ninguno de los dos hubo consultas en espera.

## 17
- Carga y transformación
- Cargar los 100 GB tomó 20 min 44 s
- Desde S3, en RA3, una sola vez
- Copiar una tabla desde S3: 1,50x
- Crear una tabla resumen (CTAS): 1,62x
- [gráfico: RA3, RG]

**Notas:** La carga inicial la hice una sola vez, en RA3, y RG se creó a partir del snapshot. La prueba de transformación repite una copia desde S3 y la creación de una tabla resumen en los dos clústeres: RG fue 1,5 y 1,6 veces más rápido. Cada una se ejecutó dos veces, así que lo tomo como tendencia, no como número exacto.

## 18
- Más rápido y también más barato
- USD 0,089 → 0,041
- lo que costó cada ejecución de las 20 consultas
- 2,2x
- menos costo por el mismo trabajo
- Dos razones que se suman: el nodo RG cuesta 30 % menos por hora y además termina antes.

**Notas:** Esto es lo que más le interesa a quien paga la factura. No solo el nodo es más barato: como termina antes, cada ejecución cuesta menos de la mitad.

## 19
- ¿Y Serverless?
-  | RA3 | RG | Serverless 4 RPU
- 20 consultas (total) | 148,3 s | 96,7 s | 243,9 s
- Consultas por hora, 5 usuarios | 680 | 1224 | 720
- Iceberg (6 consultas) | 29,4 s | 14,6 s | 34,7 s
- Costo por ejecución de las 20 | USD 0,089 | USD 0,041 | USD 0,102
- Con la misma memoria (64 GB) y casi el mismo precio por hora, RG fue 3,1 veces más rápido que Serverless de 4 RPU.
- La capacidad quedó fija a propósito: la ventaja de Serverless es escalar cuando hace falta y no cobrar sin consultas.

**Notas:** Agregué Serverless con la misma memoria que el clúster RG: 4 RPU son 64 GB, y cuestan 1,50 dólares por hora contra 1,52 del clúster. Fijé la capacidad para que no escalara durante la prueba. En esas condiciones, RG fue unas tres veces más rápido en las consultas del warehouse, y Serverless quedó incluso por debajo de RA3 en casi todo. Pero ojo con la conclusión: 4 RPU es el tamaño de entrada, y lo que vende Serverless es otra cosa: escalar solo cuando hace falta y no cobrar cuando no hay consultas. Todas las pruebas de Serverless del día costaron 1,48 dólares. Fuente: results/2026-10-05/summary-serverless.md.

## 20
- DATA
- LAKE

**Notas:** Ahora la parte más interesante, y la que más depende de cómo tienes guardados tus datos.

## 21
- El mismo dato, de tres formas
- Local
- Tablas dentro del warehouse
- Iceberg
- Tablas Iceberg en S3, registradas en Glue
- Parquet
- Archivos Parquet en S3, registrados en Glue
- Las mismas 6 consultas en las tres versiones devuelven exactamente las mismas 483 filas.
- RA3 lee S3 a través de Spectrum, fuera de tu VPC; RG lo lee con sus propios nodos, dentro de tu VPC.

**Notas:** Escribí las mismas cinco tablas en Iceberg y en Parquet desde el warehouse, y comprobé que las seis consultas devuelven exactamente las mismas 483 filas en las tres versiones. Así, lo único que cambia es la forma de leer los datos.

## 22
- Iceberg: 1,87x, ya con caché
- [gráfico: RA3, RG]
- Tiempo total de las 6 consultas
- 29,4 s
- 14,6 s
- RA3
- RG
- menos tiempo es mejor
- Ojo: la primera vez que RG lee los datos tarda hasta 27 s. Desde la segunda, unos 2 s, porque los guarda en caché.

**Notas:** RG lee Iceberg casi dos veces más rápido que RA3, con una salvedad: la primera vez que toca los datos tarda bastante más, porque los trae de S3 y los guarda en caché. Mi método no cuenta la primera repetición, así que este resultado es con la caché ya cargada. Si consultas el data lake de vez en cuando, ten en cuenta esa primera lectura.

## 23
- Parquet: los archivos importan
- Parquet store_sales | RA3 (total) | RG (total) | RG frente a RA3 (media geom.)
- 4 archivos de ≈3,8 GB | 31,7 s | 50,6 s | 0,82x
- 31 archivos de ≈0,5 GB | 46,5 s | 36,3 s | 1,76x
- Los dos clústeres usan exactamente el mismo plan de ejecución.
- Partir los archivos en pedazos más chicos ayuda a RG y perjudica a RA3.
- Lo repetimos una sola vez: la tendencia es clara; el número exacto, no tanto.

**Notas:** Este fue el resultado que más me sorprendió. Con Parquet, RG empezó siendo más lento que RA3. Revisé el plan de ejecución y era idéntico en los dos. La diferencia estaba en los archivos: Redshift los había escrito en solo cuatro archivos enormes, uno por slice, porque por defecto cada archivo puede llegar a 6.200 MB. Los reescribí en archivos de medio giga y RG pasó a ganar, mientras que RA3 empeoró. El mismo cambio ayuda a uno y perjudica al otro.

## 24
- Spectrum cobra aparte
- USD 0,083
- 18,2 GB leídos de Iceberg (2 repeticiones)
- USD 0,092
- 20,2 GB leídos de Parquet (2 repeticiones)
- USD 0
- por lectura en RG
- En RA3 se pagan USD 5 por cada TB leído. Multiplícalo por todo lo que consultas del data lake en un mes.

**Notas:** En el laboratorio son centavos, porque son 100 GB. Pero esto crece con el volumen y con la frecuencia: un equipo que lee decenas de TB al mes desde el data lake lo nota en la factura. En RG ese cobro desaparece.

## 25
- Lo que aprendimos del data lake
- S3 Tables pide IAM
- cross-database reference to database "…@s3tablescatalog" is not supported
- Iceberg no acepta CHAR
- CHAR type is not supported for column "d_date_id" in Iceberg table creation
- Lake Formation manda
- Insufficient Lake Formation permission(s): Required Create Table on rr_iceberg
- Si vas a usar S3 Tables desde Redshift, decide primero cómo se van a autenticar tus usuarios.

**Notas:** Quería probar S3 Tables y no pude, por una razón de diseño: esas tablas solo se leen conectándose con una identidad de IAM, y mi programa se conecta con un usuario de base de datos. Cambiar de usuario solo para esa prueba habría medido otra cosa. Además, Iceberg no acepta columnas CHAR, y Lake Formation exige permisos explícitos sobre las bases de Glue.

## 26
- LA
- MIGRACIÓN

**Notas:** Supongamos que decides migrar. ¿Cuánto cuesta en tiempo y en sustos?

## 27
- La migración tomó 2 min 48 s
- 19:05:47
- inicio
- 19:05:53
- se puede escribir
- 19:06:25
- solo lectura
- 19:06:57
- solo lectura
- 19:07:29
- solo lectura
- 19:08:00
- solo lectura
- 19:08:35
- se puede escribir
- 1:35 a 2:42
- minutos sin poder escribir (lo revisamos cada 30 s)
- Sin cambios
- en cómo se reparten los datos entre nodos

**Notas:** Restauré una copia del clúster RA3 y lo convertí a RG con un elastic resize, intentando escribir cada 30 segundos. Empezó a las 19:05:47 y terminó a las 19:08:35. El clúster quedó en solo lectura entre 1 minuto 35 y 2 minutos 42 segundos; el rango se debe a que revisábamos cada 30 segundos. Como pasamos de 2 nodos a 2 nodos, los datos quedaron repartidos igual. Ojo: si cambias la cantidad de nodos, como al pasar de 4 a 3 en el tamaño 4xlarge, el reparto sí puede desbalancearse.

## 28
- Lo que nadie te cuenta
- La contraseña administrada: para restaurar el snapshot hay que volver a pedirla con ‑‑manage‑master‑password
- Primero, un snapshot: un clúster recién restaurado no acepta el resize hasta tener un snapshot propio
- «Disponible» no es lo mismo que listo: el estado dice available, pero otro campo sigue en Modifying y el resize falla
- De 4 a 3 nodos: cambiar la cantidad de nodos puede desbalancear los datos
- Restaurar cambia el endpoint: si migras desde un snapshot, hay que reconfigurar zero-ETL, DMS y datashares

**Notas:** Las tres primeras me pasaron en el simulacro, en ese orden, y no las encontré en la guía de migración. Las dos últimas sí aparecen en la documentación y en el blog de AWS. Todas quedaron resueltas en el script del repositorio.

## 29
- DEMO

**Notas:** Ahora veamos las consultas y los datos reales.

## 30
- Demo: una consulta, dos clústeres
- SELECT count(*)
- FROM store_sales, household_demographics,
- time_dim, store
- WHERE ss_sold_time_sk = time_dim.t_time_sk
- AND ss_hdemo_sk = household_demographics.hd_demo_sk
- AND ss_store_sk = s_store_sk
- AND time_dim.t_hour = 15
- AND time_dim.t_minute >= 30
- AND household_demographics.hd_dep_count = 7
- AND store.s_store_name = 'ese'
- LIMIT 100;
- Por qué pesa: recorre las 288 millones de ventas de store_sales y las cruza con tres tablas para quedarse con una franja horaria y un tipo de hogar.
- query96
- 1,77 s
- 0,67 s
- RA3
- RG
- menos tiempo es mejor
- RG fue 2,64x más rápido

**Notas:** Esta es una consulta típica de lectura: cuenta ventas filtrando por hora del día, por tipo de hogar y por tienda. Lo pesado es que tiene que recorrer las 288 millones de filas de la tabla de ventas y cruzarlas con tres tablas más. En RA3 tarda 1,77 segundos; en RG, 0,67.

## 31
- Demo: el mismo plan en los dos
- RA3  (lq3 sobre Parquet)
- XN Hash Join DS_BCAST_INNER
- XN Hash Join DS_BCAST_INNER
- XN S3 Query Scan ss
- S3 Seq Scan pq.store_sales
- rows=287997024
- RG  (lq3 sobre Parquet)
- XN Hash Join DS_BCAST_INNER
- XN Hash Join DS_BCAST_INNER
- XN Seq Scan pq.store_sales
- format:PARQUET
- rows=287997024
- Mismos joins y mismas estimaciones de filas. Lo único que cambia es quién lee los datos de S3.

**Notas:** Así encontré la explicación del caso de Parquet. Si los planes fueran distintos, la diferencia estaría en el plan y no en el clúster. Son iguales: lo único que cambia es la pieza que lee S3, Spectrum en RA3 y los propios nodos en RG. Cuando veas una diferencia rara entre dos clústeres, empieza por aquí.

## 32
- Demo: todos los resultados
- [imagen]
- Una página con todos los números de la charla:
- Cuánto mejoró RG en cada consulta
- El data lake antes y después de reescribir los archivos Parquet
- La línea de tiempo de la migración

**Notas:** Esta página reúne todos los números de la charla, sacados directamente de los archivos del repositorio. La abro un momento para que vean cada consulta. Abrir: https://claude.ai/artifact/1MgMakVPq4URRXQMZp4aVk (privada, con la sesión del orador; copia local: slides/demo/resultados.html).

## 33
- ¿Migrar o no migrar?
- Migra si
- • Tus consultas leen y agregan muchos datos (dashboards, reportes)
- • Consultas seguido el data lake
- • Usas xlplus o 4xlarge: pagas 30 % menos por vCPU
- Prueba antes si
- • Tus consultas son de cálculo pesado (ventanas, joins grandes)
- • Tu data lake está en Parquet con archivos grandes
- • Quieres usar S3 Tables con usuarios de base de datos
- Mira Serverless si
- • Usas Redshift solo a ratos
- • No quieres administrar un clúster
- • A 4 RPU fue 3 veces más lento que RG: dale más capacidad

**Notas:** Esta es mi respuesta a la pregunta del título. Para la mayoría de los equipos con RA3, migrar conviene: es más rápido, más barato y el cambio toma minutos. Pero prueba primero con tus datos, sobre todo si tu data lake está en Parquet o si tus consultas son de cálculo pesado. Serverless es otra decisión, que depende de cómo usas Redshift: a 4 RPU fijos fue mucho más lento que RG, así que si lo eliges, dale más capacidad o deja que escale.

## 34
- Llévate el laboratorio
- github.com/andrezc98/redshift-redemption
- [imagen]
- Escanea para ir al repo
- La infraestructura, con Terraform y GitHub Actions (OIDC)
- El programa de pruebas, en Python, y el runbook paso a paso
- Todos los resultados, con su método, en la carpeta results/
- Repetirlo con 100 GB toma un día de trabajo y unas decenas de dólares

**Notas:** Todo lo que vieron está en el repositorio: la infraestructura, el programa que lanza las pruebas, el runbook con cada paso y los errores que me encontré. Cámbienle el dataset por el suyo y repitan las mediciones.

## 35
- Quiz
- Pregunta 1
- ¿Con qué lee RG los datos del data lake?
- Pregunta 2
- ¿Qué tipo de consultas mejoró más al pasar de RA3 a RG?
- Pregunta 3
- Si tienes 4 nodos ra3.4xlarge, ¿cuántos rg.4xlarge recomienda AWS?
- Pregunta 4
- En el simulacro de migración (elastic resize), ¿cuánto tiempo estuvo el clúster sin aceptar escrituras?
- Las respuestas y los comentarios están en las notas.

**Notas:** Quiz. Pregunta 1: ¿Con qué lee RG los datos del data lake? a) Redshift Spectrum; b) Con sus propios nodos, sin Spectrum (correcta); c) Amazon Athena; d) Trabajos de AWS Glue. Comentario: RA3 usa Spectrum, que cobra USD 5 por TB leído; RG lee el data lake con sus propios nodos y sin ese cobro. Pregunta 2: ¿Qué tipo de consultas mejoró más al pasar de RA3 a RG? a) Las de cálculo pesado (ventanas, joins grandes); b) Ninguna, quedaron igual; c) Las que leen y agregan muchos datos (correcta); d) Solo las del data lake. Comentario: 2,28 veces en lectura contra 1,58 en cálculo; el promedio de las 20 consultas fue 1,90. Pregunta 3: Si tienes 4 nodos ra3.4xlarge, ¿cuántos rg.4xlarge recomienda AWS? a) 3 (correcta); b) 4; c) 2; d) 8. Comentario: Un ra3.4xlarge tiene 12 vCPU y un rg.4xlarge, 16: 4 × 12 = 3 × 16 = 48. Migrar uno a uno en ese tamaño deja un tercio de capacidad de más. Pregunta 4: En el simulacro de migración (elastic resize), ¿cuánto tiempo estuvo el clúster sin aceptar escrituras? a) Nada, siempre aceptó escrituras; b) Unos 30 minutos; c) Varias horas; d) Entre 1,5 y 3 minutos (correcta). Comentario: Entre 1 min 35 s y 2 min 42 s; el resize completo tomó 2 min 48 s.

## 36
- Kahoot
- Pregunta 1
- ¿Qué procesadores usan los nuevos nodos RG de Redshift?
- Pregunta 2
- ¿Cuánto menos cuesta RG por vCPU frente a RA3?
- Las respuestas y los comentarios están en las notas.

**Notas:** Kahoot. Pregunta 1: ¿Qué procesadores usan los nuevos nodos RG de Redshift? a) Intel Xeon; b) AMD EPYC; c) AWS Graviton (correcta); d) Apple M. Comentario: RG usa Graviton, los procesadores Arm diseñados por AWS. Pregunta 2: ¿Cuánto menos cuesta RG por vCPU frente a RA3? a) 30 % (correcta); b) 10 %; c) 50 %; d) Cuesta lo mismo. Comentario: USD 1,086 entre 4 vCPU en ra3.xlplus contra 0,7602 entre 4 en rg.xlarge: 30 % menos.

## 37
- ¡Gracias!
- Andrés Zeballos
- Solutions Architect en phData
- LinkedIn: linkedin.com/in/andreszc
- GitHub: andrezc98
- [imagen]
- LinkedIn
- [imagen]
- El laboratorio

**Notas:** Gracias. Respondo preguntas en el chat. Si alguien pregunta por Snowflake u otras plataformas: trabajo con varias y son buenas respuestas para contextos distintos; hoy vine a medir la decisión que ya tienen enfrente los equipos que usan AWS: RA3 o RG.
