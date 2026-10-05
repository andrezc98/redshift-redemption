# Tarifas del lab

Única fuente de precios del proyecto. Se completa el día del lab con la tarifa
on-demand vigente en us-east-1; `rr report` se niega a calcular mientras alguna
celda diga TODO.

Cómo leerlas (API de precios, la misma que usó el spec el 2026-09-24):

    aws pricing get-products --region us-east-1 --service-code AmazonRedshift \
      --filters Type=TERM_MATCH,Field=instanceType,Value=rg.xlarge \
                Type=TERM_MATCH,Field=location,Value='US East (N. Virginia)'

| item | usd | unit | captured (date, source) |
|---|---|---|---|
| ra3.xlplus | 1.086 | node-hour | 2026-10-05, Price List API (vigente desde 2026-06-01) |
| rg.xlarge | 0.7602 | node-hour | 2026-10-05, Price List API (vigente desde 2026-06-01) |
| ra3.4xlarge | 3.26 | node-hour | 2026-10-05, Price List API (vigente desde 2026-06-01) |
| rg.4xlarge | 3.04267 | node-hour | 2026-10-05, Price List API (vigente desde 2026-06-01) |
| serverless_rpu | 0.375 | RPU-hour | 2026-10-05, Price List API (vigente desde 2026-06-01) |
| spectrum_per_tb | 5.00 | TB scanned | 2026-10-05, Price List API (vigente desde 2026-06-01) |
| rms_gb_month | 0.024 | GB-month | 2026-10-05, Price List API (vigente desde 2026-06-01) |
