-- Drops the lake copies so the next build starts clean. DROP only unregisters the table:
-- the runbook deletes the files under s3://<lake bucket>/ separately. One block per table so
-- a table that was never built doesn't stop the rest.
-- start template s_date_dim
DROP TABLE "rr-lake@s3tablescatalog".tpcds.date_dim;
-- end template s_date_dim
-- start template s_item
DROP TABLE "rr-lake@s3tablescatalog".tpcds.item;
-- end template s_item
-- start template s_store
DROP TABLE "rr-lake@s3tablescatalog".tpcds.store;
-- end template s_store
-- start template s_customer
DROP TABLE "rr-lake@s3tablescatalog".tpcds.customer;
-- end template s_customer
-- start template s_store_sales
DROP TABLE "rr-lake@s3tablescatalog".tpcds.store_sales;
-- end template s_store_sales
-- start template p_date_dim
DROP TABLE pq.date_dim;
-- end template p_date_dim
-- start template p_item
DROP TABLE pq.item;
-- end template p_item
-- start template p_store
DROP TABLE pq.store;
-- end template p_store
-- start template p_customer
DROP TABLE pq.customer;
-- end template p_customer
-- start template p_store_sales
DROP TABLE pq.store_sales;
-- end template p_store_sales
-- start template i_date_dim
DROP TABLE ice.date_dim;
-- end template i_date_dim
-- start template i_item
DROP TABLE ice.item;
-- end template i_item
-- start template i_store
DROP TABLE ice.store;
-- end template i_store
-- start template i_customer
DROP TABLE ice.customer;
-- end template i_customer
-- start template i_store_sales
DROP TABLE ice.store_sales;
-- end template i_store_sales
