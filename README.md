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
- Consultas y DDL: awslabs/amazon-redshift-utils `CloudDataWarehouseBenchmark/Cloud-DWB-Derived-from-TPCDS/1TB` @ f208c11 (sin modificar, `sql/vendor/`)
- Terraform >= 1.15, hashicorp/aws 6.66.0 (lock), estado local; VPC propia (la sandbox no tiene VPC por defecto en us-east-1)

## Problemas conocidos

- `rr` falla con `No module named 'rr'`: en esta Mac, Python 3.13 ignora los `.pth`
  que macOS marca como ocultos, y `uv` los vuelve a crear ocultos en cada sync. Por
  eso el runbook define `rr()` con `PYTHONPATH=runner`, que no depende de los `.pth`.
