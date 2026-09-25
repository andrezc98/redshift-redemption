-- start template lq3
SELECT dt.d_year, it.i_brand_id AS brand_id, it.i_brand AS brand, SUM(ss.ss_ext_sales_price) AS sum_agg
FROM {lake}date_dim dt JOIN {lake}store_sales ss ON dt.d_date_sk = ss.ss_sold_date_sk
JOIN {lake}item it ON ss.ss_item_sk = it.i_item_sk
WHERE it.i_manufact_id = 128 AND dt.d_moy = 11
GROUP BY dt.d_year, it.i_brand, it.i_brand_id
ORDER BY dt.d_year, sum_agg DESC, brand_id
LIMIT 100;
-- end template lq3
-- start template lq42
SELECT dt.d_year, it.i_category_id, it.i_category, SUM(ss.ss_ext_sales_price) AS total
FROM {lake}date_dim dt JOIN {lake}store_sales ss ON dt.d_date_sk = ss.ss_sold_date_sk
JOIN {lake}item it ON ss.ss_item_sk = it.i_item_sk
WHERE it.i_manager_id = 1 AND dt.d_moy = 11 AND dt.d_year = 2000
GROUP BY 1, 2, 3 ORDER BY total DESC, 1, 2, 3
LIMIT 100;
-- end template lq42
-- start template lq52
SELECT dt.d_year, it.i_brand_id AS brand_id, it.i_brand AS brand, SUM(ss.ss_ext_sales_price) AS ext_price
FROM {lake}date_dim dt JOIN {lake}store_sales ss ON dt.d_date_sk = ss.ss_sold_date_sk
JOIN {lake}item it ON ss.ss_item_sk = it.i_item_sk
WHERE it.i_manager_id = 1 AND dt.d_moy = 11 AND dt.d_year = 2000
GROUP BY 1, 2, 3 ORDER BY 1, ext_price DESC, brand_id
LIMIT 100;
-- end template lq52
-- start template lq55
SELECT it.i_brand_id AS brand_id, it.i_brand AS brand, SUM(ss.ss_ext_sales_price) AS ext_price
FROM {lake}date_dim dt JOIN {lake}store_sales ss ON dt.d_date_sk = ss.ss_sold_date_sk
JOIN {lake}item it ON ss.ss_item_sk = it.i_item_sk
WHERE it.i_manager_id = 28 AND dt.d_moy = 11 AND dt.d_year = 1999
GROUP BY 1, 2 ORDER BY ext_price DESC, brand_id
LIMIT 100;
-- end template lq55
-- start template lqst
SELECT s.s_state, dt.d_year, SUM(ss.ss_net_paid) AS net_paid, COUNT(*) AS n
FROM {lake}store_sales ss JOIN {lake}store s ON ss.ss_store_sk = s.s_store_sk
JOIN {lake}date_dim dt ON ss.ss_sold_date_sk = dt.d_date_sk
GROUP BY 1, 2 ORDER BY 1, 2;
-- end template lqst
-- start template lqcu
SELECT c.c_customer_id, c.c_last_name, SUM(ss.ss_net_paid) AS net_paid
FROM {lake}store_sales ss JOIN {lake}customer c ON ss.ss_customer_sk = c.c_customer_sk
JOIN {lake}date_dim dt ON ss.ss_sold_date_sk = dt.d_date_sk
WHERE dt.d_year = 2001
GROUP BY 1, 2 ORDER BY net_paid DESC
LIMIT 100;
-- end template lqcu
