# Preguntas para el quiz y el Kahoot

Charla «Redshift Redemption: los nuevos nodos RG, ¿migrar o no migrar?». Generado por
`slides/build_deck.py`. La respuesta correcta está marcada con ✅.

## Quiz (preguntas sobre la charla)

**1. ¿Con qué lee RG los datos del data lake?**
- a) Redshift Spectrum
- b) Con sus propios nodos, sin Spectrum ✅
- c) Amazon Athena
- d) Con la Fuerza, como los Jedi

Comentario: RA3 usa Spectrum, que cobra USD 5 por TB leído; RG lee el data lake con sus propios nodos y sin ese cobro.

**2. ¿Qué tipo de consultas mejoró más al pasar de RA3 a RG?**
- a) Las de cálculo pesado (ventanas, joins grandes)
- b) Las escritas en MAYÚSCULAS
- c) Las que leen y agregan muchos datos ✅
- d) Solo las del data lake

Comentario: 2,28 veces en lectura contra 1,58 en cálculo; el promedio de las 20 consultas fue 1,90.

**3. Si tienes 4 nodos ra3.4xlarge, ¿cuántos rg.4xlarge recomienda AWS?**
- a) 3 ✅
- b) 4
- c) 42, obviamente
- d) 8

Comentario: Un ra3.4xlarge tiene 12 vCPU y un rg.4xlarge, 16: 4 × 12 = 3 × 16 = 48. Migrar uno a uno en ese tamaño deja un tercio de capacidad de más.

**4. En el simulacro de migración (elastic resize), ¿cuánto tiempo estuvo el clúster sin aceptar escrituras?**
- a) Nada, siempre aceptó escrituras
- b) Unos 30 minutos
- c) Hasta que terminara esta charla
- d) Entre 1,5 y 3 minutos ✅

Comentario: Entre 1 min 35 s y 2 min 42 s; el resize completo tomó 2 min 48 s.

## Kahoot (preguntas sencillas)

**1. ¿Qué procesadores usan los nuevos nodos RG de Redshift?**
- a) Intel Xeon
- b) AMD EPYC
- c) AWS Graviton ✅
- d) Un hámster muy motivado

Comentario: RG usa Graviton, los procesadores Arm diseñados por AWS.

**2. ¿Cuánto menos cuesta RG por vCPU frente a RA3?**
- a) 30 % ✅
- b) 10 %
- c) Te pagan por usarlo
- d) Cuesta lo mismo

Comentario: USD 1,086 entre 4 vCPU en ra3.xlplus contra 0,7602 entre 4 en rg.xlarge: 30 % menos.
