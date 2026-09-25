-- Iceberg copies in the S3 table bucket rr-lake, namespace tpcds, written by the RA3 cluster.
-- start template b_date_dim
CREATE TABLE "rr-lake@s3tablescatalog".tpcds.date_dim USING ICEBERG AS SELECT * FROM public.date_dim;
-- end template b_date_dim
-- start template b_item
CREATE TABLE "rr-lake@s3tablescatalog".tpcds.item USING ICEBERG AS SELECT * FROM public.item;
-- end template b_item
-- start template b_store
CREATE TABLE "rr-lake@s3tablescatalog".tpcds.store USING ICEBERG AS SELECT * FROM public.store;
-- end template b_store
-- start template b_customer
CREATE TABLE "rr-lake@s3tablescatalog".tpcds.customer USING ICEBERG AS SELECT * FROM public.customer;
-- end template b_customer
-- start template b_store_sales
CREATE TABLE "rr-lake@s3tablescatalog".tpcds.store_sales USING ICEBERG AS SELECT * FROM public.store_sales;
-- end template b_store_sales
