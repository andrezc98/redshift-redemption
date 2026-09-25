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
| ra3.xlplus | TODO | node-hour | |
| rg.xlarge | TODO | node-hour | |
| ra3.4xlarge | TODO | node-hour | |
| rg.4xlarge | TODO | node-hour | |
| serverless_rpu | TODO | RPU-hour | |
| spectrum_per_tb | TODO | TB scanned | |
| rms_gb_month | TODO | GB-month | |
