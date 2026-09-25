# Redshift Redemption: los nuevos nodos RG, ¿migrar o no migrar?

Laboratorio de la charla para AWS Women Colombia (8 de octubre de 2026). Mide Amazon Redshift
RA3 contra la nueva generación RG (Graviton) con el mismo dataset derivado de
TPC-DS, las mismas consultas y la misma configuración: tiempo y costo lado a
lado, en el tamaño de clúster que la mayoría de los equipos opera.

> Estado: plan listo, laboratorio sin ejecutar.
> Spec: `docs/superpowers/specs/2026-09-24-redshift-redemption-design.md`
> Plan: `docs/superpowers/plans/2026-09-24-redshift-redemption.md`

## Versiones probadas
(se llena con cada corrida; verificar contra la documentación del día)

- Runner: Python 3.13, boto3 1.43.102, pytest 9.1.1 (uv.lock, 2026-09-24)
