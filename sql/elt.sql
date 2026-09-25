-- start template ecopy
DROP TABLE IF EXISTS elt_store_returns;
CREATE TABLE elt_store_returns (LIKE store_returns);
copy elt_store_returns from 's3://redshift-downloads/TPC-DS/2.13/{scale}/store_returns/' iam_role default gzip delimiter '|' EMPTYASNULL region 'us-east-1';
-- end template ecopy
-- start template ectas
DROP TABLE IF EXISTS elt_sales_by_item_month;
CREATE TABLE elt_sales_by_item_month AS
SELECT it.i_category, it.i_brand, dt.d_year, dt.d_moy, SUM(ss.ss_net_paid) AS net_paid, COUNT(*) AS n
FROM store_sales ss JOIN date_dim dt ON ss.ss_sold_date_sk = dt.d_date_sk
JOIN item it ON ss.ss_item_sk = it.i_item_sk
GROUP BY 1, 2, 3, 4;
-- end template ectas
