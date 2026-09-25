-- start template schema
CREATE EXTERNAL SCHEMA IF NOT EXISTS pq FROM DATA CATALOG DATABASE 'rr_parquet' IAM_ROLE default;
-- end template schema
-- start template b_date_dim
CREATE EXTERNAL TABLE pq.date_dim STORED AS PARQUET LOCATION 's3://{bucket}/parquet/date_dim/' AS SELECT * FROM public.date_dim;
-- end template b_date_dim
-- start template b_item
CREATE EXTERNAL TABLE pq.item STORED AS PARQUET LOCATION 's3://{bucket}/parquet/item/' AS SELECT * FROM public.item;
-- end template b_item
-- start template b_store
CREATE EXTERNAL TABLE pq.store STORED AS PARQUET LOCATION 's3://{bucket}/parquet/store/' AS SELECT * FROM public.store;
-- end template b_store
-- start template b_customer
CREATE EXTERNAL TABLE pq.customer STORED AS PARQUET LOCATION 's3://{bucket}/parquet/customer/' AS SELECT * FROM public.customer;
-- end template b_customer
-- start template b_store_sales
CREATE EXTERNAL TABLE pq.store_sales STORED AS PARQUET LOCATION 's3://{bucket}/parquet/store_sales/' AS SELECT * FROM public.store_sales;
-- end template b_store_sales
